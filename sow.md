# プロジェクト移行作業引き継ぎ書（SOW）

## 概要
`tdnet`プロジェクトから`tdnet_downloader`プロジェクトへの移行作業の引き継ぎ書です。

## 完了済み作業

### 1. ファイル移行
以下のファイルを `/home/jptyf/workspace/tdnet` から `/home/jptyf/workspace/tdnet_downloader` にコピー完了：

- `.gitignore`
- `.python-version`
- `README.md`
- `claude.md`
- `pyproject.toml`
- `tdnet_xbrl_downloader.py`
- `uv.lock`
- `xbrl_available_items.csv`
- `xbrl_detailed_items.csv`

### 2. 除外されたファイル/ディレクトリ
以下は意図的に移行しませんでした：
- `.venv/` - `uv sync`で再作成可能
- `__pycache__/` - Python実行時に自動生成
- `xbrl_data/` - `tdnet_xbrl_downloader.py`で再ダウンロード可能

## 残りの作業（次の担当者が実行）

### 1. Gitリポジトリの初期化
```bash
cd /home/jptyf/workspace/tdnet_downloader
git add .
git commit -m "Initial commit: プロジェクト移行

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

### 2. GitHub連携（必要に応じて）
```bash
# GitHubリポジトリを作成後
git remote add origin <GitHubリポジトリURL>
git branch -M main
git push -u origin main
```

### 3. 開発環境の復旧
```bash
cd /home/jptyf/workspace/tdnet_downloader
uv sync  # 仮想環境と依存関係の復旧
```

### 4. データディレクトリの復旧（必要に応じて）
```bash
# XBRLデータを再ダウンロードする場合
python tdnet_xbrl_downloader.py
```

## 元のプロジェクトについて
- 元のプロジェクト `/home/jptyf/workspace/tdnet` は保持されています
- 必要に応じて削除してください

## 移行方式
- **新規リポジトリとして移行**を選択
- Git履歴は新規開始（過去の履歴は保持しない）
- GitHubに新規アップロード予定

## 注意事項
- `.venv`は再作成が必要です
- `xbrl_data`は再ダウンロードが必要です（時間がかかる可能性があります）
- 現在のディレクトリには空のGitリポジトリが存在しています

## 作業日時
移行作業日: 2025-08-31
担当者: Claude Code