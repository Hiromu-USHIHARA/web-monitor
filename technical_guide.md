
## 概要

この記事では[Github Actions](https://docs.github.com/ja/actions)を利用して，Webページの更新を定期監視してメールで通知するシステムを構築します．
このシステムは以下の特徴を持っています：

- Pythonを使用したシンプルな実装
- ハッシュベースの更新検出
- HTMLスナップショットによる差分抽出
- SMTPによるメール通知
- GitHub Actionsによる自動実行
- 環境変数による設定管理

環境構築からコード実装，Github Actionsのセットアップまでステップバイステップに進めていきます．

> この記事は[Zennでも公開](https://zenn.dev/hiromu_ushihara/articles/3157e21cfd877a)しています．

## 1. プロジェクトの準備

まずは必要なライブラリなどの準備を行います．
> Github Actionsでのみ動かす場合にはパッケージのインストールは不要です．

### 1.1 プロジェクトディレクトリの作成

まず，プロジェクト用のディレクトリを作成します．

```bash
mkdir web-monitor
cd web-monitor
```

### 1.2 仮想環境の作成と有効化

Pythonの仮想環境を作成し，有効化します．これにより，プロジェクト固有の依存関係を管理できます．

```bash
python -m venv venv
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
   requests==2.32.4
   beautifulsoup4==4.12.2
   python-dotenv==1.0.0
   ```

2. `urls.txt`の作成
   ```
   https://example.com/page1
   https://example.com/page2
   ```
   監視対象のWebページのURLです．
    > URLの末尾に`/`がついていると正常に動作しないことがあります．

3. `.env`ファイルの作成
   ```
   SMTP_SERVER=smtp.gmail.com
   SMTP_PORT=587
   EMAIL_USER=your_email@gmail.com
   EMAIL_PASSWORD=your_app_password
   TO_EMAILS=user1@example.com,user2@example.com
   ```
   - `SMTP_SERVER`，`SMTP_PORT`: 今回はgmailを使ってメールの発信を行います．
   - `EMAIL_USER`: 送信元のgmailアドレスです．
   - `EMAIL_PASSWORD`: Googleアカウントのパスワードではなく，gmailの[アプリパスワード](https://support.google.com/accounts/answer/185833?hl=ja)です．
   - `TO_EMAILS`: `,`区切りで送信先のメールアドレスを記述します．

4. `.gitignore`ファイルの作成
   ```
   .env
   .venv
   ```

## 2. メインスクリプトの実装

それではWebページ監視ツールの主要な機能の実装を行っていきましょう．

全体は`main.py`というファイルに集約します．
```bash
touch main.py
```

### 2.1 準備

必要なライブラリのインポートと環境変数の読み込みを行います．
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
import difflib

load_dotenv()
SMTP_SERVER = os.getenv('SMTP_SERVER')
SMTP_PORT = int(os.getenv('SMTP_PORT', 587))
EMAIL_USER = os.getenv('EMAIL_USER')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')
TO_EMAILS = [email.strip() for email in os.getenv('TO_EMAILS', '').split(',') if email.strip()]
```

### 2.2 Webページの読み込み

`urls.txt`ファイルに記載されたURLからWebページの内容にアクセスする機能を実装します．

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

### 2.3 ハッシュ値の管理

Webページの更新を検知するためには前回アクセス時の情報との比較が必要です．ここではハッシュ値を`last_hashes.json`というファイルに保存しておき，その情報との比較を行うことで更新を検知することにします．

```python
HASH_FILE = 'last_hashes.json'

def initialize_hash_file():
    if not os.path.exists(HASH_FILE):
        with open(HASH_FILE, 'w') as f:
            json.dump({}, f, indent=2)
        print(f"ハッシュファイルを初期化しました: {HASH_FILE}")
```

Webページの内容からハッシュを生成，保存します．

```python
def generate_hash(content):
    return hashlib.md5(content.encode()).hexdigest()

def save_hashes(hashes):
    with open(HASH_FILE, 'w') as f:
        json.dump(hashes, f, indent=2)
```


ハッシュファイルの読み込みも実装しておきます．

```python
def load_hashes():
    try:
        if os.path.exists(HASH_FILE):
            with open(HASH_FILE, 'r') as f:
                content = f.read()
                if not content.strip():  # ファイルが空の場合
                    return {}
                return json.loads(content)
        return {}
    except json.JSONDecodeError:
        print(f"ハッシュファイルの形式が不正です。初期化します。")
        initialize_hash_file()
        return {}
```

### 2.4 メール通知機能

続いてWebページの更新をメールで通知する機能を実装します．

```python
def send_email(url):
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

### 2.5 変更検出機能の実装

次にハッシュ値の比較から変更を検出する機能を実装します．

```python
def check_webpage_changes():
    urls = load_urls()
    current_hashes = load_hashes()
    new_hashes = {}

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
        if current_hash != current_hashes[url]:
            print(f"更新を検出: {url}")
            send_email(url)
        else:
            print(f"更新なし: {url}")

    # 新しいハッシュを保存
    save_hashes(new_hashes)
    print("すべてのURLの監視が完了しました")
```

### 2.6 `main`関数の実装

ここまでで，URLの読み込み，ハッシュ値の保存・読み込み，変更の検出，メールの送信という一連の流れに必要な機能が準備できました．
これらを組み合わせて，`main`関数を実装します．

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

それではローカルで動作確認をしましょう（Github Actionsで動かしてテストしたい場合は次のセクションに飛んでください）．

```bash
python main.py
```

ログメッセージを確認して適切に動作していることを確かめてください．


## 4. GitHub Actionsの設定

続いて，Github Actionsを用いた自動化を行います．

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

> `.env`ファイルをリモートにアップしてしまわないように，必ず`.gitignore`ファイルを作成してください．

### 4.3 ワークフローファイルの作成

`.github/workflows/main.yml`を作成し，GitHub Actionsの設定を行います．

```yaml
name: Web Page Monitor

on:
  schedule:
    - cron: '0 1 * * *'  # 毎日午前10時（日本時間）に実行
  workflow_dispatch:  # 手動実行も可能

permissions:
  contents: write
  pull-requests: write

jobs:
  monitor:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v4
      with:
        token: ${{ secrets.GITHUB_TOKEN }}
    
    - name: Set up Python
      uses: actions/setup-python@v5
      with:
        python-version: '3.9'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
    
    - name: Cache hash file and snapshots
      uses: actions/cache@v4
      with:
        path: |
          last_hashes.json
        key: ${{ runner.os }}-monitor-${{ hashFiles('urls.txt') }}
        restore-keys: |
          ${{ runner.os }}-monitor-
    
    - name: Run monitor
      env:
        SMTP_SERVER: ${{ secrets.SMTP_SERVER }}
        SMTP_PORT: ${{ secrets.SMTP_PORT }}
        EMAIL_USER: ${{ secrets.EMAIL_USER }}
        EMAIL_PASSWORD: ${{ secrets.EMAIL_PASSWORD }}
        TO_EMAILS: ${{ secrets.TO_EMAILS }}
      run: python main.py
    
    - name: Commit changes
      if: success()
      run: |
        git config --local user.email "action@github.com"
        git config --local user.name "GitHub Action"
        git add last_hashes.json
        git status
        git diff --quiet && git diff --staged --quiet || (git commit -m "Update monitor data" && git push)
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

まずは手動実行して期待通りの動作をするか確認します．

1. Actionsタブでワークフローの実行状況を確認
2. 手動実行の方法を確認
3. 実行結果を確認

ログを確認して問題なければOKです．

## 5. 機能の拡張

ここまでで一通りの機能は完成しましたが，エラーハンドリングや利便性の観点からは改善の余地があります．

### 5.1 URLの追加・削除の検知

`urls.txt`に新しいURLが追加された場合や，逆に削除された場合の処理を実装します．
`check_webpage_changes`関数を変更します．

```diff python
def check_webpage_changes():
    urls = load_urls()
    current_hashes = load_hashes()
    new_hashes = {}
+    added_urls = []
+    removed_urls = []

+    # 削除されたURLを検出
+    for url in current_hashes:
+        if url not in urls:
+            removed_urls.append(url)
+            print(f"URLが削除されました: {url}")

+    # 追加されたURLを検出
+    for url in urls:
+        if url not in current_hashes:
+            added_urls.append(url)
+            print(f"新しいURLを追加: {url}")

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

+        # 前回のハッシュと比較
+        if url in current_hashes:
+            if current_hash != current_hashes[url]:
+                print(f"更新を検出: {url}")
+                # 通知を送信
+                send_email(url)
+            else:
+                print(f"更新なし: {url}")
+        else:
+            print(f"新しいURLの監視を開始: {url}")
+            send_email(url, "新しいURLの監視を開始しました。")
-        if current_hash != current_hashes[url]:
-            print(f"更新を検出: {url}")
-            send_email(url)
-        else:
-            print(f"更新なし: {url}")

    # 新しいハッシュを保存
    save_hashes(new_hashes)
    print("すべてのURLの監視が完了しました")

+    # 変更のサマリーを表示
+    if added_urls or removed_urls:
+        print("\n監視対象URLの変更サマリー:")
+        if added_urls:
+            print(f"追加されたURL: {len(added_urls)}件")
+            for url in added_urls:
+                print(f"  - {url}")
+        if removed_urls:
+            print(f"削除されたURL: {len(removed_urls)}件")
+            for url in removed_urls:
+                print(f"  - {url}")
```

### 5.2 HTMLを保存して変更内容を通知

WebページのHTMLを保存し，差分を抽出する機能を実装します．

```python
# HTML保存ディレクトリのパス
HTML_DIR = 'html_snapshots'

def initialize_html_dir():
    if not os.path.exists(HTML_DIR):
        os.makedirs(HTML_DIR)
        print(f"HTML保存ディレクトリを作成しました: {HTML_DIR}")

# HTMLファイルのパスを生成
def get_html_file_path(url):
    filename = hashlib.md5(url.encode()).hexdigest() + '.html'
    return os.path.join(HTML_DIR, filename)

# HTMLを保存
def save_html(url, content):
    file_path = get_html_file_path(url)
    print(f"HTML保存を試みます: {file_path}")
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"HTMLを保存しました: {file_path}")
    except Exception as e:
        print(f"HTMLの保存に失敗しました: {file_path} - {str(e)}")
        print(f"現在のディレクトリ: {os.getcwd()}")
        print(f"ディレクトリの存在確認: {os.path.exists(HTML_DIR)}")
        print(f"ディレクトリの権限: {oct(os.stat(HTML_DIR).st_mode)[-3:]}")
        print(f"ファイルの権限: {oct(os.stat(file_path).st_mode)[-3:] if os.path.exists(file_path) else 'ファイルが存在しません'}")

# 前回のHTMLを読み込む
def load_previous_html(url):
    file_path = get_html_file_path(url)
    print(f"前回のHTMLを読み込みます: {file_path}")
    try:
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                print(f"前回のHTMLを読み込みました: {file_path}")
                return content
        print(f"前回のHTMLが存在しません: {file_path}")
    except Exception as e:
        print(f"前回のHTMLの読み込みに失敗しました: {file_path} - {str(e)}")
        print(f"現在のディレクトリ: {os.getcwd()}")
        print(f"ディレクトリの存在確認: {os.path.exists(HTML_DIR)}")
        print(f"ディレクトリの権限: {oct(os.stat(HTML_DIR).st_mode)[-3:]}")
        print(f"ファイルの権限: {oct(os.stat(file_path).st_mode)[-3:] if os.path.exists(file_path) else 'ファイルが存在しません'}")
    return None

# 差分を抽出
def get_diff(previous_content, current_content):
    if not previous_content:
        return "初回の監視です。"
    
    previous_lines = previous_content.splitlines()
    current_lines = current_content.splitlines()
    
    diff = difflib.unified_diff(
        previous_lines,
        current_lines,
        fromfile='前回のHTML',
        tofile='現在のHTML',
        lineterm=''
    )
    return '\n'.join(diff)

# HTMLを削除
def delete_html(url):
    file_path = get_html_file_path(url)
    print(f"HTML削除を試みます: {file_path}")
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"HTMLを削除しました: {file_path}")
    except Exception as e:
        print(f"HTMLの削除に失敗しました: {file_path} - {str(e)}")
```

変更内容をこれまでの機能に反映していきます．

```diff python
+ def send_email(url, changes):
- def send_email(url):
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
    
+    変更内容:
+    {changes}
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

```diff python
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
            # HTMLスナップショットを削除
            delete_html(url)

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
+                # 前回のHTMLを読み込む
+                previous_content = load_previous_html(url)
+                # 差分を抽出
+                diff = get_diff(previous_content, current_content)
                # 通知を送信
+                send_email(url, f"ページの内容が更新されました。\n\n差分:\n{diff}")
-                send_email(url)
+                # 現在のHTMLを保存（前回のHTMLは上書き）
+                save_html(url, current_content)
            else:
                print(f"更新なし: {url}")
        else:
            print(f"新しいURLの監視を開始: {url}")
+            # 初回のHTMLを保存
+            save_html(url, current_content)
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

def main():
    print("ウェブページ監視を開始します...")
    
    # ハッシュファイルとHTML保存ディレクトリの初期化
    initialize_hash_file()
+    initialize_html_dir()
    
    # ウェブページの変更をチェック
    check_webpage_changes()
    
    print("ウェブページ監視を完了しました。")
```

```diff yaml
# .github/workflows/main.yml
name: Web Page Monitor

on:
  schedule:
    - cron: '0 1 * * *'  # 毎日午前10時（日本時間）に実行
  workflow_dispatch:  # 手動実行も可能

permissions:
  contents: write
  pull-requests: write

jobs:
  monitor:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v4
      with:
        token: ${{ secrets.GITHUB_TOKEN }}
    
    - name: Set up Python
      uses: actions/setup-python@v5
      with:
        python-version: '3.9'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
    
    - name: Cache hash file and snapshots
      uses: actions/cache@v4
      with:
        path: |
          last_hashes.json
+          html_snapshots/
        key: ${{ runner.os }}-monitor-${{ hashFiles('urls.txt') }}
        restore-keys: |
          ${{ runner.os }}-monitor-
    
    - name: Run monitor
      env:
        SMTP_SERVER: ${{ secrets.SMTP_SERVER }}
        SMTP_PORT: ${{ secrets.SMTP_PORT }}
        EMAIL_USER: ${{ secrets.EMAIL_USER }}
        EMAIL_PASSWORD: ${{ secrets.EMAIL_PASSWORD }}
        TO_EMAILS: ${{ secrets.TO_EMAILS }}
      run: python main.py
    
    - name: Commit changes
      if: success()
      run: |
        git config --local user.email "action@github.com"
        git config --local user.name "GitHub Action"
+        git add last_hashes.json html_snapshots/
-        git add last_hashes.json
        git status
        git diff --quiet && git diff --staged --quiet || (git commit -m "Update monitor data" && git push)
```

## おわりに
以上でGithub Actionsで動かすWebページ自動監視ツールが出来上がりました．
完成版のコードは[Githubリポジトリ](https://github.com/Hiromu-USHIHARA/web-monitor.git)で公開しています．

“退屈なことはPythonにやらせ”て楽しいインターネットライフを！^[すみません．読んでないです...]
