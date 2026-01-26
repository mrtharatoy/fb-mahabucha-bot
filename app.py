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

# --- Debug Token (เช็คครั้งสุดท้าย) ---
def debug_token_type():
    print("\n🔐 --- TOKEN DEBUGGER ---")
    url = f"https://graph.facebook.com/me?access_token={PAGE_ACCESS_TOKEN}"
    try:
        r = requests.get(url)
        if r.status_code == 200:
            data = r.json()
            name = data.get('name', 'Unknown')
            if 'accounts' in r.text or 'first_name' in r.text: 
                print(f"❌ WARNING: User Token (ชื่อ: {name}) -> ใช้ไม่ได้!")
            else:
                print(f"✅ SUCCESS: Page Token (ชื่อ: {name}) -> ใช้ได้แน่นอน!")
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
                    key = full_name.rsplit('.', 1)[0].lower()
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

# --- ฟังก์ชันดึงป้ายทั้งหมด (ใช้ v19.0 + Page Token) ---
def get_all_relevant_labels():
    relevant_labels = []
    
    # กลับมาใช้ v19.0 (เพราะ Token ถูกแล้ว)
    url = "https://graph.facebook.com/v19.0/me/custom_labels"
    
    # เทคนิคสำคัญ: ต้องใส่ access_token ใน params เสมอ แม้ตอนเปลี่ยนหน้า
    params = {
        "access_token": PAGE_ACCESS_TOKEN,
        "limit": 100,
        "fields": "id,name"
    }
    
    print("🔎 Scanning ALL labels (turning pages)...")
    
    while True:
        try:
            r = requests.get(url, params=params)
            if r.status_code != 200:
                print(f"⚠️ Error fetching labels page: {r.status_code} - {r.text}")
                break
                
            data = r.json()
            labels = data.get('data', [])
            
            # กรองเฉพาะป้ายที่ตรงกับไฟล์รูป
            for label in labels:
                label_name = label.get('name', '').lower()
                # print(f"   - Saw label: {label_name}") # เปิดบรรทัดนี้ถ้าอยากเห็นทุกป้าย
                if label_name in CACHED_FILES:
                    relevant_labels.append(label)
                    print(f"   👉 FOUND TARGET LABEL: {label['name']} (ID: {label['id']})")
            
            # พลิกหน้าต่อไป (Pagination)
            if 'paging' in data and 'next' in data['paging']:
                url = data['paging']['next']
                # สำคัญ: url 'next' อาจจะไม่มี access_token ติดมา เราต้องใส่เพิ่มเข้าไป
                params = {"access_token": PAGE_ACCESS_TOKEN}
            else:
                break # หมดหน้าแล้ว
                
        except Exception as e:
            print(f"💥 Error in pagination: {e}")
            break
            
    print(f"✅ Finished scanning. Found {len(relevant_labels)} matching labels.")
    return relevant_labels

def check_page_labels_for_user(user_id):
    # 1. หาป้ายที่ชื่อตรงกับรูปมาก่อน
    target_labels = get_all_relevant_labels()
    
    if not target_labels:
        print("❌ No labels match our file list. (Customer might have Ad labels only)")
        return

    found_any = False
    
    # 2. เจาะดูทีละป้าย ว่ามีลูกค้าคนนี้อยู่ไหม
    for label_obj in target_labels:
        label_name = label_obj.get('name', '').lower()
        label_id = label_obj.get('id')
        
        print(f"🧐 Checking inside label '{label_name}'...")
        
        # ใช้ v19.0 เจาะดูคน
        url_users = f"https://graph.facebook.com/v19.0/{label_id}/users"
        params_users = {
            "access_token": PAGE_ACCESS_TOKEN,
            "limit": 5000, # ดึงมาเยอะๆ เลย
            "fields": "id"
        }
        
        try:
            r_users = requests.get(url_users, params=params_users)
            if r_users.status_code == 200:
                users_data = r_users.json().get('data', [])
                user_ids = [u['id'] for u in users_data]
                
                # เช็คว่าลูกค้าเราอยู่ในนั้นไหม
                if user_id in user_ids:
                    full_filename = CACHED_FILES[label_name]
                    print(f"🎉 BINGO! User {user_id} found in tag '{label_name}'")
                    print(f"📤 Sending image: {full_filename}")
                    
                    image_url = get_github_image_url(full_filename)
                    send_image(user_id, image_url)
                    found_any = True
                    break # เจอแล้วหยุดเลย (หรือเอาออกถ้าอยากให้ส่งหลายรูป)
                else:
                    print(f"   User not in this label (Total people in label: {len(users_data)})")
            else:
                print(f"⚠️ Failed to check users: {r_users.status_code}")
                
        except Exception as e:
            print(f"💥 Error checking users: {e}")

    if not found_any:
        print("❌ User checked against candidate labels, but not found.")

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
    requests.post("https://graph.facebook.com/v19.0/me/messages", params=params, json=data)

if __name__ == '__main__':
    app.run(port=5000)
