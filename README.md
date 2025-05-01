# ウェブページ更新監視ツール

## 概要
このツールは指定したウェブページの更新を監視し、変更があった場合にメールで通知するアプリケーションです。GitHub Actionsを使用して定期的に実行され、更新の検出から通知までを自動化します。

## リポジトリ構成
```
├── .github/
│   └── workflows/
│       └── main.yml      # GitHub Actionsの設定ファイル
├── main.py              # メインのPythonスクリプト
├── requirements.txt     # Pythonの依存パッケージ
├── urls.txt            # 監視対象のURLリスト
├── last_hashes.json    # 前回のページ内容のハッシュ値
└── README.md           # このファイル
```

## 技術仕様
- プログラミング言語: Python 3.9
- 主要ライブラリ:
  - requests: ウェブページの取得
  - beautifulsoup4: HTMLの解析
  - python-dotenv: 環境変数の管理

## 機能説明
### 主要関数
1. `initialize_hash_file()`
   - ハッシュファイルの初期化
   - ファイルが存在しない場合に空のJSONオブジェクトを作成

2. `load_hashes()`
   - 前回のハッシュ値を読み込み
   - ファイルが存在しない場合や不正な形式の場合は空の辞書を返す

3. `save_hashes(hashes)`
   - 新しいハッシュ値を保存
   - JSON形式でファイルに書き込み

4. `generate_hash(content)`
   - ページの内容からMD5ハッシュを生成
   - 更新の検出に使用

5. `load_urls()`
   - 監視対象のURLを読み込み
   - urls.txtからURLリストを取得
   - 読み込み状況をログに記録

6. `get_page_content(url)`
   - 指定したURLのページ内容を取得
   - エラーハンドリングを含む
   - 取得状況をログに記録

7. `send_email(url, changes)`
   - 更新通知のメールを送信
   - SMTPサーバーを使用
   - 複数のメールアドレスに対応

8. `check_webpage_changes()`
   - メインの監視処理
   - 各URLの内容を取得し、前回のハッシュと比較
   - 更新を検出した場合にメール通知
   - URLの追加・削除を検出
   - 変更のサマリーを表示

## 監視の種類
1. ページの更新
   - ページの内容が変更された場合に通知
   - ハッシュ値の比較により検出

2. URLの追加
   - 新しいURLが追加された場合に通知
   - 初回の監視開始を通知
   - 変更サマリーに表示

3. URLの削除
   - URLが削除された場合に検出
   - 変更サマリーに表示
   - 次回から監視対象から除外

## ローカルでの実行方法
1. 環境の準備
   ```bash
   pip install -r requirements.txt
   ```

2. 環境変数の設定
   `.env`ファイルを作成し、以下を設定：
   ```
   SMTP_SERVER=smtp.gmail.com
   SMTP_PORT=587
   EMAIL_USER=your_email@gmail.com
   EMAIL_PASSWORD=your_app_password
   TO_EMAILS=user1@example.com,user2@example.com,user3@example.com
   ```

3. 監視対象URLの設定
   `urls.txt`に監視したいURLを1行ずつ記述

4. 実行
   ```bash
   python main.py
   ```

## GitHub Actionsでの実行方法
1. リポジトリの設定
   - リポジトリの「Settings」→「Secrets and variables」→「Actions」で以下を設定：
     - SMTP_SERVER
     - SMTP_PORT
     - EMAIL_USER
     - EMAIL_PASSWORD
     - TO_EMAILS（カンマ区切りのメールアドレスリスト）

2. ワークフローの設定
   - デフォルトで毎日午前10時（日本時間）に実行
   - 手動実行も可能

3. 実行の確認
   - 「Actions」タブでワークフローの実行状況を確認
   - ログでエラーや通知の送信状況を確認
   - URLの変更状況を確認

## 注意事項
- Gmailを使用する場合は2段階認証を有効にし、アプリパスワードを生成する必要があります
- 監視対象のURLが変更された場合、初回実行時に通知が送信されます
- ハッシュファイルはGitHub Actionsのキャッシュとリポジトリの両方で管理されます
- 複数のメールアドレスはカンマ（,）で区切って指定します
- URLの追加・削除は実行時に自動的に検出されます 



## 更新履歴
### Apr. 29, 2025
- 初回公開

### May, 1. 2025
- HTML保存機能を追加
  - 監視対象ページのHTMLスナップショットを保存
  - 差分検出時に前回のHTMLと比較可能
  - `html_snapshots`ディレクトリに自動保存