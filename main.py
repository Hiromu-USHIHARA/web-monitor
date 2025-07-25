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
import openai

# 環境変数の読み込み
load_dotenv()

# メール設定
SMTP_SERVER = os.getenv('SMTP_SERVER')
SMTP_PORT = int(os.getenv('SMTP_PORT', 587))
EMAIL_USER = os.getenv('EMAIL_USER')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')
# 複数のメールアドレスをカンマ区切りで取得
TO_EMAILS = [email.strip() for email in os.getenv('TO_EMAILS', '').split(',') if email.strip()]

# OpenAI設定
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
OPENAI_MODEL = 'gpt-4.1-nano'

# 監視対象のURLを読み込む
def load_urls():
    try:
        with open('urls.txt', 'r') as f:
            urls = [line.strip() for line in f if line.strip()]
        print(f"監視対象URLを読み込みました: {len(urls)}件")
        return urls
    except Exception as e:
        print(f"URLファイルの読み込みに失敗しました: {e}")
        return []

# ウェブページの内容を取得
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

HASH_FILE = 'last_hashes.json'

# ハッシュファイルを初期化
def initialize_hash_file():
    if not os.path.exists(HASH_FILE):
        with open(HASH_FILE, 'w') as f:
            json.dump({}, f, indent=2)
        print(f"ハッシュファイルを初期化しました: {HASH_FILE}")

# ウェブページの内容からハッシュを生成
def generate_hash(content):
    # テキストの正規化（HTMLタグを除去してから正規化）
    soup = BeautifulSoup(content, 'html.parser')
    text_content = soup.get_text()
    normalized_content = ' '.join(text_content.split())
    # エンコーディングを明示的に指定
    return hashlib.md5(normalized_content.encode('utf-8')).hexdigest()

# ハッシュファイルを保存
def save_hashes(hashes):
    try:
        print(f"ハッシュを保存します: {hashes}")  # デバッグ用
        with open(HASH_FILE, 'w') as f:
            json.dump(hashes, f, indent=2)
        print(f"ハッシュを保存しました: {len(hashes)}件")
    except Exception as e:
        print(f"ハッシュの保存に失敗しました: {e}")

# ハッシュファイルを読み込む
def load_hashes():
    try:
        if os.path.exists(HASH_FILE):
            print(f"ハッシュファイルを読み込みます: {HASH_FILE}")
            with open(HASH_FILE, 'r') as f:
                content = f.read()
                if not content.strip():  # ファイルが空の場合
                    print("ハッシュファイルが空です")
                    return {}
                hashes = json.loads(content)
                print(f"読み込んだハッシュ: {hashes}")  # デバッグ用
                return hashes
        print(f"ハッシュファイルが存在しません: {HASH_FILE}")
        return {}
    except json.JSONDecodeError as e:
        print(f"ハッシュファイルの形式が不正です: {e}")
        print(f"ファイルの内容: {content}")  # デバッグ用
        initialize_hash_file()
        return {}
    except Exception as e:
        print(f"ハッシュファイルの読み込みに失敗しました: {e}")
        return {}

HTML_DIR = 'html_snapshots'

# HTML保存ディレクトリの初期化
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

# OpenAI APIを使って差分を要約
def summarize_diff_with_openai(diff, url):
    if not OPENAI_API_KEY:
        print("警告: OpenAI APIキーが設定されていません。差分をそのまま返します。")
        return diff
    
    try:
        print("OpenAI APIを使用して差分を要約します...")
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        
        # 差分が長すぎる場合は切り詰める（OpenAI APIの制限を考慮）
        max_diff_length = 25000  # 安全マージン
        if len(diff) > max_diff_length:
            diff_short = diff[:max_diff_length] + "\n... (差分が長すぎるため切り詰めました)"
        
        prompt = f"""
以下のウェブページの差分を日本語で要約してください。

差分:
{diff_short}
"""
        
        # 最新版のresponses APIを使用
        response = client.responses.create(
            model=OPENAI_MODEL,
            input=prompt,
            instructions="あなたはウェブページの変更内容を要約する専門家です。"
        )
        
        summary = response.output_text.strip()
        print("OpenAI APIによる要約が完了しました")
        return f"【AI要約】\n{summary}\n\n【詳細差分】\n{diff}"
        
    except openai.AuthenticationError:
        print("エラー: OpenAI APIキーが無効です。差分をそのまま返します。")
        return diff
    except openai.RateLimitError:
        print("エラー: OpenAI APIのレート制限に達しました。差分をそのまま返します。")
        return diff
    except openai.InsufficientQuotaError:
        print("エラー: OpenAI APIのクレジットが不足しています。差分をそのまま返します。")
        return diff
    except Exception as e:
        print(f"エラー: OpenAI APIの呼び出しに失敗しました: {e}。差分をそのまま返します。")
        return diff

# メールを送信
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

# ウェブページの変更をチェック
def check_webpage_changes():
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
                    # 差分を要約
                    summarized_diff = summarize_diff_with_openai(diff, url)
                    # 通知を送信
                    send_email(url, summarized_diff)
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
