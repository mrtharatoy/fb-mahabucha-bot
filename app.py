import os
import requests
import re
import threading
from flask import Flask, request

app = Flask(__name__)

# --- CONFIG ---
GITHUB_USERNAME = "mrtharatoy"
REPO_NAME = "fb-mahabucha-bot"
BRANCH = "main"
FOLDER_NAME = "images" 
PAGE_ACCESS_TOKEN = os.environ.get('PAGE_ACCESS_TOKEN')
VERIFY_TOKEN = os.environ.get('VERIFY_TOKEN')
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')

CACHED_FILES = {}
FILES_LOADED = False

# --- 1. โหลดรายชื่อรูป ---
def update_file_list():
    global CACHED_FILES, FILES_LOADED
    print("🔄 Loading file list from GitHub...")
    api_url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{REPO_NAME}/contents/{FOLDER_NAME}?ref={BRANCH}"
    headers = {"User-Agent": "Bot", "Accept": "application/vnd.github.v3+json"}
    if GITHUB_TOKEN: headers["Authorization"] = f"token {GITHUB_TOKEN}"
    
    try:
        r = requests.get(api_url, headers=headers, timeout=15)
        if r.status_code == 200:
            data = r.json()
            temp_cache = {}
            for item in data:
                if item['type'] == 'file':
                    key = item['name'].rsplit('.', 1)[0].strip().lower()
                    temp_cache[key] = item['name']
            
            CACHED_FILES = temp_cache
            FILES_LOADED = True
            print(f"✅ FILES READY: {len(CACHED_FILES)} images.")
        else:
            print(f"⚠️ Github Error: {r.status_code}")
    except Exception as e:
        print(f"❌ Error loading files: {e}")

def get_image_url(filename):
    return f"https://raw.githubusercontent.com/{GITHUB_USERNAME}/{REPO_NAME}/{BRANCH}/{FOLDER_NAME}/{filename}"

# --- ฟังก์ชันแย่งไมค์ ---
def take_thread_control(recipient_id):
    params = {"access_token": PAGE_ACCESS_TOKEN}
    data = {"recipient": {"id": recipient_id}}
    requests.post("https://graph.facebook.com/v19.0/me/take_thread_control", params=params, json=data)

# --- [EDITED] ฟังก์ชันส่งข้อความ (เปลี่ยน TAG เป็น EVENT UPDATE) ---
def send_message(recipient_id, text):
    print(f"💬 Sending: {text}")
    params = {"access_token": PAGE_ACCESS_TOKEN}
    headers = {"Content-Type": "application/json"}
    data = {
        "recipient": {"id": recipient_id},
        "messaging_type": "MESSAGE_TAG",
        "tag": "CONFIRMED_EVENT_UPDATE",      # 👈 เปลี่ยน Tag เป็นอันนี้ หวังผลกับงานพิธี
        "message": {"text": text, "metadata": "BOT_SENT_THIS"}
    }
    r = requests.post("https://graph.facebook.com/v19.0/me/messages", params=params, json=data)
    print(f"👉 FB Result (Text): {r.status_code} - {r.text}")

def send_image(recipient_id, image_url):
    print(f"📤 Sending Image...")
    params = {"access_token": PAGE_ACCESS_TOKEN}
    headers = {"Content-Type": "application/json"}
    data = {
        "recipient": {"id": recipient_id},
        "messaging_type": "MESSAGE_TAG",
        "tag": "CONFIRMED_EVENT_UPDATE",      # 👈 เปลี่ยน Tag เป็นอันนี้
        "message": {
            "attachment": {"type": "image", "payload": {"url": image_url, "is_reusable": True}},
            "metadata": "BOT_SENT_THIS"
        }
    }
    r = requests.post("https://graph.facebook.com/v19.0/me/messages", params=params, json=data)
    print(f"👉 FB Result (Image): {r.status_code} - {r.text}")

# --- 2. LOGIC ---
def process_message(target_id, text, is_admin_sender):
    if not FILES_LOADED:
        update_file_list()

    text_cleaned = text.lower().replace(" ", "")
    pattern = r'(?:269|999)[a-z0-9]{6}'
    valid_format_codes = re.findall(pattern, text_cleaned)
    
    if not valid_format_codes:
        return

    found_actions = [] 
    unknown_codes = []

    for code in valid_format_codes:
        if code in CACHED_FILES:
            found_actions.append((code, CACHED_FILES[code]))
        else:
            if code not in unknown_codes: unknown_codes.append(code)

    # ✅ เจอรูป -> ส่ง
    if found_actions:
        take_thread_control(target_id)
        
        intro_msg = (
            "📸 ขออนุญาตส่งภาพนะครับ\n\n"
            "รวมภาพงานพิธี กดได้ที่ link นี้\n\n"
            " -> linktr.ee/mahabucha\n\n"
            "หรือ รับชมได้ที่หน้าเพจ \"มหาบูชา\"\n\n"
            "ทีมงานเทวาลัยสยามคเณศ ขอขอบคุณครับ"
        )
        send_message(target_id, intro_msg)

        for code_key, filename in found_actions:
            send_message(target_id, f"ภาพถาดถวาย รหัส : {code_key}")
            send_image(target_id, get_image_url(filename))
            
    if is_admin_sender: return 

    if unknown_codes:
        take_thread_control(target_id)
        msg = (
            "⚠️ ขออภัยครับ \n \n"
            "ไม่พบภาพถาดถวายของท่าน \n \n"
            "เนื่องจากถาดของท่านยังไม่ได้รับการถวาย หรือรหัสที่ท่านพิมพ์เข้ามาผิดครับ 🙏"
        )
        send_message(target_id, msg)

# --- 3. WEBHOOK ---
@app.route('/', methods=['GET'])
def verify():
    if request.args.get("hub.mode") == "subscribe" and request.args.get("hub.verify_token") == VERIFY_TOKEN:
        return request.args.get("hub.challenge"), 200
    return "Bot Running", 200

@app.route('/', methods=['POST'])
def webhook():
    data = request.json
    if data['object'] == 'page':
        for entry in data['entry']:
            if 'messaging' in entry:
                for event in entry['messaging']:
                    if 'message' in event:
                        text = event['message'].get('text', '')
                        if event.get('message', {}).get('metadata') == "BOT_SENT_THIS": continue
                        
                        is_echo = event.get('message', {}).get('is_echo', False)
                        if is_echo:
                            if 'recipient' in event and 'id' in event['recipient']:
                                process_message(event['recipient']['id'], text, is_admin_sender=True)
                        else:
                            process_message(event['sender']['id'], text, is_admin_sender=False)
    return "ok", 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
