# TDnet XBRL 財務データ一括取得システム

TDnet（適時開示情報伝達システム）から決算短信XBRLファイルを自動取得し、財務情報を抽出してCSV形式で出力する一括処理システムです。

## 概要

東京証券取引所のTDnetで公開されている企業の決算短信から、約130項目の財務データを自動的に抽出し、CSV形式で出力します。ダウンロードから財務データ抽出、CSV出力まで一括で行うことができ、処理後は不要なXBRL/ZIPファイルは自動削除されます。

## 主要機能

### ✅ 一括処理ワークフロー
- **ステップ1**: XBRLファイルの自動ダウンロード
- **ステップ2**: 包括的財務データ抽出（約130項目）
- **ステップ3**: CSV出力（UTF-8 BOM付き、文字化けなし）
- **ステップ4**: 自動ファイルクリーンアップ

### ✅ 高度なフィルタリング機能
- **決算短信のみ抽出**: 訂正版・修正版を自動除外
- **REIT自動除外**: REIT（不動産投資信託）を決算短信フィルターから除外
- **重複排除**: 同一XBRLファイルの重複を自動検出・排除
- **複数タクソノミ対応**: 一般事業会社中心の財務データ抽出

### ✅ 包括的財務データ抽出
- **企業基本情報**: 会社名、証券コード、提出日、決算期末日など
- **損益計算書**: 売上高、営業利益、経常利益、当期純利益など（当期・前期）
- **貸借対照表**: 総資産、純資産、自己資本など（当期末・前期末）
- **キャッシュフロー**: 営業CF、投資CF、財務CF、現金及び現金同等物
- **比率・指標**: ROE、ROA、EPS、BPS、配当性向など
- **配当・株式情報**: 配当金、株主総会日程、発行済株式数など
- **詳細財務諸表**: 現金預金、売上債権、棚卸資産、固定資産詳細など

### ✅ その他の機能
- **全ページ自動取得**: 100件制限を解除し、全ページから自動取得
- **日付フォーマット統一**: 全角・半角混在に対応したyyyy-mm-dd形式への自動変換
- **Unicode正規化**: 全角・半角文字の混在問題を自動解決
- **進捗表示**: リアルタイムでダウンロード・処理状況を表示
- **エラーハンドリング**: ネットワークエラーや形式エラーに対応
- **デバッグ機能**: ページング構造の詳細分析

## セットアップ

### 必要要件
- Python 3.12以上
- uv（Pythonパッケージマネージャー）

### インストール
```bash
# リポジトリのクローン
git clone [repository-url]
cd tdnet

# uvで依存関係をインストール
uv sync
```

## スクリプトの使い分け

### 🚀 tdnet_xbrl_downloader.py（推奨）
- **全機能対応**: ダウンロード、財務データ抽出、CSV出力、ファイル管理
- **高度な機能**: 全ページ取得、フィルタリング、一括処理
- **本格運用向け**: コマンドライン引数豊富、エラーハンドリング完備

### 📋 tdnet_xbrl_scraper.py（学習・参考用）
- **シンプル機能**: 単一ページからのXBRL一覧表示のみ
- **制限事項**: 100件制限、ダウンロード機能なし、財務データ抽出なし
- **用途**: コードの学習、TDnet APIの理解、基本動作確認

**⚠️ 注意**: 実際のデータ収集には `tdnet_xbrl_downloader.py` をご利用ください。

## 使い方

**💡 ヒント**: 以下の例はすべて `tdnet_xbrl_downloader.py` を使用します。`tdnet_xbrl_scraper.py` は学習・参考用の簡易版です。

### 🚀 一括処理（推奨）

#### 決算短信の一括処理
```bash
# 基本的な一括処理（ダウンロード→財務データ抽出→CSV出力→ファイル削除）
uv run python tdnet_xbrl_downloader.py --extract-all -d 2025-08-19 --filter kessan --all-pages

# CSV出力ファイル名を指定
uv run python tdnet_xbrl_downloader.py --extract-all -d 2025-08-19 --filter kessan --all-pages --output-csv results.csv

# XBRLファイルを保持したい場合
uv run python tdnet_xbrl_downloader.py --extract-all -d 2025-08-19 --filter kessan --all-pages --keep-files
```

