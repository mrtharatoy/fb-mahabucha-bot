import os
import requests
import re # เพิ่มโมดูล Regex สำหรับจับแพทเทิร์นรหัส
from flask import Flask, request

app = Flask(__name__)

# --- CONFIG ---
GITHUB_USERNAME = "mrtharatoy"
REPO_NAME = "fb-mahabucha-bot"
BRANCH = "main"
FOLDER_NAME = "images" 
PAGE_ACCESS_TOKEN = os.environ.get('PAGE_ACCESS_TOKEN')
VERIFY_TOKEN = os.environ.get('VERIFY_TOKEN')
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')

CACHED_FILES = {}

# --- 1. โหลดรายชื่อรูป ---
def update_file_list():
    global CACHED_FILES
    print("🔄 Loading file list...")
    api_url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{REPO_NAME}/contents/{FOLDER_NAME}?ref={BRANCH}"
    headers = {"User-Agent": "Bot", "Accept": "application/vnd.github.v3+json"}
    if GITHUB_TOKEN: headers["Authorization"] = f"token {GITHUB_TOKEN}"
    
    try:
        r = requests.get(api_url, headers=headers)
        if r.status_code == 200:
            data = r.json()
            CACHED_FILES.clear()
            for item in data:
                if item['type'] == 'file':
                    # เก็บชื่อไฟล์เป็นตัวเล็ก ตัดช่องว่าง
                    key = item['name'].rsplit('.', 1)[0].strip().lower()
                    CACHED_FILES[key] = item['name']
            print(f"📂 FILES READY: {len(CACHED_FILES)} images.")
    except Exception as e:
        print(f"❌ Error: {e}")

update_file_list()

def get_image_url(filename):
    return f"https://raw.githubusercontent.com/{GITHUB_USERNAME}/{REPO_NAME}/{BRANCH}/{FOLDER_NAME}/{filename}"

def send_message(recipient_id, text):
    """ฟังก์ชันส่งข้อความตัวอักษร"""
    print(f"💬 Sending message to {recipient_id}: {text}")
    params = {"access_token": PAGE_ACCESS_TOKEN}
    headers = {"Content-Type": "application/json"}
    data = {
        "recipient": {"id": recipient_id},
        "message": {"text": text}
    }
    requests.post("https://graph.facebook.com/v19.0/me/messages", params=params, json=data)

def send_image(recipient_id, image_url):
    """ฟังก์ชันส่งรูปภาพ"""
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
    requests.post("https://graph.facebook.com/v19.0/me/messages", params=params, json=data)

# --- 2. LOGIC วิเคราะห์ข้อความ (หัวใจหลัก) ---
def process_user_message(sender_id, text):
    text_lower = text.lower()
    
    # ตัวแปรเก็บผลลัพธ์
    found_codes = []      # รหัสที่มีรูปจริง (พร้อมส่ง)
    unknown_codes = []    # รหัสที่ลูกค้าพิมพ์ผิด หรือยังไม่มีในระบบ
    
    # 1️⃣ Loop เช็คไฟล์ที่มีในระบบ (Cond 1 & 4)
    # วนลูปดูว่าในประโยค มีรหัสสินค้าของเราซ่อนอยู่ไหม
    for code_key, full_filename in CACHED_FILES.items():
        if code_key in text_lower:
            if full_filename not in found_codes:
                found_codes.append(full_filename)

    # 2️⃣ ส่งรูปทันที ถ้าเจอ (Cond 1 & 4)
    if found_codes:
        for filename in found_codes:
            print(f"✅ Found code: {filename} -> Sending...")
            send_image(sender_id, get_image_url(filename))
            
    # 3️⃣ เช็คหารหัสที่ 'ไม่มีในระบบ' (Cond 3)
    # ใช้ Regex หารหัสที่มีตัวเลขผสมตัวอักษร (เช่น 999AA, A123) ความยาว 3 ตัวขึ้นไป
    # เพื่อแยกว่าอันไหนคือ 'รหัส' อันไหนคือ 'คำพูดปกติ'
    potential_matches = re.findall(r'[a-z0-9]*\d+[a-z0-9]*', text_lower)
    
    for word in potential_matches:
        # กรองเฉพาะคำที่ยาวเกิน 3 ตัวอักษร และไม่ใช่รหัสที่เจอไปแล้วในข้อ 1
        if len(word) >= 4:
            is_known = False
            for known_key in CACHED_FILES.keys():
                if known_key in word: # ถ้าคำนี้มีส่วนคล้ายกับรหัสจริง ให้ถือว่าเป็นรหัสจริง
                    is_known = True
                    break
            
            if not is_known:
                unknown_codes.append(word)

    # ถ้าเจอแต่รหัสแปลกๆ ที่ไม่มีไฟล์ -> แจ้งเตือน (Cond 3)
    if not found_codes and unknown_codes:
        msg = f"ขออภัยครับ ยังไม่มีรูปสำหรับรหัส '{unknown_codes[0]}' ในระบบ\nรบกวนรอแอดมินมาเพิ่มรูปให้นะครับ 🙏"
        send_message(sender_id, msg)

    # 4️⃣ เช็คคำว่า 'รูป' หรือ 'ภาพ' แต่ไม่เจอเพจ (Cond 2)
    # ต้องไม่เจอรูป (not found_codes) และไม่เจอรหัสแปลกๆ (not unknown_codes)
    if not found_codes and not unknown_codes:
        if 'รูป' in text_lower or 'ภาพ' in text_lower:
            msg = "หากต้องการดูรูปสินค้า รบกวนพิมพ์ 'รหัสสินค้า' ได้เลยครับ (เช่น 999AA01)\n\nหรือถ้าไม่ทราบรหัส รบกวนรอแอดมินสักครู่นะครับ 😊"
            send_message(sender_id, msg)

# --- 3. WEBHOOK ---
@app.route('/', methods=['GET'])
def verify():
    if request.args.get("hub.mode") == "subscribe" and request.args.get("hub.verify_token") == VERIFY_TOKEN:
        return request.args.get("hub.challenge"), 200
    return "Bot Running", 200

@app.route('/', methods=['POST'])
def webhook():
    data = request.json
    if data['object'] == 'page':
        for entry in data['entry']:
            if 'messaging' in entry:
                for event in entry['messaging']:
                    if 'message' in event:
                        # กันบอทคุยกับตัวเอง (Echo)
                        if event.get('message', {}).get('is_echo'):
                            continue

                        sender_id = event['sender']['id']
                        text = event['message'].get('text', '')
                        
                        if text:
                            print(f"📩 User typed: {text}")
                            process_user_message(sender_id, text)
                        
    return "ok", 200

if __name__ == '__main__':
    app.run(port=5000)
