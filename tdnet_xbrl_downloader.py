#!/usr/bin/env python3
"""
TDnetからXBRLファイルをダウンロードする機能
コマンドライン引数対応版 + XBRL財務データ解析機能
"""

"""
実行コマンド
#### 決算短信の一括処理
# 基本的な一括処理（ダウンロード→財務データ抽出→CSV出力→ファイル削除）
uv run python tdnet_xbrl_downloader.py --extract-all -d 2025-09-15 --filter kessan --all-pages
"""

import argparse
import requests
from bs4 import BeautifulSoup
import urllib.parse
from datetime import datetime, timedelta
import os
import zipfile
from pathlib import Path
import time
import sys
import json
import csv
from typing import Dict, List, Optional, Union

def analyze_pagination_structure(soup, debug=False):
    """
    ページング構造を分析
    
    Args:
        soup: BeautifulSoupオブジェクト
        debug: デバッグ情報を表示するかどうか
    
    Returns:
        ページング情報の辞書
    """
    
    pagination_info = {
        'has_next': False,
        'next_url': None,
        'current_page': None,
        'total_pages': None,
        'total_count': None,
        'pagination_elements': []
    }
    
    if debug:
        print("\n" + "="*60)
        print("【ページング構造調査】")
        print("-"*60)
    
    # 「次へ」ボタンや類似要素を探す
    next_keywords = ['次へ', 'next', '→', '＞', 'Next']
    
    for keyword in next_keywords:
        # aタグで検索
        next_links = soup.find_all('a', string=lambda text: text and keyword in text)
        if next_links and debug:
            print(f"\n「{keyword}」を含むリンク: {len(next_links)}個")
            for i, link in enumerate(next_links[:3]):
                href = link.get('href', 'なし')
                onclick = link.get('onclick', 'なし')
                parent = link.parent.name if link.parent else 'なし'
                print(f"  {i+1}. href='{href}', onclick='{onclick}', parent=<{parent}>")
        
        # input/buttonで検索
        next_buttons = soup.find_all(['input', 'button'], value=lambda value: value and keyword in value if value else False)
        if next_buttons and debug:
            print(f"\n「{keyword}」を含むボタン: {len(next_buttons)}個")
            for i, button in enumerate(next_buttons[:3]):
                button_type = button.get('type', 'なし')
                onclick = button.get('onclick', 'なし')
                name = button.get('name', 'なし')
                print(f"  {i+1}. type='{button_type}', onclick='{onclick}', name='{name}'")
    
    # ページ番号関連の要素を探す
    if debug:
        print(f"\n【ページ番号・件数情報】")
        
        # 件数表示パターンを探す (1～100件 / 全136件 のような)
        import re
        count_patterns = soup.find_all(string=re.compile(r'\d+～\d+.*全\d+'))
        if count_patterns:
            print(f"件数表示パターン: {len(count_patterns)}個")
            for i, pattern in enumerate(count_patterns):
                text = pattern.strip()
                print(f"  {i+1}. '{text}'")
        
        # より広いパターンで数字を含む表示を探す
        number_patterns = soup.find_all(string=re.compile(r'\d+.*\d+.*件'))
        if number_patterns:
            print(f"件数関連テキスト: {len(number_patterns)}個")
            for i, pattern in enumerate(number_patterns[:5]):
                text = pattern.strip()
                if text:
                    print(f"  {i+1}. '{text}'")
        
        # pagerTd クラスの要素を詳しく調査
        print(f"\n【pagerTd要素の詳細調査】")
        pager_elements = soup.find_all(class_='pagerTd')
        if pager_elements:
            print(f"pagerTd要素: {len(pager_elements)}個")
            for i, pager in enumerate(pager_elements):
                print(f"\n  pagerTd {i+1}:")
                print(f"    全体HTML: {str(pager)[:200]}...")
                
                # div要素を探す
                divs = pager.find_all('div')
                print(f"    内部div数: {len(divs)}")
                
                for j, div in enumerate(divs[:5]):
                    onclick = div.get('onclick', '')
                    text = div.get_text(strip=True)
                    print(f"      div {j+1}: onclick='{onclick}', text='{text}'")
        else:
            print("pagerTd要素が見つかりません")
        
        # form要素とhidden inputを調査
        print(f"\n【フォーム要素の調査】")
        forms = soup.find_all('form')
        print(f"form要素: {len(forms)}個")
        
        for i, form in enumerate(forms):
            action = form.get('action', '')
            method = form.get('method', '')
            print(f"  form {i+1}: action='{action}', method='{method}'")
            
            # hidden input要素
            hidden_inputs = form.find_all('input', type='hidden')
            if hidden_inputs:
                print(f"    hidden input: {len(hidden_inputs)}個")
                for j, inp in enumerate(hidden_inputs[:10]):
                    name = inp.get('name', '')
                    value = inp.get('value', '')
                    print(f"      {j+1}. name='{name}', value='{value}'")
    
    # JavaScriptコードを探す
    if debug:
        print(f"\n【JavaScript分析】")
        scripts = soup.find_all('script')
        js_pagination_found = False
        
        for script in scripts:
            if script.string:
                # ページング関連のJavaScript関数を探す
                js_keywords = ['next', 'page', 'paging', 'pagination', 'changePage']
                for keyword in js_keywords:
                    if keyword in script.string.lower():
                        if not js_pagination_found:
                            print("ページング関連のJavaScript関数を発見:")
                            js_pagination_found = True
                        
                        # 関数の抜粋を表示
                        lines = script.string.split('\n')
                        for line_num, line in enumerate(lines):
                            if keyword in line.lower():
                                start = max(0, line_num - 2)
                                end = min(len(lines), line_num + 3)
                                print(f"  関数抜粋 (行{line_num}):")
                                for i in range(start, end):
                                    marker = "→" if i == line_num else " "
                                    print(f"    {marker} {lines[i].strip()}")
                                break
                        break
        
        if not js_pagination_found:
            print("ページング関連のJavaScriptは見つかりませんでした")
    
    return pagination_info


def check_all_pages_duplicates(date_str, max_pages=15):
    """
    全ページの重複確認を実行
    
    Args:
        date_str: YYYYMMDD形式の日付文字列
        max_pages: 確認する最大ページ数
    
    Returns:
        重複確認結果の辞書
    """
    
    print("="*60)
    print("【全ページ重複確認】")
    print("="*60)
    
    all_xbrl_urls = set()
    all_records = []
    page_stats = []
    
    for page in range(1, max_pages + 1):
        print(f"\nページ {page} を確認中...")
        
        try:
            records = fetch_xbrl_list(date_str, debug=False, page=page)
            
            if not records:
                print(f"  ページ {page}: データなし（終了）")
                break
                
            # このページのXBRL URL一覧
            page_urls = set()
            xbrl_count = 0
            
            for record in records:
                if record.get('xbrl_url'):
                    page_urls.add(record['xbrl_url'])
                    xbrl_count += 1
            
            # 重複チェック
            duplicates = page_urls & all_xbrl_urls
            
            page_info = {
                'page': page,
                'total_records': len(records),
                'xbrl_count': xbrl_count,
                'new_urls': len(page_urls - all_xbrl_urls),
                'duplicates': len(duplicates),
                'duplicate_urls': list(duplicates)
            }
            
            page_stats.append(page_info)
            
            print(f"  ページ {page}: {len(records)}件の開示情報, {xbrl_count}件のXBRL")
            print(f"    新規XBRL: {page_info['new_urls']}件")
            if duplicates:
                print(f"    ⚠️ 重複XBRL: {len(duplicates)}件")
                for dup_url in list(duplicates)[:3]:  # 最初の3件を表示
                    print(f"      - {dup_url}")
            else:
                print(f"    ✅ 重複なし")
            
            # 累積データに追加
            all_xbrl_urls.update(page_urls)
            all_records.extend(records)
            
            # 少し待機
            time.sleep(0.5)
            
        except Exception as e:
            print(f"  ページ {page}: エラー - {e}")
            break
    
    # 結果サマリー
    print(f"\n" + "="*60)
    print("【重複確認結果サマリー】")
    print("="*60)
    
    total_pages = len(page_stats)
    total_records = sum(p['total_records'] for p in page_stats)
    total_xbrl = sum(p['xbrl_count'] for p in page_stats)
    total_duplicates = sum(p['duplicates'] for p in page_stats)
    
    print(f"確認ページ数: {total_pages}ページ")
    print(f"総開示情報: {total_records}件")
    print(f"総XBRL件数: {total_xbrl}件")
    print(f"ユニークXBRL: {len(all_xbrl_urls)}件")
    print(f"重複XBRL: {total_duplicates}件")
    
    if total_duplicates == 0:
        print("✅ 重複は確認されませんでした")
    else:
        print("⚠️ 重複が確認されました")
        
    # ページ別詳細
    print(f"\n【ページ別詳細】")
    for p in page_stats:
        dup_mark = "⚠️" if p['duplicates'] > 0 else "✅"
        print(f"  ページ{p['page']:2d}: {p['total_records']:3d}件 / XBRL{p['xbrl_count']:2d}件 / 重複{p['duplicates']:2d}件 {dup_mark}")
    
    return {
        'total_pages': total_pages,
        'total_records': total_records,
        'total_xbrl': total_xbrl,
        'unique_xbrl': len(all_xbrl_urls),
        'total_duplicates': total_duplicates,
        'page_stats': page_stats,
        'all_records': all_records
    }