### 📋 基本機能

#### 1. ヘルプの確認
```bash
uv run python tdnet_xbrl_downloader.py --help
```

#### 2. 指定日のXBRLリストを表示
```bash
# 今日の日付でリスト表示
uv run python tdnet_xbrl_downloader.py

# 指定日のリスト表示
uv run python tdnet_xbrl_downloader.py -d 2025-08-19

# 全ページからリスト取得
uv run python tdnet_xbrl_downloader.py -d 2025-08-19 --all-pages
```

#### 3. フィルタリング
```bash
# 決算短信のみ表示（訂正版は自動除外）
uv run python tdnet_xbrl_downloader.py -d 2025-08-19 --all-pages --filter kessan

# 業績予想の修正のみ表示
uv run python tdnet_xbrl_downloader.py -d 2025-08-19 --all-pages --filter gyoseki
```

#### 4. XBRLファイルのダウンロードのみ
```bash
# 基本的なダウンロード
uv run python tdnet_xbrl_downloader.py -d 2025-08-19 --download

# 全ページから決算短信をダウンロード
uv run python tdnet_xbrl_downloader.py -d 2025-08-19 --all-pages --filter kessan --download

# 件数制限付きダウンロード
uv run python tdnet_xbrl_downloader.py -d 2025-08-19 --all-pages --download --limit 10
```

### 🔧 デバッグ・調査機能
```bash
# ページング構造の詳細分析
uv run python tdnet_xbrl_downloader.py -d 2025-08-19 --debug

# 特定ページの確認
uv run python tdnet_xbrl_downloader.py -d 2025-08-19 --page 2

# 全ページの重複確認
uv run python tdnet_xbrl_downloader.py -d 2025-08-14 --check-duplicates
```

### コマンドライン引数一覧

| 引数 | 説明 | 例 |
|------|------|---|
| `-d, --date` | 対象日付 | `-d 2025-08-19` |
| `--extract-all` | 一括処理（ダウンロード→抽出→CSV出力） | `--extract-all` |
| `--output-csv` | CSV出力ファイル名 | `--output-csv results.csv` |
| `--keep-files` | CSV出力後もXBRL/ZIPファイルを保持 | `--keep-files` |
| `--download` | XBRLファイルをダウンロードのみ | `--download` |
| `--all-pages` | 全ページから取得 | `--all-pages` |
| `--filter` | フィルター条件 (all/kessan/gyoseki) | `--filter kessan` |
| `--limit` | ダウンロード件数制限 | `--limit 10` |
| `--analyze` | ダウンロード済みファイルの解析のみ | `--analyze` |
| `--page` | 特定ページ取得（デバッグ用） | `--page 2` |
| `--debug` | 詳細な調査情報を表示 | `--debug` |

## 出力データ仕様

### CSV出力形式
- **ファイル名**: `financial_data_YYYYMMDD.csv`（デフォルト）
- **エンコーディング**: UTF-8 BOM付き（Excel・Googleスプレッドシートで文字化けなし）
- **構造**: 1行1企業、当期・前期データを同行に展開
- **左端列**: 決算開示日（`date`フィールド、yyyy-mm-dd形式）
- **日付統一**: 全ての日付フィールドがyyyy-mm-dd形式で統一出力

### 取得データ項目（約130項目）

#### 企業基本情報
- 会社名、証券コード、提出日、決算期末日
- 代表者、問い合わせ先、電話番号、URL

#### 損益計算書（当期・前期）
- 売上高、営業利益、経常利益、当期純利益
- 包括利益、持分法投資損益

#### 貸借対照表（当期末・前期末）
- 総資産、純資産、自己資本
- 現金及び預金、売上債権、棚卸資産
- 固定資産、負債詳細

#### キャッシュフロー（当期・前期）
- 営業活動、投資活動、財務活動によるキャッシュフロー
- 現金及び現金同等物期末残高

#### 比率・指標
- ROE、ROA、EPS、BPS
- 営業利益率、自己資本比率、配当性向
- 発行済株式数、自己株式数

