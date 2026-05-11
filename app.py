import os
import requests
import re
import threading
import time
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# --- ⚙️ 1. CONFIG ---
GITHUB_USERNAME = "mrtharatoy"
REPO_NAME = "siamganesh-online-backend"
BRANCH = "main"

MAHABUCHA_PAGE_ID = os.environ.get('MAHABUCHA_PAGE_ID')
MAHABUCHA_TOKEN = os.environ.get('MAHABUCHA_TOKEN')
MUTETEAM_PAGE_ID = os.environ.get('MUTETEAM_PAGE_ID')
MUTETEAM_TOKEN = os.environ.get('MUTETEAM_TOKEN')
VERIFY_TOKEN = os.environ.get('VERIFY_TOKEN')
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')

CACHED_FILES = {"mahabucha": {}, "muteteam": {}}
FILES_LOADED = False
lock = threading.Lock()

# --- 📂 2. GITHUB FILES ---
def update_file_list():
    global CACHED_FILES, FILES_LOADED
    print("🔄 Updating image list from GitHub...")
    headers = {"User-Agent": "Siamganesh-Bot", "Accept": "application/vnd.github.v3+json"}
    if GITHUB_TOKEN: headers["Authorization"] = f"token {GITHUB_TOKEN}"
    
    for page in ["mahabucha", "muteteam"]:
        api_url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{REPO_NAME}/contents/images/{page}?ref={BRANCH}"
        try:
            r = requests.get(api_url, headers=headers, timeout=15)
            if r.status_code == 200:
                temp_cache = {item['name'].rsplit('.', 1)[0].strip().lower(): item['name'] 
                              for item in r.json() if item['type'] == 'file' and item['name'] != '.keep'}
                CACHED_FILES[page] = temp_cache
                print(f"✅ {page.upper()} loaded: {len(temp_cache)} images.")
        except Exception as e: print(f"❌ Error {page}: {e}")
    FILES_LOADED = True

def get_image_url(page, filename):
    return f"https://raw.githubusercontent.com/{GITHUB_USERNAME}/{REPO_NAME}/{BRANCH}/images/{page}/{filename}"

# --- 💬 3. FACEBOOK TOOLS ---
def get_page_token(page_id):
    if str(page_id) == str(MAHABUCHA_PAGE_ID): return MAHABUCHA_TOKEN
    if str(page_id) == str(MUTETEAM_PAGE_ID): return MUTETEAM_TOKEN
    return None

def send_fb_action(recipient_id, page_id, data_type, payload):
    token = get_page_token(page_id)
    if not token: return
    url = "https://graph.facebook.com/v19.0/me/messages"
    params = {"access_token": token}
    
    if data_type == "text":
        msg = {"text": payload, "metadata": "BOT_SENT_THIS"}
    else: # image
        msg = {"attachment": {"type": "image", "payload": {"url": payload, "is_reusable": True}}, "metadata": "BOT_SENT_THIS"}
        
    data = {"recipient": {"id": recipient_id}, "message": msg}
    r = requests.post(url, params=params, json=data)
    if r.status_code != 200: # Use Tag if failed
        data["messaging_type"] = "MESSAGE_TAG"
        data["tag"] = "CONFIRMED_EVENT_UPDATE"
        requests.post(url, params=params, json=data)

