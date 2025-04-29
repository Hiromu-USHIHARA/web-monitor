# Github Actionsで作るウェブページ更新監視ツール

## 概要

このガイドでは，ウェブページの更新を監視し，変更があった場合にメールで通知するシステムの実装手順を解説します．このシステムは以下の特徴を持っています：

- Pythonを使用したシンプルな実装
- ハッシュベースの更新検出
- SMTPによるメール通知
- GitHub Actionsによる自動実行
- 環境変数による設定管理

実装は，環境構築から始まり，基本機能の実装，GitHub Actionsの設定，テスト，そして運用までの流れで進めていきます．

## 1. プロジェクトの準備

このセクションでは，ウェブページ監視ツールの開発環境を整備します．プロジェクトのディレクトリ構造を作成し，必要なパッケージをインストールします．また，設定ファイルの初期化も行います．

### 1.1 プロジェクトディレクトリの作成

まず，プロジェクト用のディレクトリを作成します．

```bash
mkdir web-monitor
cd web-monitor
```

### 1.2 仮想環境の作成と有効化

Pythonの仮想環境を作成し，有効化します．これにより，プロジェクト固有の依存関係を管理できます．

```bash
python3.9 -m venv venv
source venv/bin/activate
```

### 1.3 必要なパッケージのインストール

プロジェクトで使用するパッケージをインストールします．

```bash
pip install requests beautifulsoup4 python-dotenv
```

各パッケージの役割：
- requests: ウェブページの取得
- beautifulsoup4: HTMLの解析
- python-dotenv: 環境変数の管理

### 1.4 基本ファイルの作成

プロジェクトに必要な基本ファイルを作成します．

1. `requirements.txt`の作成
   ```
   requests==2.31.0
   beautifulsoup4==4.12.2
   python-dotenv==1.0.0
   ```

2. `urls.txt`の作成
   ```
   https://example.com/page1
   https://example.com/page2
   ```

3. `.env`ファイルの作成
   ```
   SMTP_SERVER=smtp.gmail.com
   SMTP_PORT=587
   EMAIL_USER=your_email@gmail.com
   EMAIL_PASSWORD=your_app_password
   TO_EMAILS=user1@example.com,user2@example.com
   ```

## 2. メインスクリプトの実装

このセクションでは，ウェブページ監視の主要な機能を実装します．各関数の役割と実装手順を順を追って説明します．実装は，ライブラリのインポートから始まり，環境変数の読み込み，各機能の実装，そしてメイン処理の実装まで進めていきます．

### 2.1 必要なライブラリのインポート

`main.py`を作成し，必要なライブラリをインポートします．

```python
import os
import requests
from bs4 import BeautifulSoup
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
import json
import hashlib
```

### 2.2 環境変数の読み込み

`.env`ファイルから設定を読み込みます．

```python
load_dotenv()
SMTP_SERVER = os.getenv('SMTP_SERVER')
SMTP_PORT = int(os.getenv('SMTP_PORT', 587))
EMAIL_USER = os.getenv('EMAIL_USER')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')
TO_EMAILS = [email.strip() for email in os.getenv('TO_EMAILS', '').split(',') if email.strip()]
```

### 2.3 ハッシュファイルの管理関数の実装

ページの更新を検出するために，ハッシュ値を管理する関数を実装します．

```python
HASH_FILE = 'last_hashes.json'

def initialize_hash_file():
    if not os.path.exists(HASH_FILE):
        with open(HASH_FILE, 'w') as f:
            json.dump({}, f, indent=2)
        print(f"ハッシュファイルを初期化しました: {HASH_FILE}")

def load_hashes():
    try:
        if os.path.exists(HASH_FILE):
            with open(HASH_FILE, 'r') as f:
                content = f.read()
                if not content.strip():
                    return {}
                return json.loads(content)
        return {}
    except json.JSONDecodeError:
        print(f"ハッシュファイルの形式が不正です。初期化します。")
        initialize_hash_file()
        return {}

def save_hashes(hashes):
    with open(HASH_FILE, 'w') as f:
        json.dump(hashes, f, indent=2)
```

### 2.4 ハッシュ生成とページ取得関数の実装

ページの内容を取得し，ハッシュ値を生成する関数を実装します．

```python
def generate_hash(content):
    return hashlib.md5(content.encode()).hexdigest()

def get_page_content(url):
    try:
        print(f"URLの取得を開始: {url}")
        response = requests.get(url)
        response.raise_for_status()
        print(f"URLの取得が成功: {url}")
        return response.text
    except requests.RequestException as e:
        print(f"URLの取得に失敗: {url} - {e}")
        return None
```

### 2.5 メール通知関数の実装

更新を検出した場合にメールを送信する関数を実装します．

```python
def send_email(url, changes):
    if not TO_EMAILS:
        print("警告: 送信先メールアドレスが設定されていません")
        return

    msg = MIMEMultipart()
    msg['From'] = EMAIL_USER
    msg['To'] = ', '.join(TO_EMAILS)
    msg['Subject'] = f"ウェブページ更新通知: {url}"

    body = f"""
    以下のウェブページに更新がありました：
    URL: {url}
    
    変更内容:
    {changes}
    """
    msg.attach(MIMEText(body, 'plain'))

    try:
        print(f"メール送信を開始: {url} -> {', '.join(TO_EMAILS)}")
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        print(f"メール送信が成功: {url}")
    except Exception as e:
        print(f"メール送信に失敗: {e}")
```

