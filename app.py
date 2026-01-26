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
            print(f"📂 FILES LOADED: {len(CACHED_FILES)} files ready.")
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
    # ใช้ v24.0 ตามที่คุณมี
    requests.post("https://graph.facebook.com/v24.0/me/messages", params=params, json=data)

# ==========================================
# 1. ระบบพิมพ์หา (Manual Search)
# ==========================================
def check_text_command(user_id, text):
    text_clean = text.strip().lower()
    if text_clean in CACHED_FILES:
        full_filename = CACHED_FILES[text_clean]
        print(f"✅ Text Match: '{text}' -> Sending {full_filename}")
        image_url = get_github_image_url(full_filename)
        send_image(user_id, image_url)
        return True
    return False

# ==========================================
# 2. ระบบหาป้าย (Deep Fetch V24.0)
# ==========================================
def fetch_label_name_by_id(label_id):
    """เจาะถามชื่อป้ายด้วย ID (แก้ปัญหาชื่อว่าง)"""
    url = f"https://graph.facebook.com/v24.0/{label_id}" # ใช้ v24.0
    params = {
        "access_token": PAGE_ACCESS_TOKEN,
        "fields": "name"
    }
    try:
        r = requests.get(url, params=params)
        if r.status_code == 200:
            name = r.json().get('name', '')
            # print(f"      (Deep Fetch Result: ID {label_id} = '{name}')")
            return name
    except:
        pass
    return ''

def check_labels_auto(user_id):
    print(f"🔎 Scanning Labels for {user_id}...") # บรรทัดนี้ต้องขึ้นแน่นอน
    
    url = "https://graph.facebook.com/v24.0/me/custom_labels"
    params = {
        "access_token": PAGE_ACCESS_TOKEN,
        "limit": 100,
        "fields": "name,id"
    }
    
    found = False
    
    while True:
        try:
            r = requests.get(url, params=params)
            data = r.json()
            labels = data.get('data', [])
            
            if not labels: break

            for label in labels:
                raw_name = label.get('name', '')
                label_id = label.get('id')
                
                # ถ้าชื่อว่าง -> เจาะถามใหม่
                if not raw_name:
                    raw_name = fetch_label_name_by_id(label_id)
                
                if not raw_name: continue
                    
                clean_name = raw_name.strip().lower()
                
                # ถ้าเจอชื่อป้ายที่ตรงกับไฟล์
                if clean_name in CACHED_FILES:
                    print(f"   🎯 Potential Tag Found: '{raw_name}' (Checking User...)")
                    
                    if is_user_in_label(label_id, user_id):
                        full_filename = CACHED_FILES[clean_name]
                        print(f"   🎉 USER IS IN TAG: {raw_name} -> Sending Image")
                        image_url = get_github_image_url(full_filename)
                        send_image(user_id, image_url)
                        found = True
                        # ไม่ return แล้ว เพื่อให้มันหาต่อเผื่อมีป้ายอื่น
            
            if 'paging' in data and 'next' in data['paging']:
                url = data['paging']['next']
                params = {"access_token": PAGE_ACCESS_TOKEN}
            else:
                break
                
        except Exception as e:
            print(f"💥 Error scanning labels: {e}")
            break
            
    if not found:
        print("❌ Scan finished. User matches no tags.")

def is_user_in_label(label_id, user_id):
    url = f"https://graph.facebook.com/v24.0/{label_id}/users"
    params = {"access_token": PAGE_ACCESS_TOKEN, "limit": 2000}
    try:
        r = requests.get(url, params)
        if r.status_code == 200:
            ids = [u['id'] for u in r.json().get('data', [])]
            return user_id in ids
    except: pass
    return False

# ==========================================
# MAIN WEBHOOK
# ==========================================
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
                        user_text = event['message'].get('text', '')
                        
                        # --- ทำงานขนาน 2 ระบบ (ไม่บล็อคกันเองแล้ว) ---
                        
                        # 1. ระบบพิมพ์ (ถ้าเจอ ก็ส่ง)
                        check_text_command(sender_id, user_text)
                        
                        # 2. ระบบป้าย (เช็คทุกครั้ง แม้จะพิมพ์ถูกแล้วก็ตาม)
                        check_labels_auto(sender_id)
                            
    return "ok", 200

if __name__ == '__main__':
    app.run(port=5000)
