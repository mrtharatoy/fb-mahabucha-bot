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

# ⭐ ฟังก์ชันเช็คกุญแจ (จะทำงานทันทีที่เริ่มระบบ) ⭐
def debug_token_type():
    print("\n🔐 --- TOKEN DEBUGGER ---")
    url = f"https://graph.facebook.com/me?access_token={PAGE_ACCESS_TOKEN}"
    try:
        r = requests.get(url)
        if r.status_code == 200:
            data = r.json()
            name = data.get('name', 'Unknown')
            id = data.get('id', 'Unknown')
            # เช็คว่า Metadata บอกว่าเป็น User หรือ Page
            if 'accounts' in r.text or 'first_name' in r.text: 
                print(f"❌ WARNING: คุณกำลังใช้ 'User Token' (ชื่อ: {name})")
                print("👉 กุญแจนี้ใช้ดึงป้ายกำกับไม่ได้! กรุณาไปเปลี่ยนเป็น Page Token")
            else:
                print(f"✅ SUCCESS: คุณกำลังใช้ 'Page Token' (ชื่อ: {name})")
                print("👉 กุญแจนี้ถูกต้อง! พร้อมใช้งาน")
        else:
            print(f"⚠️ Token Error: ใช้งานไม่ได้ ({r.status_code})")
    except Exception as e:
        print(f"Error checking token: {e}")
    print("--------------------------\n")

# รันตรวจสอบทันที
debug_token_type()

def update_file_list():
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

# --- ฟังก์ชันเช็คป้าย (Page Labels) ---
def check_page_labels_for_user(user_id):
    # ใช้ API v19.0 (ต้องใช้ Page Token เท่านั้นถึงจะผ่านจุดนี้)
    url_labels = f"https://graph.facebook.com/v19.0/me/custom_labels"
    params_labels = {
        "access_token": PAGE_ACCESS_TOKEN,
        "fields": "id,name", 
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
                
                # ถ้าชื่อป้าย ตรงกับชื่อไฟล์รูป
                if label_name in CACHED_FILES:
                    # เจาะดูคนในป้าย (ขอแค่ ID)
                    url_users = f"https://graph.facebook.com/v19.0/{label_id}/users"
                    params_users = {
                        "access_token": PAGE_ACCESS_TOKEN,
                        "limit": 2000,
                        "fields": "id" # เอาแค่ ID เพื่อความชัวร์
                    }
                    
                    r_users = requests.get(url_users, params=params_users)
                    if r_users.status_code == 200:
                        users_data = r_users.json().get('data', [])
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
    requests.post("https://graph.facebook.com/v19.0/me/messages", params=params, json=data)

if __name__ == '__main__':
    app.run(port=5000)
