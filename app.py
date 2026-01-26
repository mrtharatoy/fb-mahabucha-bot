import os
import requests
import re
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
                    key = item['name'].rsplit('.', 1)[0].strip().lower()
                    CACHED_FILES[key] = item['name']
            print(f"📂 FILES READY: {len(CACHED_FILES)} images.")
    except Exception as e:
        print(f"❌ Error: {e}")

update_file_list()

def get_image_url(filename):
    return f"https://raw.githubusercontent.com/{GITHUB_USERNAME}/{REPO_NAME}/{BRANCH}/{FOLDER_NAME}/{filename}"

def send_message(recipient_id, text):
    print(f"💬 Sending message to {recipient_id}: {text}")
    params = {"access_token": PAGE_ACCESS_TOKEN}
    headers = {"Content-Type": "application/json"}
    data = {
        "recipient": {"id": recipient_id},
        "message": {"text": text}
    }
    requests.post("https://graph.facebook.com/v19.0/me/messages", params=params, json=data)

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
    requests.post("https://graph.facebook.com/v19.0/me/messages", params=params, json=data)

# --- 2. LOGIC วิเคราะห์ข้อความ (Smart & Detailed) ---
def process_message(target_id, text, is_admin_sender):
    text_lower = text.lower()
    
    # เก็บข้อมูลรหัสที่พบ
    # found_actions เก็บเป็นคู่ (รหัสที่พิมพ์, ชื่อไฟล์รูป)
    found_actions = [] 
    
    # 1️⃣ หา "รหัสที่ถูกต้อง" (สำหรับ User และ Admin)
    for code_key, full_filename in CACHED_FILES.items():
        if code_key in text_lower:
            # ป้องกันการใส่ซ้ำ
            if (code_key, full_filename) not in found_actions:
                found_actions.append((code_key, full_filename))

    # ✅ จัดการรหัสที่ "เจอ" (Found Codes)
    if found_actions:
        for code_key, filename in found_actions:
            print(f"✅ Code found ({code_key}) -> Sending to {target_id}")
            
            # (ข้อ 1) ส่งข้อความบอกก่อนว่ารหัสนี้คือรูปนี้
            msg = f"รหัส '{code_key}' คือรูปนี้ครับ 👇"
            send_message(target_id, msg)
            
            # แล้วค่อยส่งรูป
            send_image(target_id, get_image_url(filename))
            
    # --- ถ้าเป็น Admin ให้จบแค่นี้ (ไม่ต้องแจ้งเตือนรหัสผิดให้ลูกค้าตกใจ) ---
    if is_admin_sender:
        return 

    # --- ส่วนของ User (จัดการรหัสผิด และ คำทั่วไป) ---
    
    # 2️⃣ หารหัสที่ "ไม่เจอ" (Unknown Codes)
    unknown_codes = []
    # Regex หาคำที่เป็นภาษาอังกฤษผสมตัวเลข
    potential_matches = re.findall(r'[a-z0-9]*\d+[a-z0-9]*', text_lower)
    
    for word in potential_matches:
        if len(word) >= 4: # กรองคำสั้นๆ ทิ้ง
            is_known = False
            
            # เช็คว่าคำนี้ เป็นส่วนหนึ่งของรหัสที่เจอไปแล้วหรือยัง? (จะได้ไม่แจ้งซ้ำ)
            for found_key, _ in found_actions:
                if found_key in word or word in found_key:
                    is_known = True
                    break
            
            # เช็คกับฐานข้อมูลอีกที
            if not is_known:
                for known_key in CACHED_FILES.keys():
                    if known_key in word: 
                        is_known = True
                        break
            
            if not is_known:
                if word not in unknown_codes:
                    unknown_codes.append(word)

    # ⚠️ (ข้อ 2) แจ้งเตือนรหัสที่ไม่เจอ (แม้จะเจอรูปอื่นแล้ว ก็ต้องบอกว่าอันนี้หาไม่เจอ)
    if unknown_codes:
        # รวมรหัสที่ไม่เจอมาบอกทีเดียว หรือบอกทีละอันก็ได้ (เอาทีละอันให้ชัดเจน)
        for bad_code in unknown_codes:
            msg = f"⚠️ รหัส '{bad_code}' ไม่พบในระบบ หรืออาจพิมพ์ผิดครับ\n(รอแอดมินตรวจสอบให้นะครับ 🙏)"
            send_message(target_id, msg)

    # 3️⃣ เช็คคำว่า 'รูป/ภาพ' (กรณีไม่เจออะไรเลย)
    if not found_actions and not unknown_codes:
        if 'รูป' in text_lower or 'ภาพ' in text_lower:
            msg = "หากต้องการดูรูปสินค้า รบกวนพิมพ์ 'รหัสสินค้า' ได้เลยครับ (เช่น 999AA01)\n\nหรือถ้าไม่ทราบรหัส รบกวนรอแอดมินสักครู่นะครับ 😊"
            send_message(target_id, msg)

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
                        text = event['message'].get('text', '')
                        
                        # เช็คว่าเป็น Admin หรือ ลูกค้า
                        is_echo = event.get('message', {}).get('is_echo', False)
                        
                        if is_echo:
                            # Admin พิมพ์: ส่งหาลูกค้า
                            if 'recipient' in event and 'id' in event['recipient']:
                                target_id = event['recipient']['id']
                                print(f"👮 Admin typed: {text}")
                                process_message(target_id, text, is_admin_sender=True)
                        else:
                            # ลูกค้าพิมพ์: ตอบลูกค้า
                            target_id = event['sender']['id']
                            print(f"👤 User typed: {text}")
                            process_message(target_id, text, is_admin_sender=False)
                        
    return "ok", 200

if __name__ == '__main__':
    app.run(port=5000)