### 2.6 URL管理関数の実装

監視対象のURLを管理する関数を実装します．

```python
def load_urls():
    try:
        with open('urls.txt', 'r') as f:
            urls = [line.strip() for line in f if line.strip()]
        print(f"監視対象URLを読み込みました: {len(urls)}件")
        return urls
    except Exception as e:
        print(f"URLファイルの読み込みに失敗しました: {e}")
        return []
```

### 2.7 メインの監視処理関数の実装

ウェブページの更新を監視するメインの関数を実装します．

```python
def check_webpage_changes():
    urls = load_urls()
    current_hashes = load_hashes()
    new_hashes = {}
    added_urls = []
    removed_urls = []

    # 削除されたURLを検出
    for url in current_hashes:
        if url not in urls:
            removed_urls.append(url)
            print(f"URLが削除されました: {url}")

    # 追加されたURLを検出
    for url in urls:
        if url not in current_hashes:
            added_urls.append(url)
            print(f"新しいURLを追加: {url}")

    for url in urls:
        print(f"URLの監視を開始: {url}")
        current_content = get_page_content(url)
        if not current_content:
            continue

        # ページのメインコンテンツを抽出
        soup = BeautifulSoup(current_content, 'html.parser')
        main_content = soup.get_text()
        
        # ハッシュを生成
        current_hash = generate_hash(main_content)
        new_hashes[url] = current_hash

        # 前回のハッシュと比較
        if url in current_hashes:
            if current_hash != current_hashes[url]:
                print(f"更新を検出: {url}")
                send_email(url, "ページの内容が更新されました。")
            else:
                print(f"更新なし: {url}")
        else:
            print(f"新しいURLの監視を開始: {url}")
            send_email(url, "新しいURLの監視を開始しました。")

    # 新しいハッシュを保存
    save_hashes(new_hashes)
    print("すべてのURLの監視が完了しました")

    # 変更のサマリーを表示
    if added_urls or removed_urls:
        print("\n監視対象URLの変更サマリー:")
        if added_urls:
            print(f"追加されたURL: {len(added_urls)}件")
            for url in added_urls:
                print(f"  - {url}")
        if removed_urls:
            print(f"削除されたURL: {len(removed_urls)}件")
            for url in removed_urls:
                print(f"  - {url}")
```

### 2.8 メイン関数の実装

プログラムのエントリーポイントとなるメイン関数を実装します．

```python
def main():
    print("ウェブページ監視を開始します...")
    
    # ハッシュファイルの初期化
    initialize_hash_file()
    
    # ウェブページの変更をチェック
    check_webpage_changes()
    
    print("ウェブページ監視を完了しました。")

if __name__ == "__main__":
    main()
```

## 3. ローカルでのテスト

このセクションでは，実装したスクリプトの動作確認を行います．ローカル環境でスクリプトを実行し，各機能が期待通りに動作することを確認します．また，エラーハンドリングが適切に行われているかも確認します．

### 3.1 スクリプトの実行

実装したスクリプトをローカルで実行し，動作を確認します．

```bash
python main.py
```

### 3.2 動作確認

以下の点を確認します：
- URLの取得が正常に行われるか
- メール送信が正常に行われるか
- エラーハンドリングが適切か

## 4. GitHub Actionsの設定

このセクションでは，GitHub Actionsを使用して自動化された監視システムを構築します．GitHubリポジトリの作成から始まり，ワークフローの設定，シークレットの管理，そして自動実行の確認までを行います．

### 4.1 GitHubリポジトリの作成

1. GitHubで新しいリポジトリを作成します
2. リポジトリ名を設定（例：web-monitor）
3. 必要に応じて説明を追加します

### 4.2 ローカルリポジトリの初期化

```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/your-username/web-monitor.git
git push -u origin main
```

### 4.3 ワークフローファイルの作成

`.github/workflows/main.yml`を作成し，GitHub Actionsの設定を行います．

```yaml
name: Web Page Monitor

on:
  schedule:
    - cron: '0 1 * * *'  # 毎日午前10時（日本時間）に実行
  workflow_dispatch:  # 手動実行も可能

jobs:
  monitor:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python
      uses: actions/setup-python@v5
      with:
        python-version: '3.9'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
    
    - name: Run monitor
      env:
        SMTP_SERVER: ${{ secrets.SMTP_SERVER }}
        SMTP_PORT: ${{ secrets.SMTP_PORT }}
        EMAIL_USER: ${{ secrets.EMAIL_USER }}
        EMAIL_PASSWORD: ${{ secrets.EMAIL_PASSWORD }}
        TO_EMAILS: ${{ secrets.TO_EMAILS }}
      run: python main.py
```

### 4.4 GitHub Secretsの設定

セキュリティを考慮して，機密情報はGitHub Secretsとして管理します．

1. リポジトリの「Settings」→「Secrets and variables」→「Actions」に移動
2. 以下のシークレットを追加：
   - SMTP_SERVER
   - SMTP_PORT
   - EMAIL_USER
   - EMAIL_PASSWORD
   - TO_EMAILS

### 4.5 GitHub Actionsの実行確認

1. Actionsタブでワークフローの実行状況を確認
2. 手動実行の方法を確認
3. 実行結果を確認