def fetch_all_pages_xbrl(date_str, debug=False):
    """
    全ページからXBRLデータを取得
    
    Args:
        date_str: YYYYMMDD形式の日付文字列
        debug: デバッグ情報を表示するかどうか
    
    Returns:
        全ページのXBRLデータのリスト
    """
    
    print("="*60)
    print("【全ページXBRL取得】")
    print("="*60)
    
    all_xbrl_records = []
    page = 1
    total_pages = 0
    
    # 1ページ目で総件数を取得
    print("1ページ目で総件数を確認中...")
    first_page_records = fetch_xbrl_list(date_str, debug=False, page=1)
    
    if not first_page_records:
        print("❌ 1ページ目のデータが取得できませんでした")
        return []
    
    # 総件数を取得するために再度アクセス
    try:
        url = f'https://www.release.tdnet.info/inbs/I_list_001_{date_str}.html'
        r = requests.get(url)
        r.raise_for_status()
        soup = BeautifulSoup(r.content, 'html.parser')
        r.close()
        
        # 件数表示パターンを探す (1～100件 / 全1048件 のような)
        import re
        count_patterns = soup.find_all(string=re.compile(r'\d+～\d+.*全(\d+)'))
        total_count = 0
        
        for pattern in count_patterns:
            match = re.search(r'全(\d+)件', pattern)
            if match:
                total_count = int(match.group(1))
                break
        
        if total_count > 0:
            total_pages = (total_count + 99) // 100  # 切り上げ計算
            print(f"総件数: {total_count}件")
            print(f"予想ページ数: {total_pages}ページ")
        else:
            print("総件数が取得できませんでした。順次アクセスで確認します。")
            total_pages = 20  # 最大20ページまで確認
            
    except Exception as e:
        print(f"総件数取得エラー: {e}")
        total_pages = 20  # エラー時は最大20ページ
    
    # 全ページを順次取得
    print(f"\n全ページのXBRLデータを取得開始...")
    print("-"*60)
    
    for page in range(1, total_pages + 1):
        print(f"\nページ {page}/{total_pages if total_pages <= 20 else '?'} を取得中...")
        
        try:
            if page == 1:
                # 1ページ目は既に取得済み
                records = first_page_records
            else:
                records = fetch_xbrl_list(date_str, debug=False, page=page)
            
            if not records:
                print(f"  ページ {page}: データなし（全{page-1}ページで完了）")
                break
            
            # XBRLデータのみを抽出
            xbrl_records = [r for r in records if r.get('xbrl_url')]
            
            print(f"  ページ {page}: {len(records)}件の開示情報, {len(xbrl_records)}件のXBRL")
            
            # 累積データに追加
            all_xbrl_records.extend(xbrl_records)
            
            # サーバーに負荷をかけないよう少し待機
            if page < total_pages:
                time.sleep(0.5)
                
        except requests.exceptions.HTTPError as e:
            if "404" in str(e):
                print(f"  ページ {page}: 存在しません（全{page-1}ページで完了）")
                break
            else:
                print(f"  ページ {page}: HTTPエラー - {e}")
                break
        except Exception as e:
            print(f"  ページ {page}: エラー - {e}")
            break
    
    # 重複排除（念のため）
    unique_urls = set()
    unique_records = []
    duplicates_removed = 0
    
    for record in all_xbrl_records:
        xbrl_url = record.get('xbrl_url')
        if xbrl_url and xbrl_url not in unique_urls:
            unique_urls.add(xbrl_url)
            unique_records.append(record)
        elif xbrl_url:
            duplicates_removed += 1
    
    # 結果サマリー
    print(f"\n" + "="*60)
    print("【全ページ取得結果】")
    print("="*60)
    
    actual_pages = page - 1 if page > 1 else 1
    print(f"取得ページ数: {actual_pages}ページ")
    print(f"総XBRLデータ: {len(all_xbrl_records)}件")
    print(f"ユニークXBRL: {len(unique_records)}件")
    if duplicates_removed > 0:
        print(f"重複除去: {duplicates_removed}件")
    else:
        print("重複: なし")
    
    return unique_records


def fetch_xbrl_list(date_str="20250819", debug=False, page=1):
    """
    指定日付・ページのXBRLファイル一覧を取得
    
    Args:
        date_str: YYYYMMDD形式の日付文字列
        debug: デバッグ情報を表示するかどうか
        page: 取得するページ番号
    
    Returns:
        XBRLデータのリスト
    """
    
    # ページ番号に応じてURLを構築
    url = f'https://www.release.tdnet.info/inbs/I_list_{page:03d}_{date_str}.html'
    print(f"アクセス先URL (ページ{page}): {url}\n")
    
    try:
        r = requests.get(url)
        r.raise_for_status()
        soup = BeautifulSoup(r.content, 'html.parser')
        r.close()
        
        # デバッグモードの場合はページング構造を分析
        if debug:
            analyze_pagination_structure(soup, debug=True)
        
        xbrl_record_list = []
        
        # メインテーブルの全行を取得
        tr_elms = soup.select('table#main-list-table > tr')
        if debug or not debug:  # 常に表示
            print(f"テーブル内の総行数: {len(tr_elms)}")
        
        for tr_elm in tr_elms:
            # 各項目を初期化
            kj_time_str = None
            kj_code_str = None
            kj_name_str = None
            kj_title_str = None
            pdf_url_str = None
            xbrl_url_str = None
            kj_place_str = None
            kj_history_str = None
            
            # 各セルを処理
            td_elms = tr_elm.select('td')
            for td_elm in td_elms:
                class_list = td_elm.get("class", [])
                
                if 'kjTime' in class_list:
                    kj_time_str = td_elm.get_text().strip()
                    
                elif 'kjCode' in class_list:
                    kj_code_str = td_elm.get_text().strip()
                    
                elif 'kjName' in class_list:
                    kj_name_str = td_elm.get_text().strip()
                    
                elif 'kjPlace' in class_list:
                    kj_place_str = td_elm.get_text().strip()
                    
                elif 'kjHistroy' in class_list:
                    kj_history_str = td_elm.get_text().strip()
                    
                elif 'kjTitle' in class_list:
                    a_elm = td_elm.select_one('a')
                    if a_elm:
                        kj_title_str = a_elm.get_text().strip()
                        pdf_name_str = a_elm.get("href")
                        pdf_url_str = urllib.parse.urljoin('https://www.release.tdnet.info/inbs/', pdf_name_str)
                        
                elif 'kjXbrl' in class_list:
                    a_elm = td_elm.select_one('a')
                    if a_elm is not None:
                        xbrl_name_str = a_elm.get("href")
                        xbrl_url_str = urllib.parse.urljoin('https://www.release.tdnet.info/inbs/', xbrl_name_str)
            
            # XBRLリンクがある場合のみ記録
            if xbrl_url_str:
                record = {
                    'time': kj_time_str,
                    'code': kj_code_str,
                    'name': kj_name_str,
                    'title': kj_title_str,
                    'pdf_url': pdf_url_str,
                    'xbrl_url': xbrl_url_str,
                    'place': kj_place_str,
                    'history': kj_history_str
                }
                xbrl_record_list.append(record)
        
        return xbrl_record_list
        
    except requests.exceptions.RequestException as e:
        print(f"❌ エラー: {e}")
        return []