# --- 🧠 4. MESSAGE PROCESSOR ---
def process_message(target_id, text, page_id):
    global FILES_LOADED
    page_name = "mahabucha" if str(page_id) == str(MAHABUCHA_PAGE_ID) else "muteteam" if str(page_id) == str(MUTETEAM_PAGE_ID) else None
    if not page_name: return

    # ✨ NEW REGEX PATTERN (ล็อค 269 หรือ 999 ให้ตรงกับหน้าบ้าน)
    pattern_regex = r'(?:269|999)[a-z]{2}(?:0[1-9]|1[0-9]|20)\d{3}'
    
    text_cleaned = text.lower().replace(" ", "")
    valid_codes = re.findall(pattern_regex, text_cleaned)

    # นินจาโหมด: ถ้าไม่เจอรหัสตามแพทเทิร์นเลย ให้หยุดการทำงาน
    if not valid_codes:
        return

    if not FILES_LOADED:
        with lock:
            if not FILES_LOADED: update_file_list()

    current_cache = CACHED_FILES[page_name]
    found_imgs = []
    unknown_codes = []

    for code in valid_codes:
        if code in current_cache:
            found_imgs.append((code, current_cache[code]))
        else:
            unknown_codes.append(code)

    # ส่งคำนำ (อัปเดตข้อความใหม่)
    if found_imgs:
        page_display_name = "มหาบูชา" if page_name == "mahabucha" else "มูเตทีม"
        intro = f"📸 ขออนุญาตส่งมอบความสิริมงคลผ่านภาพถ่าย ที่ใช้ในงานพิธีในครั้งนี้ครับ\n\nร่วมอนุโมทนาและรับชมภาพบรรยากาศได้ที่เพจ \"{page_display_name}\" นะครับ 🙏✨"
        
        send_fb_action(target_id, page_id, "text", intro)
        
        for code_key, filename in found_imgs:
            send_fb_action(target_id, page_id, "text", f"ภาพถาดถวาย รหัส : {code_key.upper()}")
            send_fb_action(target_id, page_id, "image", get_image_url(page_name, filename))

    if unknown_codes:
        msg = "⚠️ ขออภัยครับ \n \nไม่พบภาพถาดถวายจากรหัสของท่าน \n \nรบกวนรอแอดมินเข้ามาตรวจสอบให้ ซักครู่นะครับ ⏳"
        send_fb_action(target_id, page_id, "text", msg)

# --- 🌐 5. API ---
@app.route('/api/search', methods=['GET'])
def search_api():
    global FILES_LOADED
    page = request.args.get('page', '').lower()
    code = request.args.get('code', '').lower().strip()
    
    if page not in ["mahabucha", "muteteam"] or not code:
        return jsonify({"found": False, "message": "ข้อมูลไม่ครบ"}), 400

    if not FILES_LOADED:
        with lock:
            if not FILES_LOADED: update_file_list()

    current_cache = CACHED_FILES.get(page, {})
    if code in current_cache:
        return jsonify({"found": True, "code": code.upper(), "image_url": get_image_url(page, current_cache[code])}), 200
    return jsonify({"found": False, "message": "ไม่พบรูปภาพ"}), 404

@app.route('/', methods=['GET'])
def verify():
    if request.args.get("hub.verify_token") == VERIFY_TOKEN:
        return request.args.get("hub.challenge"), 200
    return "🟢 Siamganesh Online Backend is Live", 200

# --- 🔌 6. WEBHOOK ---
@app.route('/', methods=['POST'])
def webhook():
    data = request.json
    if data.get('object') == 'page':
        for entry in data['entry']:
            p_id = entry.get('id')
            if 'messaging' in entry:
                for ev in entry['messaging']:
                    if 'message' in ev:
                        # 1. กันบอทคุยกับตัวเอง
                        if ev['message'].get('metadata') == "BOT_SENT_THIS": 
                            continue
                        
                        # 2. ป้องกันข้อความเก่าค้างท่อเกิน 5 นาที
                        message_timestamp = ev.get('timestamp')
                        if message_timestamp:
                            time_diff = (int(time.time() * 1000) - message_timestamp) / 1000
                            if time_diff > 300: 
                                continue
                                
                        text = ev['message'].get('text', '')
                        is_echo = ev['message'].get('is_echo', False)
                        
                        # 3. กำหนดเป้าหมาย (ส่งให้ใคร?)
                        # ถ้าแอดมินพิมพ์ (is_echo) -> ส่งรูปให้ลูกค้า (recipient)
                        # ถ้าลูกค้าพิมพ์ -> ส่งรูปให้ลูกค้า (sender)
                        target_id = ev.get('recipient', {}).get('id') if is_echo else ev.get('sender', {}).get('id')
                        
                        if target_id and text:
                            # ปิดการทำงานของบอทชั่วคราว (ใส่ # นำหน้า)
                             process_message(target_id, text, p_id)
                            # pass # ใส่ pass ไว้เพื่อให้ระบบทำงานข้ามจุดนี้ไป
    return "ok", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
