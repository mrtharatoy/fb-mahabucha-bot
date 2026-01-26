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

# ตัวแปรเก็บรายชื่อไฟล์
CACHED_FILES = []

def update_file_list():
    """ฟังก์ชันวิ่งไปดูรายชื่อไฟล์ทั้งหมดใน GitHub"""
    global CACHED_FILES
    print("🔄 Updating file list from GitHub...")
    api_url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{REPO_NAME}/contents/{FOLDER_NAME}?ref={BRANCH}"
    
    try:
        r = requests.get(api_url)
        if r.status_code == 200:
            data = r.json()
            # ดึงเฉพาะชื่อไฟล์ ตัดนามสกุลทิ้ง
            CACHED_FILES = [item['name'].rsplit('.', 1)[0] for item in data if item['type'] == 'file']
            print(f"📚 Updated! Now have {len(CACHED_FILES)} files.")
            return True
        else:
            print(f"⚠️ Failed to fetch list: {r.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error updating file list: {e}")
        return False

# โหลดครั้งแรกตอนเปิด Server
update_file_list()

def get_github_image_url(filename_without_ext):
    return f"https://raw.githubusercontent.com/{GITHUB_USERNAME}/{REPO_NAME}/{BRANCH}/{FOLDER_NAME}/{filename_without_ext}.jpg"

def find_and_send_images(sender_id, text, file_list):
    """ฟังก์ชันช่วยค้นหาและส่งรูป (แยกออกมาให้เรียกใช้ซ้ำได้)"""
    user_text_lower = text.lower()
    found_count = 0
    
    for filename in file_list:
        if filename.lower() in user_text_lower:
            print(f"✅ Found Keyword: {filename}")
            image_url = get_github_image_url(filename) 
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
                        
                        # รอบที่ 1: ลองหาจากความจำเดิมก่อน
                        found = find_and_send_images(sender_id, text, CACHED_FILES)
                        
                        # ถ้าไม่เจอเลยสักรูป -> ลองอัปเดตรายชื่อไฟล์ใหม่ แล้วหาอีกรอบ
                        if found == 0:
                            print("🤔 Not found in cache. Fetching new list from GitHub...")
                            success = update_file_list()
                            if success:
                                # รอบที่ 2: หาจากรายชื่อใหม่
                                found_retry = find_and_send_images(sender_id, text, CACHED_FILES)
                                if found_retry == 0:
                                    print("❌ Still not found after refresh.")
                            else:
                                print("❌ Could not refresh list.")

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
