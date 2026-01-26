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
            if 'accounts' in r.text or 'first_name' in r.text: 
                print(f"❌ WARNING: User Token ({name}) -> ใช้ไม่ได้!")
            else:
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
                    # ตัดช่องว่าง + ตัวเล็ก
                    key = full_name.rsplit('.', 1)[0].strip().lower()
                    CACHED_FILES[key] = full_name
            print(f"📚 Updated! Found {len(CACHED_FILES)} files: {list(CACHED_FILES.keys())}")
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

# --- ฟังก์ชันดึงป้าย (Spy Mode + Auto Trim) ---
def get_all_relevant_labels():
    relevant_labels = []
    url = "https://graph.facebook.com/v16.0/me/custom_labels"
    params = {
        "access_token": PAGE_ACCESS_TOKEN,
        "limit": 100,
    }
    
    print("🔎 Scanning ALL labels (Showing everything)...")
    
    page_count = 1
    while True:
        try:
            print(f"   📖 Reading Page {page_count}...")
            r = requests.get(url, params=params)
            
            if r.status_code != 200:
                print(f"⚠️ Error fetching labels: {r.status_code} - {r.text}")
                break
                
            data = r.json()
            labels = data.get('data', [])
            
            if not labels:
                print("   (This page is empty)")
            
            for label in labels:
                raw_name = label.get('name', '')
                # ⭐ แก้ไขจุดตาย: ตัดช่องว่างหน้าหลังทิ้ง (.strip) ⭐
                clean_name = raw_name.strip().lower()
                
                # ปริ้นท์ให้เห็นกับตาว่าบอทเห็นอะไร
                # print(f"   👀 Saw: '{raw_name}' -> Clean: '{clean_name}'") 
                
                if clean_name in CACHED_FILES:
                    relevant_labels.append(label)
                    print(f"   👉 MATCH FOUND!: '{raw_name}' matches file '{clean_name}'")
                # else:
                    # ถ้าอยากเห็นว่าอันไหนไม่ตรง ให้เปิดบรรทัดนี้
                    # print(f"      Mismatch: '{clean_name}' not in file list.")

            if 'paging' in data and 'next' in data['paging']:
                url = data['paging']['next']
                params = {"access_token": PAGE_ACCESS_TOKEN}
                page_count += 1
            else:
                break 
                
        except Exception as e:
            print(f"💥 Error in pagination: {e}")
            break
            
    print(f"✅ Finished scanning. Found {len(relevant_labels)} matching labels.")
    return relevant_labels

def check_page_labels_for_user(user_id):
    target_labels = get_all_relevant_labels()
    
    if not target_labels:
        print("❌ No labels match our file list. (Check exact spelling/spaces)")
        return

    found_any = False
    
    for label_obj in target_labels:
        # ตัดช่องว่างอีกทีเพื่อความชัวร์
        clean_name = label_obj.get('name', '').strip().lower()
        label_id = label_obj.get('id')
        
        print(f"🧐 Checking inside label '{clean_name}'...")
        
        url_users = f"https://graph.facebook.com/v16.0/{label_id}/users"
        params_users = {
            "access_token": PAGE_ACCESS_TOKEN,
            "limit": 5000
        }
        
        try:
            r_users = requests.get(url_users, params=params_users)
            if r_users.status_code == 200:
                users_data = r_users.json().get('data', [])
                user_ids = [u['id'] for u in users_data]
                
                # Debug: ปริ้นท์ ID ของคนในป้ายออกมาดู
                # print(f"   People inside: {user_ids}") 
                
                if user_id in user_ids:
                    full_filename = CACHED_FILES[clean_name]
                    print(f"🎉 BINGO! User {user_id} IS in tag '{clean_name}'")
                    
                    image_url = get_github_image_url(full_filename)
                    send_image(user_id, image_url)
                    found_any = True
                    break 
                else:
                    print(f"   User {user_id} is NOT in this label.")
            else:
                print(f"⚠️ Failed to check users: {r_users.status_code}")
                
        except Exception as e:
            print(f"💥 Error checking users: {e}")

    if not found_any:
        print("❌ User checked against matching labels, but is not in the list.")

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
                        print(f"📩 Checking tags for user: {sender_id}")
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
