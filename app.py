import os
import requests
import re
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

# --- 1. โหลดรายชื่อรูป ---
def update_file_list():
    global CACHED_FILES
    print("🔄 Loading file list...")
    api_url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{REPO_NAME}/contents/{FOLDER_NAME}?ref={BRANCH}"
    headers = {"User-Agent": "Bot", "Accept": "application/vnd.github.v3+json"}
    if GITHUB_TOKEN: headers["Authorization"] = f"token {GITHUB_TOKEN}"
    
    try:
        r = requests.get(api_url, headers=headers)
        if r.status_code == 200:
            data = r.json()
            CACHED_FILES.clear()
            for item in data:
                if item['type'] == 'file':
                    key = item['name'].rsplit('.', 1)[0].strip().lower()
                    CACHED_FILES[key] = item['name']
            print(f"📂 FILES READY: {len(CACHED_FILES)} images.")
    except Exception as e:
        print(f"❌ Error: {e}")

update_file_list()

def get_image_url(filename):
    return f"https://raw.githubusercontent.com/{GITHUB_USERNAME}/{REPO_NAME}/{BRANCH}/{FOLDER_NAME}/{filename}"

# --- [NEW] ฟังก์ชันแย่งไมค์ (Take Thread Control) ---
def take_thread_control(recipient_id):
    print(f"🎤 Attempting to take thread control for {recipient_id}...")
    params = {"access_token": PAGE_ACCESS_TOKEN}
    headers = {"Content-Type": "application/json"}
    data = {"recipient": {"id": recipient_id}}
    
    # ยิงคำสั่งขอสิทธิ์พูด
    r = requests.post("https://graph.facebook.com/v19.0/me/take_thread_control", params=params, json=data)
    print(f"👉 Control Result: {r.status_code} - {r.text}")

# --- ฟังก์ชันส่งข้อความ (พร้อมปริ้น Error) ---
def send_message(recipient_id, text):
    print(f"💬 Sending message to {recipient_id}: {text}")
    params = {"access_token": PAGE_ACCESS_TOKEN}
    headers = {"Content-Type": "application/json"}
    data = {
        "recipient": {"id": recipient_id},
        "message": {
            "text": text,
            "metadata": "BOT_SENT_THIS"
        }
    }
    r = requests.post("https://graph.facebook.com/v19.0/me/messages", params=params, json=data)
    print(f"👉 FB RESPONSE (Text): {r.status_code} - {r.text}") # ดู Error ตรงนี้

def send_image(recipient_id, image_url):
    print(f"📤 Sending image to {recipient_id}...")
    params = {"access_token": PAGE_ACCESS_TOKEN}
    headers = {"Content-Type": "application/json"}
    data = {
        "recipient": {"id": recipient_id},
        "message": {
            "attachment": {
                "type": "image",
                "payload": {"url": image_url, "is_reusable": True}
            },
            "metadata": "BOT_SENT_THIS"
        }
    }
    r = requests.post("https://graph.facebook.com/v19.0/me/messages", params=params, json=data)
    print(f"👉 FB RESPONSE (Image): {r.status_code} - {r.text}") # ดู Error ตรงนี้

# --- 2. LOGIC วิเคราะห์ข้อความ ---
def process_message(target_id, text, is_admin_sender):
    text_cleaned = text.lower().replace(" ", "")
    
    pattern = r'(?:269|999)[a-z0-9]{6}'
    valid_format_codes = re.findall(pattern, text_cleaned)
    
    if not valid_format_codes:
        # ไม่เจอรหัส -> จบการทำงานเงียบๆ
        return

    found_actions = [] 
    unknown_codes = []

    for code in valid_format_codes:
        if code in CACHED_FILES:
            full_filename = CACHED_FILES[code]
            if (code, full_filename) not in found_actions:
                found_actions.append((code, full_filename))
        else:
            if code not in unknown_codes:
                unknown_codes.append(code)

    # ✅ เจอรูป -> ส่ง
    if found_actions:
        # 🔥 [สำคัญ] แย่งไมค์ก่อนส่ง! (เฉพาะตอนเจอรูป)
        take_thread_control(target_id)
        # ----------------------------------------

        intro_msg = (
            "📸 ขออนุญาตส่งภาพนะครับ\n\n"
            "รวมภาพงานพิธี กดได้ที่ link นี้\n\n"
            " -> linktr.ee/mahabucha\n\n"
            "หรือ รับชมได้ที่หน้าเพจ \"มหาบูชา\"\n\n"
            "ทีมงานเทวาลัยสยามคเณศ ขอขอบคุณครับ"
        )
        send_message(target_id, intro_msg)

        for code_key, filename in found_actions:
            print(f"✅ Code found ({code_key}) -> Sending to {target_id}")
            msg = f"ภาพถาดถวาย รหัส : {code_key}"
            send_message(target_id, msg)
            send_image(target_id, get_image_url(filename))
            
    if is_admin_sender:
        return 

    # ⚠️ แจ้งเตือน (กรณีหาไม่เจอ)
    if unknown_codes:
        # ก็ต้องแย่งไมค์ก่อนแจ้งเตือนเหมือนกัน
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
                        
                        if event.get('message', {}).get('metadata') == "BOT_SENT_THIS":
                            continue

                        is_echo = event.get('message', {}).get('is_echo', False)
                        
                        if is_echo:
                            # Admin พิมพ์
                            if 'recipient' in event and 'id' in event['recipient']:
                                target_id = event['recipient']['id']
                                print(f"👮 Admin typed: {text}")
                                process_message(target_id, text, is_admin_sender=True)
                        else:
                            # ลูกค้าพิมพ์
                            target_id = event['sender']['id']
                            print(f"👤 User typed: {text}")
                            process_message(target_id, text, is_admin_sender=False)
                        
    return "ok", 200

if __name__ == '__main__':
    app.run(port=5000)
