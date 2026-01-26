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

# --- ฟังก์ชันใหม่: ดึง Tag จาก 'เพจ' แทนดึงจาก 'ลูกค้า' (แก้ Error 400) ---
def check_page_labels_for_user(user_id):
    """
    1. ดึงป้ายกำกับทั้งหมดของเพจ พร้อมรายชื่อคนในป้ายนั้น
    2. เช็คว่า user_id ของเรา ไปโผล่อยู่ในป้ายไหนบ้าง
    """
    # API: ขอป้ายทั้งหมด (name) และขอรายชื่อคนในป้าย (users)
    url = f"https://graph.facebook.com/v19.0/me/custom_labels"
    params = {
        "access_token": PAGE_ACCESS_TOKEN,
        "fields": "name,users", 
        "limit": 100 # ดึงมาทีละ 100 ป้าย (ถ้ามีเยอะกว่านี้อาจต้องวนลูปเพิ่ม)
    }
    
    try:
        r = requests.get(url, params=params)
        if r.status_code == 200:
            data = r.json()
            labels_data = data.get('data', [])
            
            print(f"🧐 Scanning {len(labels_data)} labels from Page...")
            
            found_any = False
            
            # วนดูทุกป้ายในเพจ
            for label_obj in labels_data:
                label_name = label_obj.get('name', '').lower()
                
                # ถ้าป้ายนี้ชื่อตรงกับไฟล์รูปที่เรามี
                if label_name in CACHED_FILES:
                    # เช็คว่าลูกค้าคนนี้ (user_id) อยู่ในป้ายนี้ไหม?
                    users_in_label = label_obj.get('users', {}).get('data', [])
                    
                    # แปลง list ของ users ให้เป็น list ของ id ล้วนๆ เพื่อเช็คง่ายๆ
                    user_ids_in_label = [u['id'] for u in users_in_label]
                    
                    if user_id in user_ids_in_label:
                        full_filename = CACHED_FILES[label_name]
                        print(f"✅ Match Found! User is in label '{label_name}' -> File: {full_filename}")
                        
                        image_url = get_github_image_url(full_filename)
                        send_image(user_id, image_url)
                        found_any = True
            
            if not found_any:
                print("❌ User not found in any matching labels.")
                
        else:
            print(f"⚠️ Error fetching page labels: {r.status_code} - {r.text}")
            
    except Exception as e:
        print(f"💥 Exception checking labels: {e}")


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
                # ป้องกัน Echo (คุยกับตัวเอง)
                if event.get('message', {}).get('is_echo'):
                    print("Ignored echo.")
                    continue

                if 'message' in event:
                    sender_id = event['sender']['id']
                    print(f"📩 Message from {sender_id}. Checking Page Labels...")
                    
                    # ใช้ฟังก์ชันใหม่ที่เข้าทางประตูหลัง
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
    requests.post("https://graph.facebook.com/v19.0/me/messages", params=params, json=data)

if __name__ == '__main__':
    app.run(port=5000)
