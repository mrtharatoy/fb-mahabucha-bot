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

# ==========================================
# 🕵️‍♂️ METHOD 1: Custom Labels (เพิ่ม fields=name,id)
# ==========================================
def check_custom_labels(user_id):
    print(f"   [Method 1] Scanning Custom Labels API...")
    url = "https://graph.facebook.com/v16.0/me/custom_labels"
    
    # ⭐ จุดแก้ที่ 1: บังคับขอ name และ id ⭐
    params = {
        "access_token": PAGE_ACCESS_TOKEN, 
        "limit": 100,
        "fields": "name,id" 
    }
    
    while True:
        try:
            r = requests.get(url, params=params)
            data = r.json()
            labels = data.get('data', [])
            
            if not labels: break

            for label in labels:
                # ปริ้นท์ข้อมูลดิบดูเลยว่า Facebook ส่งอะไรมา
                # print(f"      RAW DATA: {label}") 
                
                raw_name = label.get('name', 'NO_NAME')
                clean_name = raw_name.strip().lower()
                
                print(f"      - Found Label: '{raw_name}'") 
                
                if clean_name in CACHED_FILES:
                    # เจาะดูคน
                    label_id = label.get('id')
                    if is_user_in_label(label_id, user_id):
                        return clean_name
            
            if 'paging' in data and 'next' in data['paging']:
                url = data['paging']['next']
                # ⭐ จุดแก้ที่ 2: หน้าถัดไปก็ต้องบังคับขอ name ด้วย ⭐
                params = {"access_token": PAGE_ACCESS_TOKEN, "fields": "name,id"}
            else:
                break
        except Exception as e:
            print(f"      💥 Method 1 Error: {e}")
            break
    return None

def is_user_in_label(label_id, user_id):
    url = f"https://graph.facebook.com/v16.0/{label_id}/users"
    params = {"access_token": PAGE_ACCESS_TOKEN, "limit": 2000}
    try:
        r = requests.get(url, params)
        if r.status_code == 200:
            ids = [u['id'] for u in r.json().get('data', [])]
            return user_id in ids
    except: pass
    return False

# ==========================================
# 🕵️‍♂️ METHOD 2: Conversation Tags (เพิ่ม debug)
# ==========================================
def check_conversation_tags(user_id):
    print(f"   [Method 2] Scanning Inbox Conversation Tags...")
    
    url_conv = f"https://graph.facebook.com/v16.0/me/conversations"
    params_conv = {
        "access_token": PAGE_ACCESS_TOKEN,
        "platform": "MESSENGER",
        "user_id": user_id
    }
    
    try:
        r = requests.get(url_conv, params=params_conv)
        data = r.json()
        
        # Debug: ดูว่าหาห้องแชทเจอไหม
        if 'error' in data:
            print(f"      ⚠️ Conversation API Error: {data['error']['message']}")
            
        if 'data' in data and len(data['data']) > 0:
            conv_id = data['data'][0]['id']
            # print(f"      Found Conv ID: {conv_id}")
            
            url_tags = f"https://graph.facebook.com/v16.0/{conv_id}"
            params_tags = {
                "access_token": PAGE_ACCESS_TOKEN,
                "fields": "tags"
            }
            r_tags = requests.get(url_tags, params=params_tags)
            tags_data = r_tags.json().get('tags', {}).get('data', [])
            
            if not tags_data:
                print("      (No tags found attached to this conversation)")
            
            for tag in tags_data:
                raw_name = tag.get('name', 'NO_NAME')
                clean_name = raw_name.strip().lower()
                print(f"      - Found Chat Tag: '{raw_name}'")
                
                if clean_name in CACHED_FILES:
                    return clean_name 
        else:
            print("      ⚠️ Could not find conversation ID for this user (User might be inactive).")
            
    except Exception as e:
        print(f"      💥 Method 2 Error: {e}")
        
    return None

# ==========================================
# MAIN
# ==========================================
def master_check_and_send(user_id):
    print(f"\n🚀 STARTING SEARCH for User: {user_id}")
    
    matched_file = check_custom_labels(user_id)
    
    if not matched_file:
        matched_file = check_conversation_tags(user_id)
        
    if matched_file:
        full_filename = CACHED_FILES[matched_file]
        print(f"🎉 SUCCESS! Match found: '{matched_file}' -> Sending {full_filename}")
        image_url = get_github_image_url(full_filename)
        send_image(user_id, image_url)
    else:
        print("❌ FAILED. No matching tags found in either system.")

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
                        master_check_and_send(sender_id)
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
