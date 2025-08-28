---
title: "Github Actionsで作るウェブページ更新監視ツール（AI要約機能追加編）"
emoji: "👀"
type: "tech"
topics:
  - "python"
  - "githubactions"
  - "openai"
  - "zennfes2025free"
published: true
published_at: "2025-08-28 17:24"
---

この記事では，[以前の記事](https://zenn.dev/hiromu_ushihara/articles/3157e21cfd877a)で作成したWebページ更新監視ツールに，機能を追加します．
具体的には，OpenAI APIを利用して，更新があったページの更新内容の差分を要約して通知する機能を実装します．

@[card](https://zenn.dev/hiromu_ushihara/articles/3157e21cfd877a)

## 現行版の問題点と改善案

前回の記事で作成したアプリケーションでは，Webページに更新があった場合には，更新があった旨とhtmlの差分がメールで通知されるようになっていました．
しかし，htmlの生の差分テキストは人間が読むようにはできていません．
綺麗に構造化されたページならまだしも，そうでないページの場合には目も当てられません．
そのため実際の運用では，更新通知があった後にブラウザでChatGPTに差分テキストを与えて要約を作成してもらうことが珍しくありませんでした．

そこで，更新があった場合の差分要約まで一括で行えるように，OpenAI APIを呼び出す機能を追加するとより便利になると考え，今回の機能追加に至りました．

:::message
OpenAI APIを使わない（無料の）運用も可能ですので，ご安心ください
:::

## 実装

前回作成した`main.py`に要約機能を追加します．
概略は以下の通りです．

- 環境変数としてOpenAI APIのキーを読み込む
- APIを通して指定されたモデルを呼び出し，要約を生成する
    - 入力トークンが過剰にならないように，差分を圧縮する
- 従来の仕様を含むようにエラーハンドリングを行う
    - キーが設定されていない場合やクレジットが不足している場合には，警告の表示とともに，差分テキストをそのまま通知する←従来の機能を内包
- 通知メッセージには要約と生の差分テキストの両方を含める

`main.py`の更新内容は以下の通りです（一部を省略しています）．

:::details main.pyの更新
```diff python: main.py
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
from datetime import datetime
+ import openai

# 環境変数の読み込み
load_dotenv()

# メール設定
SMTP_SERVER = os.getenv('SMTP_SERVER')
SMTP_PORT = int(os.getenv('SMTP_PORT', 587))
EMAIL_USER = os.getenv('EMAIL_USER')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')
# 複数のメールアドレスをカンマ区切りで取得
TO_EMAILS = [email.strip() for email in os.getenv('TO_EMAILS', '').split(',') if email.strip()]

+ # OpenAI設定
+ OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
+ OPENAI_MODEL = 'gpt-4.1-nano'

# 監視対象のURLを読み込む
def load_urls():
    # 中略

# ウェブページの内容を取得
def get_page_content(url):
    # 中略

HASH_FILE = 'last_hashes.json'

# ハッシュファイルを初期化
def initialize_hash_file():
    # 中略

# ウェブページの内容からハッシュを生成
def generate_hash(content):
    # 中略

# ハッシュファイルを保存
def save_hashes(hashes):
    # 中略

# ハッシュファイルを読み込む
def load_hashes():
    # 中略

HTML_DIR = 'html_snapshots'

# HTML保存ディレクトリの初期化
def initialize_html_dir():
    # 中略

# HTMLファイルのパスを生成
def get_html_file_path(url):
    # 中略

# HTMLを保存
def save_html(url, content):
    # 中略

# 前回のHTMLを読み込む
def load_previous_html(url):
    # 中略

# 差分を抽出
def get_diff(previous_content, current_content):
    # 中略

# HTMLを削除
def delete_html(url):
    # 中略

+ # OpenAI APIを使って差分を要約
+ def summarize_diff_with_openai(diff, url):
+     if not OPENAI_API_KEY:
+         print("警告: OpenAI APIキーが設定されていません。差分をそのまま返します。")
+         return diff
+     
+     try:
+         print("OpenAI APIを使用して差分を要約します...")
+         client = openai.OpenAI(api_key=OPENAI_API_KEY)
+         
+         # 差分が長すぎる場合は切り詰める（OpenAI APIの制限を考慮）
+         max_diff_length = 25000  # 安全マージン
+         if len(diff) > max_diff_length:
+             diff_short = diff[:max_diff_length] + "\n... (差分が長すぎるため切り詰めました)"
+         else:
+             diff_short=diff
+         
+         prompt = f"""
+ 以下のウェブページの差分を日本語で要約してください。
+ 
+ 差分:
+ {diff_short}
+ """
+         
+         # 最新版のresponses APIを使用
+         response = client.responses.create(
+             model=OPENAI_MODEL,
+             input=prompt,
+             instructions="あなたはウェブページの変更内容を要約する専門家です。"
+         )
+         
+         summary = response.output_text.strip()
+         print("OpenAI APIによる要約が完了しました")
+         return f"【AI要約】\n{summary}\n\n【詳細差分】\n{diff}"
+         
+     except openai.AuthenticationError:
+         print("エラー: OpenAI APIキーが無効です。差分をそのまま返します。")
+         return diff
+     except openai.RateLimitError:
+         print("エラー: OpenAI APIのレート制限に達しました。差分をそのまま返します。")
+         return diff
+     except openai.QuotaExceededError:
+         print("エラー: OpenAI APIのクレジットが不足しています。差分をそのまま返します。")
+         return diff
+     except Exception as e:
+         print(f"エラー: OpenAI APIの呼び出しに失敗しました: {e}。差分をそのまま返します。")
+         return diff

# メールを送信
def send_email(url, changes):
    # 中略

# ウェブページの変更をチェック
+ def check_webpage_changes(summarize=True):
- def check_webpage_changes():
    urls = load_urls()
    current_hashes = load_hashes()
    new_hashes = current_hashes.copy()  # 現在のハッシュをコピー
    added_urls = []
    removed_urls = []

    # 削除されたURLを検出
    for url in current_hashes:
        if url not in urls:
            removed_urls.append(url)
            print(f"URLが削除されました: {url}")
            # HTMLスナップショットを削除
            delete_html(url)
            # ハッシュからも削除
            new_hashes.pop(url, None)
            # 変更を即時保存
            save_hashes(new_hashes)

    # 追加されたURLを検出
    for url in urls:
        if url not in current_hashes:
            added_urls.append(url)
            print(f"新しいURLを追加: {url}")

    for url in urls:
        print(f"URLの監視を開始: {url}")
        try:
            current_content = get_page_content(url)
            if not current_content:
                print(f"警告: {url}のコンテンツ取得に失敗しました。前回のハッシュを維持します。")
                continue

            # ハッシュを生成（完全なHTMLコンテンツから）
            current_hash = generate_hash(current_content)
            new_hashes[url] = current_hash

            # 前回のハッシュと比較
            if url in current_hashes:
                if current_hash != current_hashes[url]:
                    print(f"更新を検出: {url}")
                    print(f"前回のハッシュ: {current_hashes[url]}")
                    print(f"現在のハッシュ: {current_hash}")
                    # 前回のHTMLを読み込む
                    previous_content = load_previous_html(url)
                    # 差分を抽出
                    diff = get_diff(previous_content, current_content)
+                     # 差分を要約
+                     if summarize:
+                         summarized_diff = summarize_diff_with_openai(diff, url)
+                     else:
+                         summarized_diff = diff
                    # 通知を送信
-                     send_email(url, f"ページの内容が更新されました。\n\n差分:\n{diff}")
+                     send_email(url, summarized_diff)
                    # 前回のHTMLを削除して新しいHTMLを保存
                    delete_html(url)
                    print(f"前回のHTMLを削除しました: {url}")
                    save_html(url, current_content)
                    print(f"HTMLを保存しました: {url}")
                    # 変更を即時保存
                    save_hashes(new_hashes)
                else:
                    print(f"更新なし: {url}")
            else:
                print(f"新しいURLの監視を開始: {url}")
                # 初回のHTMLを保存
                save_html(url, current_content)
                print(f"HTMLを保存しました: {url}")
                # 変更を即時保存
                save_hashes(new_hashes)
                send_email(url, "新しいURLの監視を開始しました。")
        except Exception as e:
            print(f"エラー: {url}の処理中にエラーが発生しました: {e}")
            print(f"前回のハッシュを維持します。")
            continue

    print("すべてのURLの監視が完了しました")
    print(f"処理したURL数: {len(urls)}")
    print(f"更新されたURL数: {sum(1 for url in urls if url in current_hashes and new_hashes[url] != current_hashes[url])}")

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
    initialize_html_dir()
    
    # ウェブページの変更をチェック
    check_webpage_changes()
    
    print("ウェブページ監視を完了しました。")

if __name__ == "__main__":
    main()
```
:::

また，必要なライブラリも更新します．

```diff txt: requirements.txt
requests==2.32.4
beautifulsoup4==4.12.2
python-dotenv==1.0.0
+ openai==1.97.1
```

以上でAI要約機能が実装できました．
必要に応じて，`OPENAI_MODEL = 'gpt-4.1-nano'`，`max_diff_length = 25000`，`prompt`の部分を変更することにより，要約の精度を高めたり，欲しい情報を取捨選択することが可能です．

Github Actionsで運用する場合には，「Settings」→「Secrets and variables」→「Actions」から，環境変数`OPENAI_API_KEY`を設定してください．
その上で，ワークフローファイルに環境変数の読み込みを追加します．

```diff yml: .github/workflows/main.yml
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
    
    - name: Run monitor
      env:
        SMTP_SERVER: ${{ secrets.SMTP_SERVER }}
        SMTP_PORT: ${{ secrets.SMTP_PORT }}
        EMAIL_USER: ${{ secrets.EMAIL_USER }}
        EMAIL_PASSWORD: ${{ secrets.EMAIL_PASSWORD }}
        TO_EMAILS: ${{ secrets.TO_EMAILS }}
+         OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
      run: python main.py
    
    - name: Commit changes
      if: success()
      run: |
        git config --local user.email "action@github.com"
        git config --local user.name "GitHub Action"
        git add last_hashes.json html_snapshots/
        git status
        git diff --quiet && git diff --staged --quiet || (git commit -m "Update monitor data" && git push)
```

:::message
要約を行わない場合には，環境変数`OPENAI_API_KEY`を未設定にするか，`main`関数内の`check_webpage_changes()`を`check_webpage_changes(summarize=False)`に書き換えてください．
:::

## おわりに

この記事では，以前作成したWebページ更新監視ツールにOpenAI APIを利用した要約機能を追加実装しました．
コードはGithubで公開していますので，ぜひご活用ください．

@[card](https://github.com/Hiromu-USHIHARA/web-monitor)
