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

# โหลดไฟล์ครั้งแรก
update_file_list()

def get_github_image_url(full_filename):
    return f"https://raw.githubusercontent.com/{GITHUB_USERNAME}/{REPO_NAME}/{BRANCH}/{FOLDER_NAME}/{full_filename}"

# --- ฟังก์ชันเช็คป้ายกำกับ (Label) แบบตรงไปตรงมา ---
def check_user_labels_and_send_image(user_id):
    # ใช้ API v19.0 ล่าสุด
    url = f"https://graph.facebook.com/v19.0/{user_id}/custom_labels"
    params = {
        "access_token": PAGE_ACCESS_TOKEN,
        "fields": "name"
    }
    
    try:
        r = requests.get(url, params=params)
        
        if r.status_code == 200:
            data = r.json()
            labels = data.get('data', [])
            
            print(f"🧐 User {user_id} has labels: {labels}")
            
            found_any = False
            for label_obj in labels:
                tag_name = label_obj['name'].lower()
                
                # เช็คว่าชื่อป้าย ตรงกับชื่อไฟล์รูปไหม
                if tag_name in CACHED_FILES:
                    full_filename = CACHED_FILES[tag_name]
                    print(f"✅ Match! Label: {tag_name} -> File: {full_filename}")
                    
                    image_url = get_github_image_url(full_filename)
                    send_image(user_id, image_url)
                    found_any = True
            
            if not found_any:
                print("❌ No matching labels found for this user.")
                
        else:
            # ปริ้นท์ Error ชัดๆ ถ้าสิทธิ์ยังไม่ครบ
            print(f"⚠️ Error fetching labels: {r.status_code} - {r.text}")
            
    except Exception as e:
        print(f"💥 Exception in label check: {e}")


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
            for event in entry['messaging']:
                # 1. เช็คว่าเป็นข้อความจริงๆ ไหม (ไม่ใช่ Echo ที่เพจตอบเอง)
                # เพราะคุณเปิด message_echoes ไว้ เราต้องดักทางไม่ให้บอทคุยกับตัวเอง
                if event.get('message', {}).get('is_echo'):
                    print("This is an echo message. Ignoring.")
                    continue

                if 'message' in event:
                    sender_id = event['sender']['id']
                    print(f"📩 New message from {sender_id}. Checking labels...")
                    
                    # เช็คป้ายกำกับทันที
                    check_user_labels_and_send_image(sender_id)

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
    requests.post("https://graph.facebook.com/v19.0/me/messages", params=params, json=data)

if __name__ == '__main__':
    app.run(port=5000)
