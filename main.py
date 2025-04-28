import os
import requests
from bs4 import BeautifulSoup
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
import json
import hashlib

# 環境変数の読み込み
load_dotenv()

# メール設定
SMTP_SERVER = os.getenv('SMTP_SERVER')
SMTP_PORT = int(os.getenv('SMTP_PORT', 587))
EMAIL_USER = os.getenv('EMAIL_USER')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')
# 複数のメールアドレスをカンマ区切りで取得
TO_EMAILS = [email.strip() for email in os.getenv('TO_EMAILS', '').split(',') if email.strip()]

# ハッシュファイルのパス
HASH_FILE = 'last_hashes.json'

# ハッシュファイルを初期化
def initialize_hash_file():
    if not os.path.exists(HASH_FILE):
        with open(HASH_FILE, 'w') as f:
            json.dump({}, f, indent=2)
        print(f"ハッシュファイルを初期化しました: {HASH_FILE}")

# ハッシュファイルを読み込む
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

# ハッシュファイルを保存
def save_hashes(hashes):
    with open(HASH_FILE, 'w') as f:
        json.dump(hashes, f, indent=2)

# ウェブページの内容からハッシュを生成
def generate_hash(content):
    return hashlib.md5(content.encode()).hexdigest()

# 監視対象のURLを読み込む
def load_urls():
    with open('urls.txt', 'r') as f:
        return [line.strip() for line in f if line.strip()]

# ウェブページの内容を取得
def get_page_content(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        print(f"Error fetching {url}: {e}")
        return None

# メールを送信
def send_email(url, changes):
    if not TO_EMAILS:
        print("警告: 送信先メールアドレスが設定されていません")
        return

    msg = MIMEMultipart()
    msg['From'] = EMAIL_USER
    msg['To'] = ', '.join(TO_EMAILS)  # 複数のアドレスをカンマ区切りで設定
    msg['Subject'] = f"ウェブページ更新通知: {url}"

    body = f"""
    以下のウェブページに更新がありました：
    URL: {url}
    
    変更内容:
    {changes}
    """
    msg.attach(MIMEText(body, 'plain'))

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        print(f"メールを送信しました: {url} -> {', '.join(TO_EMAILS)}")
    except Exception as e:
        print(f"メール送信エラー: {e}")

# ウェブページの変更をチェック
def check_webpage_changes():
    urls = load_urls()
    current_hashes = load_hashes()
    new_hashes = {}

    for url in urls:
        print(f"監視中: {url}")
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
            print(f"新しいURLを追加: {url}")
            send_email(url, "新しいURLの監視を開始しました。")

    # 新しいハッシュを保存
    save_hashes(new_hashes)

def main():
    print("ウェブページ監視を開始します...")
    
    # ハッシュファイルの初期化
    initialize_hash_file()
    
    # ウェブページの変更をチェック
    check_webpage_changes()
    
    print("ウェブページ監視を完了しました。")

if __name__ == "__main__":
    main()