def download_xbrl_file(url, save_dir="downloads", company_name="", code=""):
    """
    XBRLファイル（ZIP）をダウンロード
    
    Args:
        url: XBRLファイルのURL
        save_dir: 保存先ディレクトリ
        company_name: 会社名（ファイル名用）
        code: 証券コード（ファイル名用）
    
    Returns:
        保存されたファイルパス（成功時）、None（失敗時）
    """
    
    # 保存先ディレクトリを作成
    save_path = Path(save_dir)
    save_path.mkdir(parents=True, exist_ok=True)
    
    # ファイル名を生成
    original_filename = os.path.basename(url)
    
    # 会社名と証券コードを使ってわかりやすいファイル名を作成
    if company_name and code:
        # 会社名から使用できない文字を除去
        safe_name = "".join(c for c in company_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        filename = f"{code}_{safe_name}_{original_filename}"
    else:
        filename = original_filename
    
    file_path = save_path / filename
    
    try:
        print(f"ダウンロード中: {url}")
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        # ファイルを保存
        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        print(f"  ✅ 保存完了: {file_path}")
        
        # ZIPファイルを解凍
        if str(file_path).endswith('.zip'):
            extract_dir = save_path / f"{code}_{safe_name}" if company_name and code else save_path / original_filename.replace('.zip', '')
            extract_dir.mkdir(parents=True, exist_ok=True)
            
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
                print(f"  ✅ 解凍完了: {extract_dir}")
                
                # 解凍されたファイルをリスト表示
                extracted_files = list(extract_dir.glob('*'))
                print(f"  解凍されたファイル数: {len(extracted_files)}")
                for file in extracted_files[:5]:  # 最初の5ファイルを表示
                    print(f"    - {file.name}")
        
        return file_path
        
    except requests.exceptions.RequestException as e:
        print(f"  ❌ ダウンロードエラー: {e}")
        return None
    except zipfile.BadZipFile as e:
        print(f"  ❌ ZIP解凍エラー: {e}")
        return file_path  # ZIPファイル自体は保存されている


def filter_records(records, filter_type="all"):
    """
    レコードをフィルタリング
    
    Args:
        records: XBRLレコードのリスト
        filter_type: フィルタータイプ（all, kessan, gyoseki）
    
    Returns:
        フィルタリングされたレコードのリスト
    """
    
    if filter_type == "all":
        return records
    elif filter_type == "kessan":
        # 決算短信を含むが、訂正版・修正版は除外
        filtered_records = []
        for r in records:
            title = r['title']
            # 決算短信を含むかチェック
            if '決算短信' in title:
                # REITを除外
                if 'ＲＥＩＴ' in title or 'リート' in title or 'REIT' in title:
                    print(f"  除外: {r['name']} - {title} (REIT)")
                    continue
                    
                # 訂正版・修正版を除外
                exclude_keywords = [
                    '訂正', '修正', 'データ訂正', '数値データ訂正',
                    '一部訂正', '内容訂正', '記載内容訂正'
                ]
                
                # 除外キーワードが含まれていないかチェック
                if not any(keyword in title for keyword in exclude_keywords):
                    filtered_records.append(r)
                else:
                    print(f"  除外: {r['name']} - {title}")
        
        return filtered_records
    elif filter_type == "gyoseki":
        return [r for r in records if '業績予想' in r['title'] or '業績の修正' in r['title']]
    else:
        return records



def extract_financial_data(xbrl_file_path: str) -> Dict[str, Union[str, int, float, Dict]]:
    """
    XBRLファイルから財務データを抽出（従来版・互換性維持）
    
    Args:
        xbrl_file_path: XBRLファイルのパス
    
    Returns:
        財務データの辞書
    """
    
    try:
        with open(xbrl_file_path, 'r', encoding='utf-8') as f:
            soup = BeautifulSoup(f.read(), 'html.parser')
        
        financial_data = {
            'company_info': {},
            'income_statement': {},
            'balance_sheet': {},
            'metadata': {}
        }
        
        # 基本情報の抽出
        financial_data['company_info'] = _extract_company_info(soup)
        
        # 損益計算書データの抽出
        financial_data['income_statement'] = _extract_income_statement(soup)
        
        # 貸借対照表データの抽出
        financial_data['balance_sheet'] = _extract_balance_sheet(soup)
        
        # メタデータの設定
        financial_data['metadata'] = {
            'extraction_date': datetime.now().isoformat(),
            'source_file': xbrl_file_path,
            'currency': 'JPY',
            'unit': '百万円'
        }
        
        return financial_data
        
    except Exception as e:
        print(f"❌ XBRL解析エラー: {e}")
        return {}


def _extract_company_info(soup: BeautifulSoup) -> Dict[str, str]:
    """企業基本情報を抽出"""
    
    company_info = {}
    
    try:
        # 会社名（名前空間なしで検索）
        company_name = soup.find(attrs={'name': 'tse-ed-t:CompanyName'})
        if company_name:
            company_info['company_name'] = company_name.get_text().strip()
        
        # 証券コード
        securities_code = soup.find(attrs={'name': 'tse-ed-t:SecuritiesCode'})
        if securities_code:
            text = securities_code.get_text().strip()
            # 改行や見えないdivを除去
            import re
            text = re.sub(r'\s+', '', text)
            company_info['securities_code'] = text
        
        # 提出日
        filing_date = soup.find(attrs={'name': 'tse-ed-t:FilingDate'})
        if filing_date:
            raw_date = filing_date.get_text().strip()
            company_info['filing_date'] = _format_date_to_iso(raw_date)
        
        # 決算期
        document_name = soup.find(attrs={'name': 'tse-ed-t:DocumentName'})
        if document_name:
            company_info['document_name'] = document_name.get_text().strip()
            
    except Exception as e:
        print(f"⚠️ 企業情報抽出エラー: {e}")
    
    return company_info


def _extract_income_statement(soup: BeautifulSoup) -> Dict[str, Dict[str, float]]:
    """損益計算書データを抽出"""
    
    income_data = {
        'current_year': {},
        'prior_year': {}
    }
    
    # 抽出する項目の定義
    income_items = {
        'net_sales': 'tse-ed-t:NetSales',
        'operating_income': 'tse-ed-t:OperatingIncome', 
        'ordinary_income': 'tse-ed-t:OrdinaryIncome',
        'profit_attributable_to_owners': 'tse-ed-t:ProfitAttributableToOwnersOfParent',
        'comprehensive_income': 'tse-ed-t:ComprehensiveIncome'
    }
    
    try:
        for item_key, xbrl_tag in income_items.items():
            # 当期データ
            current_elem = soup.find(attrs={'name': xbrl_tag, 'contextref': 'CurrentYearDuration_ConsolidatedMember_ResultMember'})
            if current_elem:
                value = _parse_financial_value(current_elem)
                if value is not None:
                    income_data['current_year'][item_key] = value
            
            # 前期データ
            prior_elem = soup.find(attrs={'name': xbrl_tag, 'contextref': 'PriorYearDuration_ConsolidatedMember_ResultMember'})
            if prior_elem:
                value = _parse_financial_value(prior_elem)
                if value is not None:
                    income_data['prior_year'][item_key] = value
                    
    except Exception as e:
        print(f"⚠️ 損益計算書抽出エラー: {e}")
    
    return income_data


def _extract_balance_sheet(soup: BeautifulSoup) -> Dict[str, Dict[str, float]]:
    """貸借対照表データを抽出"""
    
    balance_data = {
        'current_year': {},
        'prior_year': {}
    }
    
    # 抽出する項目の定義（決算短信から直接取得可能な項目）
    balance_items = {
        'total_assets': 'tse-ed-t:TotalAssets',
        'net_assets': 'tse-ed-t:NetAssets', 
        'owners_equity': 'tse-ed-t:OwnersEquity'
    }
    
    try:
        for item_key, xbrl_tag in balance_items.items():
            # 当期末データ
            current_elem = soup.find(attrs={'name': xbrl_tag, 'contextref': 'CurrentYearInstant_ConsolidatedMember_ResultMember'})
            if current_elem:
                value = _parse_financial_value(current_elem)
                if value is not None:
                    balance_data['current_year'][item_key] = value
            
            # 前期末データ
            prior_elem = soup.find(attrs={'name': xbrl_tag, 'contextref': 'PriorYearInstant_ConsolidatedMember_ResultMember'})
            if prior_elem:
                value = _parse_financial_value(prior_elem)
                if value is not None:
                    balance_data['prior_year'][item_key] = value
                    
    except Exception as e:
        print(f"⚠️ 貸借対照表抽出エラー: {e}")
    
    return balance_data


def _format_date_to_iso(date_str: str) -> str:
    """
    様々な形式の日付文字列をyyyy-mm-dd形式に変換
    
    Args:
        date_str: 日付文字列（例：「2025年8月19日」「2025-08-19」「20250819」）
    
    Returns:
        yyyy-mm-dd形式の文字列
    """
    import unicodedata
    import re
    
    if not date_str:
        return ''
    
    # Unicode正規化で全角・半角文字を統一（NFKC形式）
    normalized_str = unicodedata.normalize('NFKC', date_str.strip())
    
    # 既にyyyy-mm-dd形式の場合はそのまま返す
    if len(normalized_str) == 10 and normalized_str.count('-') == 2:
        return normalized_str
    
    # YYYYMMDD形式の場合
    if len(normalized_str) == 8 and normalized_str.isdigit():
        return f"{normalized_str[:4]}-{normalized_str[4:6]}-{normalized_str[6:8]}"
    
    # 日本語形式の日付を処理（例：「2025年8月19日」）
    # 正規化後の文字列で再パターンマッチ
    japanese_date_match = re.match(r'(\d{4})年(\d{1,2})月(\d{1,2})日', normalized_str)
    if japanese_date_match:
        year, month, day = japanese_date_match.groups()
        return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
    
    # その他の形式も試行
    try:
        from datetime import datetime
        # 複数の日付形式を試す
        formats = ['%Y/%m/%d', '%Y.%m.%d', '%Y-%m-%d', '%m/%d/%Y']
        for fmt in formats:
            try:
                dt = datetime.strptime(normalized_str, fmt)
                return dt.strftime('%Y-%m-%d')
            except ValueError:
                continue
    except:
        pass
    
    # 変換できない場合は正規化された文字列を返す
    return normalized_str

def _extract_comprehensive_company_info(soup: BeautifulSoup) -> Dict[str, str]:
    """企業基本情報を包括的に抽出（複数タクソノミ対応）"""
    
    company_data = {}
    
    # 複数タクソノミに対応した企業情報項目の定義
    company_item_mappings = [
        # 一般事業会社（日本基準・IFRS）
        {
            'company_name': ['tse-ed-t:CompanyName'],
            'securities_code': ['tse-ed-t:SecuritiesCode'],
            'document_name': ['tse-ed-t:DocumentName'],
            'representative_title': ['tse-ed-t:TitleRepresentative'],
            'representative_name': ['tse-ed-t:NameRepresentative'],
            'inquiries_title': ['tse-ed-t:TitleInquiries'],
            'inquiries_name': ['tse-ed-t:NameInquiries'],
            'tel': ['tse-ed-t:Tel'],
            'url': ['tse-ed-t:URL']
        },
        # REIT（不動産投資信託）
        {
            'company_name': ['tse-re-t:IssuerNameREIT'],
            'securities_code': ['tse-re-t:SecuritiesCode'],
            'document_name': ['tse-re-t:DocumentName'],
            'representative_title': ['tse-re-t:TitleRepresentative'],
            'representative_name': ['tse-re-t:NameRepresentative'],
            'inquiries_title': ['tse-re-t:TitleInquiries'],
            'inquiries_name': ['tse-re-t:NameInquiries'],
            'tel': ['tse-re-t:Tel'],
            'url': ['tse-re-t:URL']
        }
    ]
    
    try:
        # 各タクソノミを順番に試す
        for mapping in company_item_mappings:
            found_data = False
            temp_data = {}
            
            for key, xbrl_tags in mapping.items():
                for xbrl_tag in xbrl_tags:
                    elem = soup.find(attrs={'name': xbrl_tag})
                    if elem:
                        value = elem.get_text().strip()
                        if key == 'securities_code':
                            import re
                            value = re.sub(r'\s+', '', value)
                        temp_data[key] = value
                        found_data = True
                        break
                
                # データが見つからない場合は空文字を設定
                if key not in temp_data:
                    temp_data[key] = ''
            
            # いずれかのタクソノミでデータが見つかった場合は採用
            if found_data:
                company_data = temp_data
                break
        
        # どのタクソノミでもデータが見つからない場合
        if not company_data:
            for key in ['company_name', 'securities_code', 'document_name', 
                       'representative_title', 'representative_name', 
                       'inquiries_title', 'inquiries_name', 'tel', 'url']:
                company_data[key] = ''
                
    except Exception as e:
        print(f"⚠️ 企業情報抽出エラー: {e}")
    
    return company_data


def _extract_comprehensive_income_statement(soup: BeautifulSoup) -> Dict[str, float]:
    """損益計算書を包括的に抽出"""
    
    income_data = {}
    
    # 損益計算書項目の定義
    income_items = {
        'net_sales_current': ('tse-ed-t:NetSales', 'CurrentYearDuration_ConsolidatedMember_ResultMember'),
        'net_sales_prior': ('tse-ed-t:NetSales', 'PriorYearDuration_ConsolidatedMember_ResultMember'),
        'operating_income_current': ('tse-ed-t:OperatingIncome', 'CurrentYearDuration_ConsolidatedMember_ResultMember'),
        'operating_income_prior': ('tse-ed-t:OperatingIncome', 'PriorYearDuration_ConsolidatedMember_ResultMember'),
        'ordinary_income_current': ('tse-ed-t:OrdinaryIncome', 'CurrentYearDuration_ConsolidatedMember_ResultMember'),
        'ordinary_income_prior': ('tse-ed-t:OrdinaryIncome', 'PriorYearDuration_ConsolidatedMember_ResultMember'),
        'profit_attributable_to_owners_current': ('tse-ed-t:ProfitAttributableToOwnersOfParent', 'CurrentYearDuration_ConsolidatedMember_ResultMember'),
        'profit_attributable_to_owners_prior': ('tse-ed-t:ProfitAttributableToOwnersOfParent', 'PriorYearDuration_ConsolidatedMember_ResultMember'),
        'comprehensive_income_current': ('tse-ed-t:ComprehensiveIncome', 'CurrentYearDuration_ConsolidatedMember_ResultMember'),
        'comprehensive_income_prior': ('tse-ed-t:ComprehensiveIncome', 'PriorYearDuration_ConsolidatedMember_ResultMember'),
        'investment_profit_loss_current': ('tse-ed-t:InvestmentProfitLossOnEquityMethod', 'CurrentYearDuration_ConsolidatedMember_ResultMember'),
        'investment_profit_loss_prior': ('tse-ed-t:InvestmentProfitLossOnEquityMethod', 'PriorYearDuration_ConsolidatedMember_ResultMember')
    }
    
    try:
        for key, (xbrl_tag, context) in income_items.items():
            elem = soup.find(attrs={'name': xbrl_tag, 'contextref': context})
            if elem:
                value = _parse_financial_value(elem)
                if value is not None:
                    income_data[key] = value
                # 値が存在しない場合は辞書に追加しない（CSV出力時に除外される）
            # 要素が存在しない場合も辞書に追加しない
                
    except Exception as e:
        print(f"⚠️ 損益計算書抽出エラー: {e}")
    
    return income_data


def _extract_comprehensive_balance_sheet(soup: BeautifulSoup) -> Dict[str, float]:
    """貸借対照表を包括的に抽出"""
    
    balance_data = {}
    
    # 貸借対照表項目の定義
    balance_items = {
        'total_assets_current': ('tse-ed-t:TotalAssets', 'CurrentYearInstant_ConsolidatedMember_ResultMember'),
        'total_assets_prior': ('tse-ed-t:TotalAssets', 'PriorYearInstant_ConsolidatedMember_ResultMember'),
        'net_assets_current': ('tse-ed-t:NetAssets', 'CurrentYearInstant_ConsolidatedMember_ResultMember'),
        'net_assets_prior': ('tse-ed-t:NetAssets', 'PriorYearInstant_ConsolidatedMember_ResultMember'),
        'owners_equity_current': ('tse-ed-t:OwnersEquity', 'CurrentYearInstant_ConsolidatedMember_ResultMember'),
        'owners_equity_prior': ('tse-ed-t:OwnersEquity', 'PriorYearInstant_ConsolidatedMember_ResultMember')
    }
    
    try:
        for key, (xbrl_tag, context) in balance_items.items():
            elem = soup.find(attrs={'name': xbrl_tag, 'contextref': context})
            if elem:
                value = _parse_financial_value(elem)
                if value is not None:
                    balance_data[key] = value
                # 値が存在しない場合は辞書に追加しない（CSV出力時に除外される）
            # 要素が存在しない場合も辞書に追加しない
                
    except Exception as e:
        print(f"⚠️ 貸借対照表抽出エラー: {e}")
    
    return balance_data


def _extract_cash_flow_data(soup: BeautifulSoup) -> Dict[str, float]:
    """キャッシュフローデータを抽出"""
    
    cf_data = {}
    
    # キャッシュフロー項目の定義
    cf_items = {
        'operating_cash_flow_current': ('tse-ed-t:CashFlowsFromOperatingActivities', 'CurrentYearDuration_ConsolidatedMember_ResultMember'),
        'operating_cash_flow_prior': ('tse-ed-t:CashFlowsFromOperatingActivities', 'PriorYearDuration_ConsolidatedMember_ResultMember'),
        'investing_cash_flow_current': ('tse-ed-t:CashFlowsFromInvestingActivities', 'CurrentYearDuration_ConsolidatedMember_ResultMember'),
        'investing_cash_flow_prior': ('tse-ed-t:CashFlowsFromInvestingActivities', 'PriorYearDuration_ConsolidatedMember_ResultMember'),
        'financing_cash_flow_current': ('tse-ed-t:CashFlowsFromFinancingActivities', 'CurrentYearDuration_ConsolidatedMember_ResultMember'),
        'financing_cash_flow_prior': ('tse-ed-t:CashFlowsFromFinancingActivities', 'PriorYearDuration_ConsolidatedMember_ResultMember'),
        'cash_and_equivalents_current': ('tse-ed-t:CashAndEquivalentsEndOfPeriod', 'CurrentYearInstant_ConsolidatedMember_ResultMember'),
        'cash_and_equivalents_prior': ('tse-ed-t:CashAndEquivalentsEndOfPeriod', 'PriorYearInstant_ConsolidatedMember_ResultMember')
    }
    
    try:
        for key, (xbrl_tag, context) in cf_items.items():
            elem = soup.find(attrs={'name': xbrl_tag, 'contextref': context})
            if elem:
                value = _parse_financial_value(elem)
                if value is not None:
                    cf_data[key] = value
                # 値が存在しない場合は辞書に追加しない（CSV出力時に除外される）
            # 要素が存在しない場合も辞書に追加しない
                
    except Exception as e:
        print(f"⚠️ キャッシュフロー抽出エラー: {e}")
    
    return cf_data


def _extract_ratios_and_indicators(soup: BeautifulSoup) -> Dict[str, float]:
    """比率・指標データを抽出"""
    
    ratio_data = {}
    
    # 比率・指標項目の定義
    ratio_items = {
        'eps_current': ('tse-ed-t:NetIncomePerShare', 'CurrentYearDuration_ConsolidatedMember_ResultMember'),
        'eps_prior': ('tse-ed-t:NetIncomePerShare', 'PriorYearDuration_ConsolidatedMember_ResultMember'),
        'bps_current': ('tse-ed-t:NetAssetsPerShare', 'CurrentYearInstant_ConsolidatedMember_ResultMember'),
        'bps_prior': ('tse-ed-t:NetAssetsPerShare', 'PriorYearInstant_ConsolidatedMember_ResultMember'),
        'roe_current': ('tse-ed-t:NetIncomeToShareholdersEquityRatio', 'CurrentYearDuration_ConsolidatedMember_ResultMember'),
        'roe_prior': ('tse-ed-t:NetIncomeToShareholdersEquityRatio', 'PriorYearDuration_ConsolidatedMember_ResultMember'),
        'roa_current': ('tse-ed-t:OrdinaryIncomeToTotalAssetsRatio', 'CurrentYearDuration_ConsolidatedMember_ResultMember'),
        'roa_prior': ('tse-ed-t:OrdinaryIncomeToTotalAssetsRatio', 'PriorYearDuration_ConsolidatedMember_ResultMember'),
        'operating_margin_current': ('tse-ed-t:OperatingIncomeToNetSalesRatio', 'CurrentYearDuration_ConsolidatedMember_ResultMember'),
        'operating_margin_prior': ('tse-ed-t:OperatingIncomeToNetSalesRatio', 'PriorYearDuration_ConsolidatedMember_ResultMember'),
        'equity_ratio_current': ('tse-ed-t:CapitalAdequacyRatio', 'CurrentYearInstant_ConsolidatedMember_ResultMember'),
        'equity_ratio_prior': ('tse-ed-t:CapitalAdequacyRatio', 'PriorYearInstant_ConsolidatedMember_ResultMember'),
        'payout_ratio_current': ('tse-ed-t:PayoutRatio', 'CurrentYearDuration_ConsolidatedMember_ResultMember'),
        'average_shares_current': ('tse-ed-t:AverageNumberOfShares', 'CurrentYearDuration_ConsolidatedMember_ResultMember'),
        'issued_shares_current': ('tse-ed-t:NumberOfIssuedAndOutstandingSharesAtTheEndOfFiscalYearIncludingTreasuryStock', 'CurrentYearInstant_ConsolidatedMember_ResultMember')
    }
    
    try:
        for key, (xbrl_tag, context) in ratio_items.items():
            elem = soup.find(attrs={'name': xbrl_tag, 'contextref': context})
            if elem:
                value = _parse_financial_value(elem)
                if value is not None:
                    ratio_data[key] = value
                # 値が存在しない場合は辞書に追加しない（CSV出力時に除外される）
            # 要素が存在しない場合も辞書に追加しない
                
    except Exception as e:
        print(f"⚠️ 比率・指標抽出エラー: {e}")
    
    return ratio_data


def _extract_dividend_and_share_info(soup: BeautifulSoup) -> Dict[str, Union[float, str]]:
    """配当・株式情報を抽出"""
    
    dividend_data = {}
    
    # 配当・株式項目の定義
    dividend_items = {
        'dividend_per_share_current': ('tse-ed-t:DividendPerShare', 'CurrentYearDuration_ConsolidatedMember_ResultMember'),
        'total_dividend_current': ('tse-ed-t:TotalDividendPaidAnnual', 'CurrentYearDuration_ConsolidatedMember_ResultMember'),
        'shareholder_meeting_date': ('tse-ed-t:DateOfGeneralShareholdersMeetingAsPlanned', 'CurrentYearInstant'),
        'dividend_payment_date': ('tse-ed-t:DividendPayableDateAsPlanned', 'CurrentYearInstant'),
        'securities_report_date': ('tse-ed-t:AnnualSecuritiesReportFilingDateAsPlanned', 'CurrentYearInstant')
    }
    
    try:
        for key, (xbrl_tag, context) in dividend_items.items():
            elem = soup.find(attrs={'name': xbrl_tag, 'contextref': context})
            if elem:
                if 'date' in key:
                    raw_date = elem.get_text().strip()
                    dividend_data[key] = _format_date_to_iso(raw_date)
                else:
                    value = _parse_financial_value(elem)
                    if value is not None:
                        dividend_data[key] = value
                    # 値が存在しない場合は辞書に追加しない（CSV出力時に除外される）
            # 要素が存在しない場合も辞書に追加しない
                
    except Exception as e:
        print(f"⚠️ 配当・株式情報抽出エラー: {e}")
    
    return dividend_data


def _extract_other_important_items(soup: BeautifulSoup) -> Dict[str, Union[float, str]]:
    """その他重要項目を抽出"""
    
    other_data = {}
    
    # その他重要項目の定義
    other_items = {
        'fiscal_year_end': ('tse-ed-t:FiscalYearEnd', 'CurrentYearInstant'),
        'treasury_stock_count': ('tse-ed-t:NumberOfTreasuryStockAtTheEndOfFiscalYear', 'CurrentYearInstant_NonConsolidatedMember_ResultMember'),
        'new_subsidiaries_count': ('tse-ed-t:NumberOfSubsidiariesNewlyConsolidated', 'CurrentYearDuration_ConsolidatedMember_ResultMember'),
        'new_subsidiaries_names': ('tse-ed-t:NameOfSubsidiariesNewlyConsolidated', 'CurrentYearDuration_ConsolidatedMember_ResultMember')
    }
    
    try:
        for key, (xbrl_tag, context) in other_items.items():
            elem = soup.find(attrs={'name': xbrl_tag, 'contextref': context})
            if elem:
                if key in ['fiscal_year_end']:
                    raw_date = elem.get_text().strip()
                    other_data[key] = _format_date_to_iso(raw_date)
                elif key in ['new_subsidiaries_names']:
                    other_data[key] = elem.get_text().strip()
                else:
                    value = _parse_financial_value(elem)
                    if value is not None:
                        other_data[key] = value
                    # 値が存在しない場合は辞書に追加しない（CSV出力時に除外される）
            # 要素が存在しない場合も辞書に追加しない
                
    except Exception as e:
        print(f"⚠️ その他項目抽出エラー: {e}")
    
    return other_data


def _extract_detailed_financial_data(attachment_dir_path: str) -> Dict[str, float]:
    """詳細財務諸表データを抽出（Attachmentフォルダから）"""
    
    detailed_data = {}
    
    try:
        attachment_path = Path(attachment_dir_path)
        
        # 貸借対照表ファイルを探す（acbs01）
        bs_files = list(attachment_path.glob('*acbs01*ixbrl.htm'))
        
        if bs_files:
            with open(bs_files[0], 'r', encoding='utf-8') as f:
                soup = BeautifulSoup(f.read(), 'html.parser')
            
            # jppfs_cor名前空間の主要項目を抽出
            detailed_items = {
                'cash_and_deposits_current': ('jppfs_cor:CashAndDeposits', 'CurrentYearInstant'),
                'cash_and_deposits_prior': ('jppfs_cor:CashAndDeposits', 'Prior1YearInstant'),
                'accounts_receivable_current': ('jppfs_cor:NotesAndAccountsReceivableTradeAndContractAssets', 'CurrentYearInstant'),
                'accounts_receivable_prior': ('jppfs_cor:NotesAndAccountsReceivableTradeAndContractAssets', 'Prior1YearInstant'),
                'inventory_current': ('jppfs_cor:MerchandiseAndFinishedGoods', 'CurrentYearInstant'),
                'inventory_prior': ('jppfs_cor:MerchandiseAndFinishedGoods', 'Prior1YearInstant'),
                'work_in_process_current': ('jppfs_cor:WorkInProcess', 'CurrentYearInstant'),
                'work_in_process_prior': ('jppfs_cor:WorkInProcess', 'Prior1YearInstant'),
                'raw_materials_current': ('jppfs_cor:RawMaterialsAndSupplies', 'CurrentYearInstant'),
                'raw_materials_prior': ('jppfs_cor:RawMaterialsAndSupplies', 'Prior1YearInstant')
            }
            
            for key, (xbrl_tag, context) in detailed_items.items():
                elem = soup.find(attrs={'name': xbrl_tag, 'contextref': context})
                if elem:
                    value = _parse_financial_value(elem)
                    if value is not None:
                        detailed_data[key] = value
                    # 値が存在しない場合は辞書に追加しない（CSV出力時に除外される）
                # 要素が存在しない場合も辞書に追加しない
        
    except Exception as e:
        print(f"⚠️ 詳細財務データ抽出エラー: {e}")
    
    return detailed_data


def extract_comprehensive_financial_data(summary_file_path: str, attachment_dir_path: str = None) -> Dict[str, Union[str, float]]:
    """
    包括的な財務データを抽出（約130項目）
    
    Args:
        summary_file_path: Summaryファイルのパス
        attachment_dir_path: Attachmentディレクトリのパス
    
    Returns:
        包括的な財務データの辞書（dateフィールドが最左列）
    """
    
    comprehensive_data = {}
    
    try:
        # Summaryファイルを読み込み
        with open(summary_file_path, 'r', encoding='utf-8') as f:
            soup = BeautifulSoup(f.read(), 'html.parser')
        
        # 1. 日付情報（最優先で左端に配置）
        filing_date_elem = soup.find(attrs={'name': 'tse-ed-t:FilingDate'})
        if filing_date_elem:
            raw_date = filing_date_elem.get_text().strip()
            comprehensive_data['date'] = _format_date_to_iso(raw_date)
        else:
            comprehensive_data['date'] = ''
        
        # 2. 企業基本情報
        company_data = _extract_comprehensive_company_info(soup)
        comprehensive_data.update(company_data)
        
        # 3. 損益計算書データ
        income_data = _extract_comprehensive_income_statement(soup)
        comprehensive_data.update(income_data)
        
        # 4. 貸借対照表データ
        balance_data = _extract_comprehensive_balance_sheet(soup)
        comprehensive_data.update(balance_data)
        
        # 5. キャッシュフローデータ
        cf_data = _extract_cash_flow_data(soup)
        comprehensive_data.update(cf_data)
        
        # 6. 比率・指標データ
        ratio_data = _extract_ratios_and_indicators(soup)
        comprehensive_data.update(ratio_data)
        
        # 7. 配当・株式情報
        dividend_data = _extract_dividend_and_share_info(soup)
        comprehensive_data.update(dividend_data)
        
        # 8. その他重要項目
        other_data = _extract_other_important_items(soup)
        comprehensive_data.update(other_data)
        
        # 9. Summaryファイルから全tse-ed-t項目を自動抽出（新規追加）
        all_tse_items = _extract_all_tse_items(soup)
        # 既存のキーと重複しないものだけ追加
        for key, value in all_tse_items.items():
            if key not in comprehensive_data:
                comprehensive_data[key] = value
        
        # 10. 詳細財務データ（Attachmentから）
        if attachment_dir_path:
            detailed_data = _extract_detailed_financial_data(attachment_dir_path)
            comprehensive_data.update(detailed_data)
            
            # 11. Attachmentから全jppfs_cor項目を自動抽出（新規追加）
            all_jppfs_items = _extract_all_jppfs_items(attachment_dir_path)
            # 既存のキーと重複しないものだけ追加
            for key, value in all_jppfs_items.items():
                if key not in comprehensive_data:
                    comprehensive_data[key] = value
        
        return comprehensive_data
        
    except Exception as e:
        print(f"⚠️ 包括的データ抽出エラー: {e}")
        return {'date': ''}


def _parse_financial_value(element) -> Optional[float]:
    """XBRL要素から数値を解析"""
    
    try:
        # テキスト値を取得
        text_value = element.get_text().strip().replace(',', '')
        
        # ハイフンや空文字は除外
        if not text_value or text_value == '－' or text_value == '-':
            return None
        
        # サイン属性をチェック
        sign = element.get('sign', '')
        
        # 数値に変換
        value = float(text_value)
        
        # マイナス符号の処理
        if sign == '-':
            value = -value
            
        return value
            
    except (ValueError, AttributeError):
        # エラーは静かに処理（大量の項目があるため）
        pass
    
    return None


def _extract_all_tse_items(soup) -> Dict[str, Union[str, float]]:
    """Summaryファイルから全tse-ed-t項目を自動抽出"""
    import re
    
    tse_items = {}
    
    try:
        # tse-ed-t名前空間の全項目を取得
        for elem in soup.find_all(attrs={'name': re.compile(r'^tse-ed-t:')}):
            name = elem.get('name', '')
            if not name:
                continue
                
            # プレフィックスを除去してキー名を生成
            key = name.replace('tse-ed-t:', '')
            
            # コンテキストを確認
            context = elem.get('contextref', '')
            
            # コンテキストに基づいてサフィックスを追加
            if 'CurrentYear' in context:
                if 'Duration' in context:
                    key += '_current'
                elif 'Instant' in context:
                    key += '_currentyear'
            elif 'PriorYear' in context or 'Prior1Year' in context:
                if 'Duration' in context:
                    key += '_prior'
                elif 'Instant' in context:
                    key += '_prioryear'
            elif 'NextYear' in context:
                key += '_forecast'
            
            # 値を取得
            text_value = elem.get_text().strip()
            if not text_value:
                continue
            
            # 数値として解析を試みる
            value = _parse_financial_value(elem)
            if value is not None:
                tse_items[key] = value
            else:
                # 数値でない場合は文字列として保存（日付など）
                if text_value and text_value != '－':
                    # 日付形式の場合は変換
                    if '年' in text_value and '月' in text_value:
                        tse_items[key] = _format_date_to_iso(text_value)
                    else:
                        tse_items[key] = text_value
                        
    except Exception as e:
        print(f"⚠️ tse-ed-t項目の自動抽出エラー: {e}")
    
    return tse_items


def _extract_all_jppfs_items(attachment_dir_path: str) -> Dict[str, Union[str, float]]:
    """Attachmentフォルダから全jppfs_cor項目を自動抽出"""
    import re
    from pathlib import Path
    
    jppfs_items = {}
    
    try:
        attachment_path = Path(attachment_dir_path)
        
        # 全てのixbrl.htmファイルを処理
        for html_file in attachment_path.glob('*.htm'):
            with open(html_file, 'r', encoding='utf-8') as f:
                soup = BeautifulSoup(f.read(), 'html.parser')
            
            # jppfs_cor名前空間の全項目を取得
            for elem in soup.find_all(attrs={'name': re.compile(r'^jppfs_cor:')}):
                name = elem.get('name', '')
                if not name:
                    continue
                    
                # プレフィックスを除去してキー名を生成
                key = name.replace('jppfs_cor:', '')
                
                # コンテキストを確認
                context = elem.get('contextref', '')
                
                # コンテキストに基づいてサフィックスを追加
                if 'CurrentYearInstant' in context:
                    key += '_current'
                elif 'Prior1YearInstant' in context or 'PriorYearInstant' in context:
                    key += '_prior'
                elif 'CurrentYearDuration' in context:
                    key += '_duration_current'
                elif 'PriorYearDuration' in context:
                    key += '_duration_prior'
                
                # 既に存在するキーはスキップ
                if key in jppfs_items:
                    continue
                
                # 値を取得
                value = _parse_financial_value(elem)
                if value is not None:
                    jppfs_items[key] = value
                        
    except Exception as e:
        print(f"⚠️ jppfs_cor項目の自動抽出エラー: {e}")
    
    return jppfs_items


def extract_comprehensive_data_from_directory(directory_path: str) -> List[Dict[str, Union[str, float]]]:
    """
    XBRLディレクトリから包括的な財務データを抽出
    
    Args:
        directory_path: XBRLファイルがあるディレクトリのパス
    
    Returns:
        全企業の包括的財務データのリスト
    """
    
    all_financial_data = []
    directory = Path(directory_path)
    
    if not directory.exists():
        print(f"❌ ディレクトリが存在しません: {directory_path}")
        return []
    
    print(f"📁 XBRLディレクトリ包括解析開始: {directory_path}")
    print("="*60)
    
    for company_dir in directory.iterdir():
        if company_dir.is_dir():
            company_name = company_dir.name
            print(f"\n🏢 企業: {company_name}")
            
            # Summary フォルダを探す
            summary_dir = company_dir / 'XBRLData' / 'Summary'
            attachment_dir = company_dir / 'XBRLData' / 'Attachment'
            
            if summary_dir.exists():
                # ixbrl.htm ファイルを探す
                ixbrl_files = list(summary_dir.glob('*-ixbrl.htm'))
                
                if ixbrl_files:
                    ixbrl_file = ixbrl_files[0]
                    print(f"  📄 解析ファイル: {ixbrl_file.name}")
                    
                    # 包括的財務データを抽出
                    attachment_path = str(attachment_dir) if attachment_dir.exists() else None
                    comprehensive_data = extract_comprehensive_financial_data(str(ixbrl_file), attachment_path)
                    
                    if comprehensive_data and comprehensive_data.get('company_name'):
                        all_financial_data.append(comprehensive_data)
                        print(f"  ✅ データ抽出成功: {len(comprehensive_data)}項目")
                    else:
                        print(f"  ⚠️ データ抽出に失敗しました")
                else:
                    print(f"  ⚠️ ixbrl.htmファイルが見つかりません")
            else:
                print(f"  ⚠️ Summaryディレクトリが見つかりません")
    
    print(f"\n✅ 包括解析完了: {len(all_financial_data)}社のデータを抽出")
    return all_financial_data


def is_financial_item(key: str) -> bool:
    """
    財務項目かどうかを判定
    
    Args:
        key: 項目名
    
    Returns:
        財務項目の場合True
    """
    # 財務関連キーワード
    financial_keywords = [
        # 損益関連
        'Sales', 'sales', 'Revenue', 'revenue',
        'Income', 'income', 'Profit', 'profit',
        'Loss', 'loss', 'Expense', 'expense',
        'Cost', 'cost', 'Margin', 'margin',
        
        # 資産関連
        'Asset', 'asset', 'Cash', 'cash',
        'Deposit', 'deposit', 'Receivable', 'receivable',
        'Inventory', 'inventory', 'Property', 'property',
        'Equipment', 'equipment', 'Investment', 'investment',
        'Goodwill', 'goodwill',
        
        # 負債関連
        'Liability', 'liability', 'Payable', 'payable',
        'Debt', 'debt', 'Loan', 'loan',
        'Obligation', 'obligation', 'Provision', 'provision',
        
        # 純資産関連
        'Equity', 'equity', 'Capital', 'capital',
        'Surplus', 'surplus', 'Retained', 'retained',
        'Treasury', 'treasury',
        
        # キャッシュフロー関連
        'CashFlow', 'cashflow', 'CF', 'cf',
        'Operating', 'operating', 'Investing', 'investing',
        'Financing', 'financing',
        
        # 株式・配当関連
        'Share', 'share', 'Stock', 'stock',
        'Dividend', 'dividend', 'EPS', 'eps',
        'BPS', 'bps', 'DPS', 'dps',
        
        # 財務比率関連
        'Ratio', 'ratio', 'Rate', 'rate',
        'ROE', 'roe', 'ROA', 'roa', 'ROI', 'roi',
        'Adequacy', 'adequacy', 'Payout', 'payout',
        
        # その他財務項目
        'Depreciation', 'depreciation', 'Amortization', 'amortization',
        'Allowance', 'allowance', 'Accumulated', 'accumulated',
        'Deferred', 'deferred', 'Tax', 'tax',
        'Valuation', 'valuation', 'Comprehensive', 'comprehensive',
        'Attributable', 'attributable', 'Controlling', 'controlling',
        'Working', 'working', 'Fixed', 'fixed',
        'Current', 'current', 'Noncurrent', 'noncurrent',
        'Prior', 'prior', 'Previous', 'previous',
        'Quarter', 'quarter', 'Period', 'period',
        'Year', 'year', 'Annual', 'annual',
        'Fiscal', 'fiscal', 'Average', 'average',
        'Total', 'total', 'Net', 'net',
        'Gross', 'gross', 'Operating', 'operating',
        'Ordinary', 'ordinary', 'Extraordinary', 'extraordinary',
        'Special', 'special', 'Other', 'other',
        'Before', 'before', 'After', 'after',
        'Beginning', 'beginning', 'End', 'end',
        'Increase', 'increase', 'Decrease', 'decrease',
        'Change', 'change', 'Adjustment', 'adjustment',
        'Balance', 'balance', 'Amount', 'amount',
        'Number', 'number', 'Issued', 'issued',
        'Outstanding', 'outstanding', 'Consolidated', 'consolidated',
        'NonConsolidated', 'nonconsolidated', 'Segment', 'segment',
        'Business', 'business', 'Account', 'account',
        'Statement', 'statement', 'Result', 'result',
        'Forecast', 'forecast', 'Plan', 'plan',
        'Budget', 'budget', 'Actual', 'actual',
        'Member', 'member', 'Mark', 'mark'
    ]
    
    # 非財務項目（除外する項目）
    non_financial_keywords = [
        'CompanyName', 'company_name',
        'DocumentName', 'document_name',
        'FilingDate', 'filing_date', 'date',
        'SecuritiesCode', 'securities_code',
        'Tel', 'tel', 'URL', 'url',
        'Representative', 'representative',
        'Inquiries', 'inquiries',
        'Title', 'title', 'Name', 'name',
        'TokyoStockExchange', 'NagoyaStockExchange',
        'SapporoStockExchange', 'FukuokaStockExchange',
        'JapanSecuritiesDealersAssociation',
        'GeneralBusiness', 'SpecificBusiness',
        'FASF', 'fasf', 'Supplemental', 'supplemental',
        'Convening', 'convening', 'Briefing', 'briefing',
        'TargetAudience', 'WayOfGetting',
        'Note', 'note', 'Preamble', 'preamble',
        'AccountingPolicy', 'AccountingPolicies',
        'AccountingEstimate', 'AccountingEstimates',
        'Retrospective', 'retrospective',
        'Restatement', 'restatement',
        'SignificantChanges', 'significantchanges',
        'ApplyingOfSpecific', 'applyingofspecific',
        'ChangesBasedOnRevisions', 'changesbasedonrevisions',
        'ChangesOtherThan', 'changesotherthan',
        'NoteTo', 'noteto', 'SubsidiariesNewly', 'subsidiariesnewly',
        'SubsidiariesExcluded', 'subsidiariesexcluded',
        'NameOf', 'nameof', 'Fraction', 'fraction',
        'Processing', 'processing', 'Method', 'method'
    ]
    
    # キーを小文字に変換して比較
    key_lower = key.lower()
    
    # 非財務項目の場合はFalse
    for keyword in non_financial_keywords:
        if keyword.lower() in key_lower:
            return False
    
    # 財務項目の場合はTrue
    for keyword in financial_keywords:
        if keyword.lower() in key_lower:
            return True
    
    # どちらにも該当しない場合はFalse（保守的に除外）
    return False


def output_financial_data_to_csv(financial_data_list: List[Dict[str, Union[str, float]]], output_path: str, all_items: bool = False):
    """
    財務データを縦型フォーマット（date, securities_code, company_name, カテゴリ, データ）でCSVファイルに出力（UTF-8 BOM付き）
    
    Args:
        financial_data_list: 財務データのリスト
        output_path: 出力CSVファイルのパス
        all_items: 全項目を出力するかどうか（デフォルトはFalse = 財務項目のみ）
    """
    
    if not financial_data_list:
        print("❌ 出力するデータがありません")
        return
    
    try:
        # CSVファイルに出力（UTF-8 BOM付き）
        with open(output_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
            # 縦型フォーマットのヘッダー（銘柄識別用の列を追加）
            fieldnames = ['date', 'securities_code', 'company_name', 'カテゴリ', 'データ']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            # ヘッダーを書き込み
            writer.writeheader()
            
            total_rows = 0
            filtered_count = 0
            
            # 各企業のデータを処理
            for data in financial_data_list:
                date_value = data.get('date', '')
                securities_code = data.get('securities_code', '')
                company_name = data.get('company_name', '')
                
                # 除外する項目（既に列として表示するため）
                excluded_keys = ['date', 'securities_code', 'company_name']
                
                # 残りの項目をアルファベット順で出力
                remaining_keys = sorted([k for k in data.keys() 
                                       if k not in excluded_keys])
                
                for key in remaining_keys:
                    value = data[key]
                    if value != '':  # 空でない値のみ出力
                        # 財務項目のフィルタリング
                        if not all_items and not is_financial_item(key):
                            filtered_count += 1
                            continue
                            
                        writer.writerow({
                            'date': date_value,
                            'securities_code': securities_code,
                            'company_name': company_name,
                            'カテゴリ': key,
                            'データ': value
                        })
                        total_rows += 1
        
        print(f"📄 CSV出力完了: {output_path}（UTF-8 BOM付き）")
        print(f"   企業数: {len(financial_data_list)}社")
        print(f"   データ行数: {total_rows}行")
        if not all_items and filtered_count > 0:
            print(f"   除外された非財務項目: {filtered_count}行")
            print(f"   モード: 財務項目のみ（デフォルト）")
        else:
            print(f"   モード: 全項目")
        print(f"   フォーマット: 縦型（date, securities_code, company_name, カテゴリ, データ）")
        
    except Exception as e:
        print(f"❌ CSV出力エラー: {e}")


def analyze_xbrl_directory(directory_path: str, output_format: str = 'json') -> Dict[str, Dict]:
    """
    XBRLディレクトリ内の全ファイルを解析
    
    Args:
        directory_path: XBRLファイルがあるディレクトリのパス
        output_format: 出力形式 ('json', 'dict')
    
    Returns:
        解析結果の辞書
    """
    
    results = {}
    directory = Path(directory_path)
    
    if not directory.exists():
        print(f"❌ ディレクトリが存在しません: {directory_path}")
        return {}
    
    print(f"📁 XBRLディレクトリ解析開始: {directory_path}")
    print("="*60)
    
    # Summary フォルダの ixbrl.htm ファイルを優先的に解析
    for company_dir in directory.iterdir():
        if company_dir.is_dir():
            company_name = company_dir.name
            print(f"\n🏢 企業: {company_name}")
            
            # Summary フォルダを探す
            summary_dir = company_dir / 'XBRLData' / 'Summary'
            if summary_dir.exists():
                # ixbrl.htm ファイルを探す
                ixbrl_files = list(summary_dir.glob('*-ixbrl.htm'))
                
                if ixbrl_files:
                    ixbrl_file = ixbrl_files[0]  # 最初のファイルを使用
                    print(f"  📄 解析ファイル: {ixbrl_file.name}")
                    
                    # 財務データを抽出
                    financial_data = extract_financial_data(str(ixbrl_file))
                    
                    if financial_data:
                        results[company_name] = financial_data
                        
                        # 主要データの表示
                        _display_financial_summary(financial_data)
                    else:
                        print(f"  ⚠️ データ抽出に失敗しました")
                else:
                    print(f"  ⚠️ ixbrl.htmファイルが見つかりません")
            else:
                print(f"  ⚠️ Summaryディレクトリが見つかりません")
    
    print(f"\n✅ 解析完了: {len(results)}社のデータを抽出")
    
    return results


def _display_financial_summary(financial_data: Dict):
    """財務データのサマリーを表示"""
    
    try:
        company_info = financial_data.get('company_info', {})
        income_current = financial_data.get('income_statement', {}).get('current_year', {})
        balance_current = financial_data.get('balance_sheet', {}).get('current_year', {})
        
        print(f"  📊 主要財務データ:")
        
        # 損益計算書
        if income_current:
            print(f"    売上高: {income_current.get('net_sales', 'N/A')} 百万円")
            print(f"    営業利益: {income_current.get('operating_income', 'N/A')} 百万円")
            print(f"    当期純利益: {income_current.get('profit_attributable_to_owners', 'N/A')} 百万円")
        
        # 貸借対照表
        if balance_current:
            print(f"    総資産: {balance_current.get('total_assets', 'N/A')} 百万円")
            print(f"    現金及び預金: {balance_current.get('cash_and_deposits', 'N/A')} 百万円")
            
    except Exception as e:
        print(f"  ⚠️ サマリー表示エラー: {e}")


def parse_date(date_str):
    """
    日付文字列を解析してYYYYMMDD形式に変換
    
    Args:
        date_str: 様々な形式の日付文字列
    
    Returns:
        YYYYMMDD形式の文字列、またはNone
    """
    
    if not date_str:
        return None
    
    # 既にYYYYMMDD形式の場合
    if len(date_str) == 8 and date_str.isdigit():
        return date_str
    
    try:
        # 様々な形式を試す
        formats = [
            '%Y-%m-%d',    # 2025-08-19
            '%Y/%m/%d',    # 2025/08/19
            '%Y%m%d',      # 20250819
        ]
        
        for fmt in formats:
            try:
                date_obj = datetime.strptime(date_str, fmt)
                return date_obj.strftime('%Y%m%d')
            except ValueError:
                continue
                
        print(f"❌ 日付形式が不正です: {date_str}")
        return None
        
    except Exception as e:
        print(f"❌ 日付解析エラー: {e}")
        return None


def main():
    """メイン処理"""
    
    # コマンドライン引数の解析
    parser = argparse.ArgumentParser(
        description='TDnet XBRL ダウンローダー',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
使用例:
  %(prog)s                           # 今日の日付でXBRLリストを表示
  %(prog)s -d 2025-08-19            # 指定日のXBRLリストを表示
  %(prog)s -d 20250819 --download   # 指定日のXBRLファイルをダウンロード
  %(prog)s -d 20250819 --download --filter kessan  # 決算短信のみダウンロード
  %(prog)s -d 20250819 --extract-all  # 一括処理：ダウンロード→財務データ抽出→CSV出力→ファイル削除
  %(prog)s -d 20250819 --extract-all --filter kessan  # 決算短信のみ一括処理
  %(prog)s -d 20250819 --extract-all --output-csv results.csv  # CSV出力ファイル名指定
  %(prog)s -d 20250819 --extract-all --keep-files  # CSV出力後もXBRL/ZIPファイルを保持
        '''
    )
    
    parser.add_argument(
        '-d', '--date',
        help='対象日付 (YYYY-MM-DD, YYYY/MM/DD, または YYYYMMDD 形式)',
        default=None
    )
    
    parser.add_argument(
        '--download',
        action='store_true',
        help='XBRLファイルをダウンロードする'
    )
    
    parser.add_argument(
        '--filter',
        choices=['all', 'kessan', 'gyoseki'],
        default='all',
        help='フィルター条件 (all: 全て, kessan: 決算短信のみ, gyoseki: 業績予想のみ)'
    )
    
    parser.add_argument(
        '--limit',
        type=int,
        default=None,
        help='ダウンロード件数制限'
    )
    
    parser.add_argument(
        '--debug',
        action='store_true',
        help='ページング構造などの詳細情報を表示（開発・調査用）'
    )
    
    parser.add_argument(
        '--page',
        type=int,
        default=1,
        help='取得するページ番号（デバッグ用）'
    )
    
    parser.add_argument(
        '--check-duplicates',
        action='store_true',
        help='全ページの重複確認を実行（調査用）'
    )
    
    parser.add_argument(
        '--all-pages',
        action='store_true',
        help='全ページからXBRLデータを取得する'
    )
    
    parser.add_argument(
        '--analyze',
        action='store_true',
        help='ダウンロード済みXBRLファイルの財務データを解析する'
    )
    
    parser.add_argument(
        '--analyze-path',
        help='解析するXBRLディレクトリのパスを指定（デフォルト: xbrl_data/日付）'
    )
    
    parser.add_argument(
        '--output-json',
        help='解析結果をJSONファイルに出力するパス'
    )
    
    parser.add_argument(
        '--extract-all',
        action='store_true',
        help='一括処理：ダウンロード→包括財務データ抽出→CSV出力'
    )
    
    parser.add_argument(
        '--output-csv',
        help='CSV出力ファイルのパス（デフォルト: financial_data_YYYYMMDD.csv）'
    )
    
    parser.add_argument(
        '--keep-files',
        action='store_true',
        help='CSV出力後もXBRL/ZIPファイルを保持する（デフォルトは削除）'
    )
    
    parser.add_argument(
        '--all-items',
        action='store_true',
        help='全項目を出力（デフォルトは財務項目のみ）'
    )
    
    args = parser.parse_args()
    
    # 日付の処理
    if args.date:
        date_str = parse_date(args.date)
        if not date_str:
            sys.exit(1)
    else:
        # デフォルトは今日の日付
        date_str = datetime.now().strftime('%Y%m%d')
    
    print("="*60)
    print(f"TDnet XBRL ダウンローダー")
    print(f"日付: {date_str}")
    print(f"フィルター: {args.filter}")
    if args.extract_all:
        print("モード: 一括処理（ダウンロード→財務データ抽出→CSV出力）")
    elif args.download:
        print("モード: ダウンロード")
    else:
        print("モード: リスト表示のみ")
    print("="*60 + "\n")
    
    # 重複確認モード
    if args.check_duplicates:
        check_all_pages_duplicates(date_str, max_pages=15)
        return
    
    # 財務データ解析モード
    if args.analyze:
        analyze_path = args.analyze_path if args.analyze_path else f"xbrl_data/{date_str}"
        
        print("💰 XBRL財務データ解析モード")
        print(f"解析対象: {analyze_path}")
        print("="*60)
        
        # 財務データを解析
        analysis_results = analyze_xbrl_directory(analyze_path)
        
        # JSON出力
        if args.output_json and analysis_results:
            try:
                with open(args.output_json, 'w', encoding='utf-8') as f:
                    json.dump(analysis_results, f, ensure_ascii=False, indent=2)
                print(f"\n📄 解析結果をJSONファイルに出力: {args.output_json}")
            except Exception as e:
                print(f"❌ JSON出力エラー: {e}")
        
        return
    
    # XBRLデータを取得
    print("【ステップ1】XBRLリスト取得")
    print("-"*40)
    
    if args.all_pages:
        # 全ページ取得モード
        xbrl_records = fetch_all_pages_xbrl(date_str, debug=args.debug)
    else:
        # 単一ページ取得モード
        xbrl_records = fetch_xbrl_list(date_str, debug=args.debug, page=args.page)
    
    if not xbrl_records:
        print("❌ XBRLデータが取得できませんでした")
        return
    
    print(f"✅ {len(xbrl_records)}件のXBRLデータを取得\n")
    
    # フィルタリング
    filtered_records = filter_records(xbrl_records, args.filter)
    
    if not filtered_records:
        print(f"❌ フィルター条件「{args.filter}」に一致するデータがありませんでした")
        return
    
    print(f"【ステップ2】フィルタリング結果")
    print("-"*40)
    print(f"対象件数: {len(filtered_records)}件\n")
    
    # 結果表示
    print("【XBRLデータ一覧】")
    print("-"*60)
    for i, record in enumerate(filtered_records, 1):
        print(f"\n{i}. {record['name']} ({record['code']})")
        print(f"   タイトル: {record['title']}")
        print(f"   時刻: {record['time']}")
        print(f"   XBRL URL: {record['xbrl_url']}")
    
    # 一括処理モード
    if args.extract_all:
        print(f"\n{'='*60}")
        print(f"【一括処理実行】ダウンロード→財務データ抽出→CSV出力")
        print("-"*40)
        
        # 件数制限
        download_records = filtered_records
        if args.limit:
            download_records = filtered_records[:args.limit]
            print(f"制限: {args.limit}件")
        
        # 保存先ディレクトリ
        save_dir = f"xbrl_data/{date_str}"
        print(f"保存先: {save_dir}")
        print(f"処理件数: {len(download_records)}件\n")
        
        # ステップ1: ダウンロード
        print("【ステップ1】XBRLファイルダウンロード")
        print("-"*40)
        success_count = 0
        for i, record in enumerate(download_records, 1):
            print(f"\n[{i}/{len(download_records)}] {record['name']} ({record['code']})")
            
            result = download_xbrl_file(
                record['xbrl_url'],
                save_dir=save_dir,
                company_name=record['name'],
                code=record['code']
            )
            
            if result:
                success_count += 1
            
            # サーバーに負荷をかけないよう少し待機
            if i < len(download_records):
                time.sleep(1)
        
        print(f"\n✅ ダウンロード完了: {success_count}/{len(download_records)}件成功")
        
        # ステップ2: 包括的財務データ抽出
        print(f"\n【ステップ2】包括的財務データ抽出")
        print("-"*40)
        
        financial_data_list = extract_comprehensive_data_from_directory(save_dir)
        
        if not financial_data_list:
            print("❌ 財務データの抽出に失敗しました")
            return
        
        # ステップ3: CSV出力
        print(f"\n【ステップ3】CSV出力")
        print("-"*40)
        
        # CSV出力ファイル名の決定
        if args.output_csv:
            csv_output_path = args.output_csv
        else:
            csv_output_path = f"financial_data_{date_str}.csv"
        
        output_financial_data_to_csv(financial_data_list, csv_output_path, all_items=args.all_items)
        
        # ステップ4: XBRLファイル・ZIPファイルの削除（オプション）
        if not args.keep_files:
            print(f"\n【ステップ4】ファイルクリーンアップ")
            print("-"*40)
            
            # xbrl_dataディレクトリの削除
            import shutil
            try:
                if Path(save_dir).exists():
                    shutil.rmtree(save_dir)
                    print(f"🗑️ ダウンロードファイル削除完了: {save_dir}")
                else:
                    print(f"ℹ️ 削除対象ディレクトリが存在しません: {save_dir}")
            except Exception as e:
                print(f"⚠️ ファイル削除エラー: {e}")
        
        print("\n" + "="*60)
        print(f"🎉 一括処理完了!")
        print(f"   ダウンロード: {success_count}件")
        print(f"   財務データ抽出: {len(financial_data_list)}社")
        print(f"   CSV出力: {csv_output_path}")
        if not args.keep_files:
            print(f"   ファイルクリーンアップ: 完了")
        else:
            print(f"   ファイル保持: {save_dir}")
        print("="*60)
        
        return
    
    # ダウンロード処理
    elif args.download:
        print(f"\n{'='*60}")
        print(f"【ステップ3】ダウンロード実行")
        print("-"*40)
        
        # 件数制限
        download_records = filtered_records
        if args.limit:
            download_records = filtered_records[:args.limit]
            print(f"制限: {args.limit}件")
        
        # 保存先ディレクトリ
        save_dir = f"xbrl_data/{date_str}"
        print(f"保存先: {save_dir}")
        print(f"ダウンロード件数: {len(download_records)}件\n")
        
        success_count = 0
        for i, record in enumerate(download_records, 1):
            print(f"\n[{i}/{len(download_records)}] {record['name']} ({record['code']})")
            
            result = download_xbrl_file(
                record['xbrl_url'],
                save_dir=save_dir,
                company_name=record['name'],
                code=record['code']
            )
            
            if result:
                success_count += 1
            
            # サーバーに負荷をかけないよう少し待機
            if i < len(download_records):
                time.sleep(1)
        
        print("\n" + "="*60)
        print(f"ダウンロード完了: {success_count}/{len(download_records)}件成功")
        print("="*60)
    
    else:
        print(f"\n💡 ダウンロードするには --download オプションを追加してください")


if __name__ == "__main__":
    main()