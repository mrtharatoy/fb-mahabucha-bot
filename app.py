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

# --- ฟังก์ชันใหม่: แยกการทำงานเป็น 2 ขยัก (แก้ Error #12) ---
def check_page_labels_for_user(user_id):
    # 1. ดึงเฉพาะ "ชื่อป้าย" มาก่อน (ยังไม่ดึงคน)
    url_labels = f"https://graph.facebook.com/v19.0/me/custom_labels"
    params_labels = {
        "access_token": PAGE_ACCESS_TOKEN,
        "fields": "id,name", # ขอแค่ ID กับ ชื่อป้าย
        "limit": 100
    }
    
    try:
        r = requests.get(url_labels, params=params_labels)
        if r.status_code == 200:
            labels_data = r.json().get('data', [])
            print(f"🧐 Scanning {len(labels_data)} labels on Page...")
            
            found_any = False
            
            # 2. วนลูปเช็คทีละป้าย
            for label_obj in labels_data:
                label_name = label_obj.get('name', '').lower()
                label_id = label_obj.get('id')
                
                # ถ้าป้ายนี้ "ชื่อตรงกับไฟล์รูป" เท่านั้น เราถึงจะยอมเสียเวลาเข้าไปเช็คคน
                if label_name in CACHED_FILES:
                    print(f"🎯 Found relevant label: {label_name} (Checking if user is in here...)")
                    
                    # 3. เจาะดูคนในป้ายนี้ (ขอแค่ ID ไม่เอาชื่อ)
                    url_users = f"https://graph.facebook.com/v19.0/{label_id}/users"
                    params_users = {
                        "access_token": PAGE_ACCESS_TOKEN,
                        "fields": "id", # <--- หัวใจสำคัญ! ระบุชัดๆ ว่าเอาแค่ ID ห้ามเอา name
                        "limit": 2000
                    }
                    
                    r_users = requests.get(url_users, params=params_users)
                    if r_users.status_code == 200:
                        users_data = r_users.json().get('data', [])
                        user_ids_in_label = [u['id'] for u in users_data]
                        
                        # เช็คว่าลูกค้าเรา อยู่ในลิสต์นี้ไหม
                        if user_id in user_ids_in_label:
                            full_filename = CACHED_FILES[label_name]
                            print(f"✅ Match Confirmed! User is in tag '{label_name}' -> Sending {full_filename}")
                            
                            image_url = get_github_image_url(full_filename)
                            send_image(user_id, image_url)
                            found_any = True
                            # เจอแล้วหยุดเลยไหม? หรือจะหาต่อเผื่อมีหลายป้าย (ผมปล่อยให้หาต่อครับ)
                            
                    else:
                        print(f"⚠️ Error fetching users for label {label_name}: {r_users.status_code}")

            if not found_any:
                print("❌ User not found in any matching labels.")
                
        else:
            print(f"⚠️ Error fetching labels list: {r.status_code} - {r.text}")
            
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
            if 'messaging' in entry:
                for event in entry['messaging']:
                    # ป้องกัน Echo
                    if event.get('message', {}).get('is_echo'):
                        continue

                    if 'message' in event:
                        sender_id = event['sender']['id']
                        print(f"📩 Message from {sender_id}. Checking Page Labels...")
                        
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
