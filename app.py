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

# เปลี่ยนวิธีเก็บข้อมูล: เก็บเป็นคู่ { 'รหัส(ตัวเล็ก)': 'ชื่อไฟล์เต็มๆ' }
# เช่น { '999aa01': '999AA01.JPG' }
CACHED_FILES = {}

def update_file_list():
    """โหลดรายชื่อไฟล์และจำนามสกุลที่ถูกต้อง"""
    global CACHED_FILES
    print("🔄 Updating file list from GitHub...")
    api_url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{REPO_NAME}/{contents}/{FOLDER_NAME}?ref={BRANCH}"
    
    # แก้ไข URL api ให้ถูกต้อง (เอา /contents/ ใส่คืนให้)
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
            CACHED_FILES.clear() # ล้างของเก่า
            
            for item in data:
                if item['type'] == 'file':
                    full_name = item['name'] # ชื่อไฟล์จริง เช่น 999AA01.JPG
                    # สร้างกุญแจสำหรับค้นหา (ตัดนามสกุลทิ้ง + ทำเป็นตัวเล็ก)
                    key = full_name.rsplit('.', 1)[0].lower()
                    CACHED_FILES[key] = full_name
            
            print(f"📚 Updated! Found {len(CACHED_FILES)} files.")
            # print(f"   Debug List: {CACHED_FILES}") # เปิดดูถ้าอยากเห็นรายการ
            return True
        else:
            print(f"⚠️ Failed to fetch list: {r.status_code} - {r.text}")
            return False
    except Exception as e:
        print(f"❌ Error updating file list: {e}")
        return False

# โหลดครั้งแรก
update_file_list()

def get_github_image_url(full_filename):
    # สร้างลิงก์จากชื่อไฟล์จริงๆ (รวมนามสกุล)
    return f"https://raw.githubusercontent.com/{GITHUB_USERNAME}/{REPO_NAME}/{BRANCH}/{FOLDER_NAME}/{full_filename}"

def find_and_send_images(sender_id, text):
    user_text_lower = text.lower()
    found_count = 0
    
    # วนลูปเช็คจาก Dictionary โดยตรง
    for key, full_filename in CACHED_FILES.items():
        if key in user_text_lower:
            print(f"✅ Found Keyword: {key} -> File: {full_filename}")
            image_url = get_github_image_url(full_filename) 
            send_image(sender_id, image_url)
            found_count += 1
            
    return found_count

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
                if 'message' in event:
                    sender_id = event['sender']['id']
                    if 'text' in event['message']:
                        text = event['message']['text']
                        print(f"📩 User Said: '{text}'")
                        
                        found = find_and_send_images(sender_id, text)
                        
                        if found == 0:
                            print("🤔 Not found. Fetching new list...")
                            success = update_file_list()
                            if success:
                                find_and_send_images(sender_id, text)
                            else:
                                print("❌ Still failing to fetch list.")

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
    # เพิ่มการปริ้นท์ผลลัพธ์จาก Facebook เพื่อดู Error
    r = requests.post("https://graph.facebook.com/v18.0/me/messages", params=params, json=data)
    if r.status_code != 200:
        print(f"💥 Facebook Error: {r.status_code}")
        print(f"   Response: {r.text}")
    else:
        print(f"📤 Sent to FB successfully: {image_url}")

if __name__ == '__main__':
    app.run(port=5000)
