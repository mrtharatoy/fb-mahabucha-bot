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

# --- ฟังก์ชันตรวจสอบกุญแจ (เพิ่มใหม่) ---
def debug_token_status():
    """เช็คว่า Token ที่ใส่มา เป็นของ Page หรือ User"""
    url = f"https://graph.facebook.com/me?access_token={PAGE_ACCESS_TOKEN}"
    r = requests.get(url)
    if r.status_code == 200:
        data = r.json()
        print(f"🔑 Token Info: ID={data.get('id')}, Name={data.get('name')}")
        # ถ้า Name เป็นชื่อคน -> ผิด (ต้องเป็นชื่อเพจ)
    else:
        print(f"⚠️ Token Error: {r.text}")

# เช็คกุญแจทันทีที่เริ่ม Server
debug_token_status()

def update_file_list():
    """โหลดรายชื่อไฟล์จาก GitHub"""
    global CACHED_FILES
    print("🔄 Updating file list from GitHub...")
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
                    key = full_name.rsplit('.', 1)[0].lower()
                    CACHED_FILES[key] = full_name
            print(f"📚 Updated! Found {len(CACHED_FILES)} files.")
            return True
        else:
            print(f"⚠️ Failed to fetch list: {r.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error updating file list: {e}")
        return False

update_file_list()

def get_github_image_url(full_filename):
    return f"https://raw.githubusercontent.com/{GITHUB_USERNAME}/{REPO_NAME}/{BRANCH}/{FOLDER_NAME}/{full_filename}"

# --- ฟังก์ชันเช็คป้าย (Safe Mode) ---
def check_page_labels_for_user(user_id):
    # ใช้ API v18.0 (เสถียรกว่า) และไม่ระบุ fields name ตรงๆ (ให้มันคืนค่า default)
    url_labels = f"https://graph.facebook.com/v18.0/me/custom_labels"
    params_labels = {
        "access_token": PAGE_ACCESS_TOKEN,
        "fields": "id,name", # ถ้าเป็น Page Token จริง อันนี้จะผ่าน
        "limit": 100
    }
    
    try:
        r = requests.get(url_labels, params=params_labels)
        if r.status_code == 200:
            labels_data = r.json().get('data', [])
            print(f"🧐 Scanning {len(labels_data)} labels...")
            
            found_any = False
            
            for label_obj in labels_data:
                label_name = label_obj.get('name', '').lower()
                label_id = label_obj.get('id')
                
                if label_name in CACHED_FILES:
                    # ดึง ID คนในป้าย
                    url_users = f"https://graph.facebook.com/v18.0/{label_id}/users"
                    params_users = {
                        "access_token": PAGE_ACCESS_TOKEN,
                        "limit": 2000
                        # ไม่ใส่ fields เพื่อเลี่ยงปัญหา name deprecated
                    }
                    
                    r_users = requests.get(url_users, params=params_users)
                    if r_users.status_code == 200:
                        users_data = r_users.json().get('data', [])
                        # users_data จะมีแค่ id (และ name ถ้าอนุญาต) แต่เราสนแค่ id
                        user_ids_in_label = [u['id'] for u in users_data]
                        
                        if user_id in user_ids_in_label:
                            full_filename = CACHED_FILES[label_name]
                            print(f"✅ Match! Tag: '{label_name}' -> Sending: {full_filename}")
                            
                            image_url = get_github_image_url(full_filename)
                            send_image(user_id, image_url)
                            found_any = True
            
            if not found_any:
                print("❌ User not found in matching labels.")
                
        else:
            print(f"⚠️ Error fetching labels: {r.status_code} - {r.text}")
            
    except Exception as e:
        print(f"💥 Exception: {e}")

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
                    if event.get('message', {}).get('is_echo'):
                        continue
                    if 'message' in event:
                        sender_id = event['sender']['id']
                        print(f"📩 Checking labels for {sender_id}...")
                        check_page_labels_for_user(sender_id)
    return "ok", 200

def send_image(recipient_id, image_url):
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
    requests.post("https://graph.facebook.com/v18.0/me/messages", params=params, json=data)

if __name__ == '__main__':
    app.run(port=5000)