#### 配当・株式情報
- 1株当たり配当金、総配当額
- 株主総会予定日、配当支払予定日
- 有価証券報告書提出予定日

## ファイル構成

```
tdnet/
├── README.md                           # このファイル
├── pyproject.toml                      # プロジェクト設定
├── uv.lock                            # 依存関係ロックファイル
├── claude.md                          # 開発用設定ファイル
├── sow.md                             # プロジェクト仕様書
│
├── tdnet_xbrl_downloader.py           # メインスクリプト（全機能統合版）
├── tdnet_xbrl_scraper.py             # 参考用シンプルスクリプト（単一ページ表示のみ）
│
├── financial_data_YYYYMMDD.csv        # 財務データCSV出力
├── xbrl_available_items.csv           # 利用可能XBRL項目一覧
├── xbrl_detailed_items.csv           # 詳細XBRL項目一覧
│
└── xbrl_data/                         # 一時ダウンロードデータ保存先
    └── YYYYMMDD/                      # 日付ごとのフォルダ（処理後自動削除）
        ├── [証券コード]_[会社名]/       # 企業ごとのフォルダ
        │   └── XBRLData/
        │       ├── Summary/           # XBRL本体ファイル
        │       └── Attachment/        # 添付ファイル
        └── [証券コード]_[会社名]_[元ファイル名].zip
```

## 技術仕様

### フィルタリング仕様

| フィルター | 対象 | マッチ条件 | 除外条件 |
|-----------|------|-----------|---------|
| `all` | 全て | 制限なし | なし |
| `kessan` | 決算短信 | タイトルに「決算短信」を含む | 「訂正」「修正」「データ訂正」「ＲＥＩＴ」「リート」「REIT」を含む |
| `gyoseki` | 業績予想 | タイトルに「業績予想」または「業績の修正」を含む | なし |

### 対応タクソノミ

| タクソノミ | 名前空間 | 対象企業 | 決算短信フィルター |
|----------|----------|---------|---------------|
| 一般事業会社 | `tse-ed-t` | 日本基準・IFRS対応の一般事業会社 | ✅ 対象 |
| REIT | `tse-re-t` | 不動産投資信託 | ❌ 自動除外 |

### XBRLファイル形式

- **ファイル形式**: ZIP圧縮
- **解凍後の構造**:
  - `XBRLData/Summary/`: XBRL本体ファイル（.xml, .xsd, .htm）
  - `XBRLData/Attachment/`: 添付ファイル（詳細財務諸表）

### パフォーマンス

#### 実測値（2025年8月19日のテスト結果）
- **決算短信対象**: 1社（REIT 1社、訂正版2社を除外）
- **財務データ抽出**: 70項目/社
- **処理時間**: 約25秒（ダウンロード〜CSV出力完了）
- **出力CSV**: UTF-8 BOM付き、文字化けなし、日付統一（yyyy-mm-dd）

#### 負荷対策
- ページ間アクセスに**1秒の間隔**を設定
- **適切なUser-Agent**とHTTPヘッダー
- **タイムアウト設定**（10秒）
- **エラーハンドリング**による適切な停止

### 日付処理仕様

#### Unicode正規化対応
- **全角・半角混在対応**: `unicodedata.normalize('NFKC')`によりXBRLデータの文字を統一
- **日付形式統一**: 「２０２５年８月１９日」→「2025-08-19」への自動変換
- **対応パターン**: 
  - 全角数字・半角漢字: 「２０２５年8月１９日」
  - 半角数字・全角漢字: 「2025年８月19日」  
  - 混在パターン: 「２０２５年８月19日」
- **出力統一**: 全ての日付フィールドがyyyy-mm-dd形式で出力

## 実用的な使用例

### 日次の決算短信データ収集
```bash
# 平日の決算発表日に実行
uv run python tdnet_xbrl_downloader.py --extract-all -d $(date +%Y%m%d) --filter kessan --all-pages
```

### 特定期間のデータ一括収集
```bash
# 複数日のデータを順次取得
for date in 20250819 20250820 20250821; do
  uv run python tdnet_xbrl_downloader.py --extract-all -d $date --filter kessan --all-pages --output-csv financial_data_$date.csv
done
```

