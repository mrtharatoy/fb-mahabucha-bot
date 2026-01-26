import os
import requests
import json
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
                    # เก็บชื่อไฟล์เป็นตัวเล็ก ตัดช่องว่าง
                    key = item['name'].rsplit('.', 1)[0].strip().lower()
                    CACHED_FILES[key] = item['name']
            print(f"📂 FILES READY: {len(CACHED_FILES)} images.")
    except Exception as e:
        print(f"❌ Error: {e}")

update_file_list()

def get_image_url(filename):
    return f"https://raw.githubusercontent.com/{GITHUB_USERNAME}/{REPO_NAME}/{BRANCH}/{FOLDER_NAME}/{filename}"

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
            }
        }
    }
    requests.post("https://graph.facebook.com/v19.0/me/messages", params=params, json=data)

# --- 2. WEBHOOK หลัก ---
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
                    
                    # --- ส่วนสำคัญ: รับทั้งข้อความลูกค้า และ แอดมิน ---
                    if 'message' in event:
                        text = event['message'].get('text', '').strip().lower()
                        
                        # หาคนที่จะรับรูป (ถ้าเป็น Echo ให้ส่งกลับไปหาคนที่เราคุยด้วย)
                        if event.get('message', {}).get('is_echo'):
                            # กรณีแอดมินพิมพ์: recipient_id คือลูกค้า
                            recipient_id = event['recipient']['id']
                            print(f"👮 Admin typed: {text} -> To Customer: {recipient_id}")
                        else:
                            # กรณีลูกค้าพิมพ์: sender_id คือลูกค้า
                            recipient_id = event['sender']['id']
                            print(f"👤 User typed: {text}")

                        # --- เช็คว่าข้อความตรงกับรหัสรูปไหม ---
                        if text in CACHED_FILES:
                            full_filename = CACHED_FILES[text]
                            print(f"✅ MATCH FOUND! Sending {full_filename}")
                            image_url = get_image_url(full_filename)
                            send_image(recipient_id, image_url)
                        
    return "ok", 200

if __name__ == '__main__':
    app.run(port=5000)
