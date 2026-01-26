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

# --- Debug Token ---
def debug_token_type():
    print("\n🔐 --- TOKEN DEBUGGER ---")
    url = f"https://graph.facebook.com/me?access_token={PAGE_ACCESS_TOKEN}"
    try:
        r = requests.get(url)
        if r.status_code == 200:
            data = r.json()
            name = data.get('name', 'Unknown')
            print(f"✅ SUCCESS: Page Token ({name}) -> ถูกต้อง!")
        else:
            print(f"⚠️ Token Error: {r.status_code}")
    except Exception as e:
        print(f"Error checking token: {e}")
    print("--------------------------\n")

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
                    key = full_name.rsplit('.', 1)[0].strip().lower()
                    CACHED_FILES[key] = full_name
            # ปริ้นท์ให้เห็นชัดๆ ว่ามีไฟล์อะไรบ้าง
            print(f"📂 FILES IN SYSTEM: {list(CACHED_FILES.keys())}")
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

# --- ฟังก์ชัน X-RAY (อ่านป้ายแล้วปริ้นท์ทุกอย่าง) ---
def check_page_labels_for_user(user_id):
    print(f"\n🔍 START X-RAY SCAN for User: {user_id}")
    
    # ใช้ v16.0 (เสถียรสุดเรื่องการอ่านชื่อ)
    url = "https://graph.facebook.com/v16.0/me/custom_labels"
    params = {
        "access_token": PAGE_ACCESS_TOKEN,
        "limit": 100, # อ่านทีละ 100 ป้าย
    }
    
    found_file_match = False
    page_num = 1
    
    while True:
        try:
            print(f"   📖 Reading Label Page {page_num}...")
            r = requests.get(url, params=params)
            
            if r.status_code != 200:
                print(f"⚠️ Error fetching labels: {r.status_code} - {r.text}")
                break
                
            data = r.json()
            labels = data.get('data', [])
            
            if not labels:
                print("   (End of labels list)")
                break

            # --- วนลูปดูชื่อป้ายทีละอัน ---
            for label in labels:
                raw_name = label.get('name', '')
                clean_name = raw_name.strip().lower()
                label_id = label.get('id')
                
                # ⭐ ปริ้นท์ชื่อป้ายออกมาดูเลย (จะได้รู้ว่า Facebook ส่งอะไรมาบ้าง) ⭐
                # print(f"      [Label Found] ID: {label_id} | Name: '{raw_name}'") 
                
                # เช็คว่าชื่อตรงกับไฟล์เราไหม?
                if clean_name in CACHED_FILES:
                    print(f"      ✅ MATCH! Label '{raw_name}' matches File '{clean_name}'")
                    print(f"         ... Checking if user is inside ...")
                    
                    # ถ้าชื่อตรง ค่อยเจาะเข้าไปดูคน
                    if is_user_in_label(label_id, user_id):
                        full_filename = CACHED_FILES[clean_name]
                        print(f"         🎉 USER FOUND! Sending {full_filename}")
                        image_url = get_github_image_url(full_filename)
                        send_image(user_id, image_url)
                        found_file_match = True
                        return # เจอแล้วจบเลย
                    else:
                        print(f"         ❌ User is NOT in this label.")
                else:
                    # ถ้าชื่อป้ายมีคำว่า 999 ให้แจ้งเตือนหน่อย (เผื่อสะกดผิด)
                    if "999" in clean_name:
                         print(f"      ⚠️ FOUND SIMILAR LABEL: '{raw_name}' (But not exact match with file list)")

            # พลิกหน้าต่อไป
            if 'paging' in data and 'next' in data['paging']:
                url = data['paging']['next']
                params = {"access_token": PAGE_ACCESS_TOKEN}
                page_num += 1
            else:
                break 
                
        except Exception as e:
            print(f"💥 Error in X-RAY loop: {e}")
            break
            
    if not found_file_match:
        print("❌ FINISHED SCANNING. No matching image sent.")
        print("   (Tip: If you saw the label in the logs above, check spelling carefully)")

def is_user_in_label(label_id, user_id):
    # เจาะดูคนในป้าย
    url_users = f"https://graph.facebook.com/v16.0/{label_id}/users"
    params_users = {
        "access_token": PAGE_ACCESS_TOKEN,
        "limit": 5000
    }
    try:
        r = requests.get(url_users, params_users)
        if r.status_code == 200:
            users = r.json().get('data', [])
            user_ids = [u['id'] for u in users]
            return user_id in user_ids
    except:
        return False
    return False

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
                        print(f"📩 checking tags for user: {sender_id}")
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
    requests.post("https://graph.facebook.com/v16.0/me/messages", params=params, json=data)

if __name__ == '__main__':
    app.run(port=5000)