### 大量データの取得（例：決算集中日）
```bash
# 8月14日は1000件超のデータがある日
uv run python tdnet_xbrl_downloader.py --extract-all -d 2025-08-14 --filter kessan --all-pages
```

## トラブルシューティング

### よくある問題

1. **文字化け**
   ```
   → UTF-8 BOM付きで出力されるため、ExcelやGoogleスプレッドシートで正常表示
   ```

2. **404エラー**
   ```bash
   # 日付が存在しない場合（土日祝日等）
   uv run python tdnet_xbrl_downloader.py -d 2025-08-17  # 日曜日
   ```

3. **データが見つからない**
   ```bash
   # デバッグモードで詳細確認
   uv run python tdnet_xbrl_downloader.py -d 2025-08-19 --debug
   ```

4. **ダウンロード失敗**
   ```bash
   # 件数を制限して再試行
   uv run python tdnet_xbrl_downloader.py --extract-all -d 2025-08-19 --filter kessan --limit 5
   ```

5. **ディスク容量不足**
   ```bash
   # ファイル自動削除を有効にする（デフォルト）
   uv run python tdnet_xbrl_downloader.py --extract-all -d 2025-08-19 --filter kessan
   # → CSV出力後、XBRLファイルは自動削除される
   ```

## 開発の経緯

### 実装ステップ
1. **要件分析** - TDnetからXBRLファイル自動取得の要望
2. **ページ構造調査** - HTML構造、ページング、JavaScript分析
3. **基本機能実装** - 単一ページからのXBRL取得
4. **ページング対応** - 全ページ自動取得機能
5. **フィルタリング強化** - 決算短信、訂正版除外の絞り込み
6. **財務データ抽出** - 約130項目の包括的データ抽出機能
7. **CSV出力機能** - UTF-8 BOM付き、文字化け対策
8. **一括処理ワークフロー** - ダウンロード〜CSV出力の統合
9. **ファイルクリーンアップ** - 処理後の自動削除機能
10. **REIT除外機能** - 決算短信フィルターでREIT自動除外
11. **日付フォーマット統一** - Unicode正規化による全角・半角混在対応

### 技術的発見
- **kjXbrlクラス**によるXBRLリンク取得方法の確立
- **完全順次ページング**（重複なし）の確認
- **複数タクソノミ対応**（一般事業会社・REIT）
- **訂正版自動除外**のフィルタリングロジック
- **REIT自動除外**による一般事業会社中心の抽出
- **UTF-8 BOM付きCSV**による文字化け解決
- **Unicode正規化**による全角・半角混在文字の統一処理
- **日付フォーマット統一**によるyyyy-mm-dd形式での一貫出力

### 技術選定
- **BeautifulSoup4**: HTML/XML解析
- **requests**: HTTP通信
- **csv**: CSV出力（UTF-8 BOM対応）
- **unicodedata**: Unicode正規化（全角・半角統一）
- **pathlib**: ファイルパス操作
- **argparse**: コマンドライン引数処理
- **uv**: 高速なPythonパッケージ管理

## 注意事項

- **サーバー負荷軽減**: ページ間アクセスに適切な間隔を設けています
- **利用規約遵守**: 取得したデータの利用はTDnetの利用規約に従ってください
- **データ品質**: 訂正版・REITは自動除外されるため、一般事業会社の決算短信のみが対象です
- **日付形式**: 全ての日付データはyyyy-mm-dd形式で統一出力されます
- **ディスク容量**: 一時的にXBRLファイルをダウンロードするため、十分な容量を確保してください
- **ネットワーク環境**: 安定したインターネット接続が必要です

## 参考資料

- [TDnet 適時開示情報閲覧サービス](https://www.release.tdnet.info/inbs/I_main_00.html)
- [参考記事：TDnetからXBRLをダウンロードする方法](https://www.quwechan.com/entry/2024/02/23/180546)
- [XBRL形式について](https://www.xbrl-jp.org/)

## ライセンス

[ライセンス情報を記載]

## 貢献

バグ報告や機能要望は、Issueでお知らせください。

---