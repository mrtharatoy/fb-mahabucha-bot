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
                    # เก็บชื่อไฟล์เป็นตัวเล็ก ตัดนามสกุล
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

# --- ฟังก์ชันใหม่: ดึง Tag ผ่านห้องแชท (Conversation API) ---
def check_user_labels_and_send_image(user_id):
    """
    1. หา ID ห้องแชท (Conversation ID) ของลูกค้าคนนี้ก่อน
    2. เข้าไปดูในห้องแชทว่ามี tags (ป้ายกำกับ) อะไรบ้าง
    """
    
    # 1. หา Conversation ID
    conv_url = f"https://graph.facebook.com/v18.0/me/conversations"
    conv_params = {
        "access_token": PAGE_ACCESS_TOKEN,
        "user_id": user_id,
        "platform": "MESSENGER"
    }
    
    try:
        r = requests.get(conv_url, params=conv_params)
        if r.status_code == 200:
            data = r.json()
            if 'data' in data and len(data['data']) > 0:
                conversation_id = data['data'][0]['id']
                print(f"🔍 Found Conversation ID: {conversation_id}")
                
                # 2. เอา Conversation ID ไปถามหา Tags
                tags_url = f"https://graph.facebook.com/v18.0/{conversation_id}"
                tags_params = {
                    "access_token": PAGE_ACCESS_TOKEN,
                    "fields": "tags" # ขอข้อมูล tags
                }
                
                r_tags = requests.get(tags_url, params=tags_params)
                if r_tags.status_code == 200:
                    tags_data = r_tags.json()
                    
                    # เช็คว่ามี tags ไหม
                    if 'tags' in tags_data and 'data' in tags_data['tags']:
                        labels = tags_data['tags']['data']
                        print(f"🏷️ Found Labels: {labels}")
                        
                        found_any = False
                        for label in labels:
                            tag_name = label['name'].lower()
                            
                            # เทียบกับชื่อไฟล์ที่เรามี
                            if tag_name in CACHED_FILES:
                                full_filename = CACHED_FILES[tag_name]
                                print(f"✅ Match Found! Tag: {tag_name} -> File: {full_filename}")
                                image_url = get_github_image_url(full_filename)
                                send_image(user_id, image_url)
                                found_any = True
                        
                        if not found_any:
                            print("❌ User has tags, but no matching images.")
                    else:
                        print("❌ No tags found in this conversation.")
                else:
                    print(f"⚠️ Error fetching tags: {r_tags.text}")
            else:
                print("❌ Could not find conversation for this user.")
        else:
            print(f"⚠️ Error finding conversation: {r.status_code} - {r.text}")
            
    except Exception as e:
        print(f"💥 Error checking labels: {e}")


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
                    
                    print(f"📩 Message from {sender_id}. Checking tags...")
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
    requests.post("https://graph.facebook.com/v18.0/me/messages", params=params, json=data)

if __name__ == '__main__':
    app.run(port=5000)
