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

# --- ฟังก์ชันส่งข้อความ (ฝัง Metadata กันลูป) ---
def send_message(recipient_id, text):
    print(f"💬 Sending message to {recipient_id}: {text}")
    params = {"access_token": PAGE_ACCESS_TOKEN}
    headers = {"Content-Type": "application/json"}
    data = {
        "recipient": {"id": recipient_id},
        "message": {
            "text": text,
            "metadata": "BOT_SENT_THIS" # กันลูป
        }
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
            },
            "metadata": "BOT_SENT_THIS" # กันลูป
        }
    }
    requests.post("https://graph.facebook.com/v19.0/me/messages", params=params, json=data)

# --- 2. LOGIC วิเคราะห์ข้อความ (Gatekeeper + Space Vacuum) ---
def process_message(target_id, text, is_admin_sender):
    # 1. เทคนิค Space Vacuum: ดูดช่องว่างทิ้งทั้งหมดก่อน!
    # เช่น "999 ac 122" กลายเป็น "999ac122"
    # เช่น "ขอ 26 9acc052 ครับ" กลายเป็น "ขอ269acc052ครับ"
    text_cleaned = text.lower().replace(" ", "")
    
    # 2. [CORE LOGIC] กรองเฉพาะรหัสตาม Pattern (9 ตัวอักษร)
    # Pattern: ขึ้นต้นด้วย 269 หรือ 999 + ตามด้วยอะไรก็ได้ (เลข/อักษร) อีก 6 ตัว
    # รวมเป็น 9 ตัวพอดีเป๊ะ
    pattern = r'(?:269|999)[a-z0-9]{6}'
    
    # ค้นหารหัสทั้งหมดที่ซ่อนอยู่ในข้อความที่ดูดช่องว่างแล้ว
    valid_format_codes = re.findall(pattern, text_cleaned)
    
    # 🛑 GATEKEEPER: ถ้าสแกนแล้วไม่เจออะไรที่หน้าตาเหมือนรหัสเลย -> เงียบ (ไม่ตอบ)
    if not valid_format_codes:
        print(f"   (Ignored) No valid code pattern found in: {text}")
        return

    # --- ถ้าผ่านด่านมาได้ (เจอสิ่งที่หน้าตาเหมือนรหัส) ---
    found_actions = [] 
    unknown_codes = []

    for code in valid_format_codes:
        # เช็คว่ารหัสนี้ มีไฟล์อยู่จริงในระบบไหม?
        if code in CACHED_FILES:
            # เจอไฟล์จริง -> เตรียมส่ง
            full_filename = CACHED_FILES[code]
            if (code, full_filename) not in found_actions:
                found_actions.append((code, full_filename))
        else:
            # รูปแบบถูก (ขึ้นต้น 999/269 ครบ 9 ตัว) แต่ไม่มีไฟล์ -> เตรียมแจ้งเตือน
            if code not in unknown_codes:
                unknown_codes.append(code)

    # ✅ ส่วนการส่งรูป (ถ้าเจอ)
    if found_actions:
        # ส่งข้อความเปิดหัว (รอบเดียว)
        intro_msg = (
            "📸 ขออนุญาตส่งภาพนะครับ\n"
            "รวมภาพงานพิธี กดได้ที่ link นี้\n\n"
            " -> linktr.ee/mahabucha\n\n"
            "หรือ รับชมได้ที่หน้าเพจ \"มหาบูชา\"\n\n"
            "ทีมงานเทวาลัยสยามคเณศ ขอขอบคุณครับ"
        )
        send_message(target_id, intro_msg)

        # วนลูปส่งรูป
        for code_key, filename in found_actions:
            print(f"✅ Code found ({code_key}) -> Sending to {target_id}")
            msg = f"ภาพถาดถวาย รหัส : {code_key}"
            send_message(target_id, msg)
            send_image(target_id, get_image_url(filename))
            
    # ถ้าเป็น Admin ให้จบแค่นี้ (ไม่แจ้งเตือนรหัสผิด)
    if is_admin_sender:
        return 

    # ⚠️ ส่วนแจ้งเตือน (เฉพาะรหัสที่รูปแบบถูก แต่หาไฟล์ไม่เจอ)
    if unknown_codes:
        # แจ้งเตือนแค่ครั้งเดียวพอกรณีผิดหลายอัน หรือจะวนลูปก็ได้ (อันนี้แจ้งรวมเพื่อไม่ให้รก)
        msg = "ยังไม่พบรหัสภาพของท่าน พิธีอาจจะยังไม่ได้เริ่ม หรือท่านพิมพ์รหัสผิด ครับ"
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
                        
                        # --- 🛑 กันลูปด้วย Metadata ---
                        if event.get('message', {}).get('metadata') == "BOT_SENT_THIS":
                            continue
                        # ----------------------------

                        is_echo = event.get('message', {}).get('is_echo', False)
                        
                        if is_echo:
                            # Admin พิมพ์
                            if 'recipient' in event and 'id' in event['recipient']:
                                target_id = event['recipient']['id']
                                print(f"👮 Admin typed: {text}")
                                process_message(target_id, text, is_admin_sender=True)
                        else:
                            # ลูกค้าพิมพ์
                            target_id = event['sender']['id']
                            print(f"👤 User typed: {text}")
                            process_message(target_id, text, is_admin_sender=False)
                        
    return "ok", 200

if __name__ == '__main__':
    app.run(port=5000)
