import os
import requests
import json
from flask import Flask, request

app = Flask(__name__)

# --- ตั้งค่า GitHub ---
GITHUB_USERNAME = "mrtharatoy"
REPO_NAME = "fb-mahabucha-bot"
BRANCH = "main"
FOLDER_NAME = "images" 
# --------------------

PAGE_ACCESS_TOKEN = os.environ.get('PAGE_ACCESS_TOKEN')
VERIFY_TOKEN = os.environ.get('VERIFY_TOKEN')
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')

CACHED_FILES = {}

# --- Debug Token (เช็คว่า Token ยังไม่หมดอายุ) ---
def debug_token_status():
    print("\n🔐 --- SYSTEM CHECK ---")
    url = f"https://graph.facebook.com/me?access_token={PAGE_ACCESS_TOKEN}"
    try:
        r = requests.get(url)
        if r.status_code == 200:
            print(f"✅ Token Status: Active (Page: {r.json().get('name')})")
        else:
            print(f"⚠️ Token Error: {r.status_code}")
    except:
        pass
    print("----------------------\n")

debug_token_status()

def update_file_list():
    global CACHED_FILES
    print("🔄 Loading file list from GitHub...")
    api_url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{REPO_NAME}/contents/{FOLDER_NAME}?ref={BRANCH}"
    
    headers = {
        "User-Agent": "FB-Mahabucha-Bot",
        "Accept": "application/vnd.github.v3+json"
    }
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
    
    try:
        r = requests.get(api_url, headers=headers)
        if r.status_code == 200:
            data = r.json()
            CACHED_FILES.clear()
            for item in data:
                if item['type'] == 'file':
                    full_name = item['name'] 
                    # ตัดช่องว่าง + ตัวเล็ก เพื่อให้ค้นหาง่าย
                    key = full_name.rsplit('.', 1)[0].strip().lower()
                    CACHED_FILES[key] = full_name
            print(f"📂 READY: Loaded {len(CACHED_FILES)} product codes.")
            return True
        else:
            print(f"⚠️ GitHub Error: {r.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

update_file_list()

def get_github_image_url(full_filename):
    return f"https://raw.githubusercontent.com/{GITHUB_USERNAME}/{REPO_NAME}/{BRANCH}/{FOLDER_NAME}/{full_filename}"

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
    # ใช้ v19.0 (มาตรฐานปัจจุบัน)
    r = requests.post("https://graph.facebook.com/v19.0/me/messages", params=params, json=data)
    if r.status_code != 200:
        print(f"💥 Facebook Send Error: {r.text}")

@app.route('/', methods=['GET'])
def verify():
    if request.args.get("hub.mode") == "subscribe" and request.args.get("hub.challenge"):
        if request.args.get("hub.verify_token") == VERIFY_TOKEN:
            return request.args.get("hub.challenge"), 200
    return "Bot is running!", 200

@app.route('/', methods=['POST'])
def webhook():
    data = request.json
    if data['object'] == 'page':
        for entry in data['entry']:
            if 'messaging' in entry:
                for event in entry['messaging']:
                    # กรองข้อความ Echo (บอทคุยกับตัวเอง)
                    if event.get('message', {}).get('is_echo'):
                        continue
                        
                    if 'message' in event:
                        sender_id = event['sender']['id']
                        # รับข้อความมา แล้วตัดช่องว่างทิ้ง
                        user_text = event['message'].get('text', '').strip().lower()
                        
                        if user_text in CACHED_FILES:
                            full_filename = CACHED_FILES[user_text]
                            print(f"✅ Found Code: '{user_text}' -> Sending {full_filename}")
                            
                            image_url = get_github_image_url(full_filename)
                            send_image(sender_id, image_url)
                        else:
                            # (Optional) ถ้าพิมพ์ผิด ไม่ต้องทำอะไร หรือจะให้ตอบกลับก็ได้
                            print(f"User typed: '{user_text}' (No match)")
                            
    return "ok", 200

if __name__ == '__main__':
    app.run(port=5000)
