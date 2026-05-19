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
MAHABUCHA_TOKEN   = os.environ.get('MAHABUCHA_TOKEN')
MUTETEAM_PAGE_ID  = os.environ.get('MUTETEAM_PAGE_ID')
MUTETEAM_TOKEN    = os.environ.get('MUTETEAM_TOKEN')
VERIFY_TOKEN      = os.environ.get('VERIFY_TOKEN')
GITHUB_TOKEN      = os.environ.get('GITHUB_TOKEN')

CACHED_FILES = {"mahabucha": {}, "muteteam": {}}
FILES_LOADED = False
lock = threading.Lock()

# --- 📂 2. GITHUB FILES ---
def update_file_list():
    global CACHED_FILES, FILES_LOADED
    print("🔄 Updating image list from GitHub...")
    headers = {"User-Agent": "Siamganesh-Bot", "Accept": "application/vnd.github.v3+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"

    for page in ["mahabucha", "muteteam"]:
        api_url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{REPO_NAME}/contents/images/{page}?ref={BRANCH}"
        try:
            r = requests.get(api_url, headers=headers, timeout=15)
            if r.status_code == 200:
                files = r.json()
                temp_cache = {}
                for item in files:
                    if item['type'] == 'file' and item['name'] != '.keep':
                        # เก็บชื่อไฟล์เต็ม (รวม extension) โดยใช้ชื่อ (ไม่มี extension) เป็น key
                        name_no_ext = item['name'].rsplit('.', 1)[0].strip().lower()
                        temp_cache[name_no_ext] = item['name']
                CACHED_FILES[page] = temp_cache
                print(f"✅ {page.upper()} loaded: {len(temp_cache)} images.")
        except Exception as e:
            print(f"❌ Error {page}: {e}")
    FILES_LOADED = True

def get_image_url(page, filename):
    return f"https://raw.githubusercontent.com/{GITHUB_USERNAME}/{REPO_NAME}/{BRANCH}/images/{page}/{filename}"

# --- 💬 3. FACEBOOK TOOLS ---
def get_page_token(page_id):
    if str(page_id) == str(MAHABUCHA_PAGE_ID): return MAHABUCHA_TOKEN
    if str(page_id) == str(MUTETEAM_PAGE_ID):  return MUTETEAM_TOKEN
    return None

def send_fb_action(recipient_id, page_id, data_type, payload):
    token = get_page_token(page_id)
    if not token:
        return
    url    = "https://graph.facebook.com/v19.0/me/messages"
    params = {"access_token": token}

    if data_type == "text":
        msg = {"text": payload, "metadata": "BOT_SENT_THIS"}
    else:  # image
        msg = {
            "attachment": {
                "type": "image",
                "payload": {"url": payload, "is_reusable": True}
            },
            "metadata": "BOT_SENT_THIS"
        }

    data = {"recipient": {"id": recipient_id}, "message": msg}
    r = requests.post(url, params=params, json=data)

    # Fallback: ถ้าส่งไม่ได้ ลอง MESSAGE_TAG
    if r.status_code != 200:
        data["messaging_type"] = "MESSAGE_TAG"
        data["tag"] = "CONFIRMED_EVENT_UPDATE"
        requests.post(url, params=params, json=data)

# --- 🧠 4. MESSAGE PROCESSOR ---
def process_mahabucha(target_id, text, page_id):
    """
    มหาบูชา — ใช้ pattern รหัสภาพองค์เทพ เดิม
    Pattern: (269|999)[a-z]{2}(01-20)[0-9]{3}
    """
    pattern_regex = r'(?:269|999)[a-z]{2}(?:0[1-9]|1[0-9]|20)\d{3}'
    text_cleaned  = text.lower().replace(" ", "")
    valid_codes   = re.findall(pattern_regex, text_cleaned)

    if not valid_codes:
        return  # ไม่ใช่รหัสที่ต้องดักจับ หยุดเงียบๆ

    if not FILES_LOADED:
        with lock:
            if not FILES_LOADED:
                update_file_list()

    current_cache = CACHED_FILES["mahabucha"]
    found_imgs    = []
    unknown_codes = []

    for code in valid_codes:
        if code in current_cache:
            found_imgs.append((code, current_cache[code]))
        else:
            unknown_codes.append(code)

    if found_imgs:
        intro = (
            "📸 ขออนุญาตส่งมอบความสิริมงคลผ่านภาพถ่าย ที่ใช้ในงานพิธีในครั้งนี้ครับ\n\n"
            "ร่วมอนุโมทนาและรับชมภาพบรรยากาศได้ที่เพจ \"มหาบูชา\" นะครับ 🙏✨"
        )
        send_fb_action(target_id, page_id, "text", intro)
        for code_key, filename in found_imgs:
            send_fb_action(target_id, page_id, "text", f"ภาพถาดถวาย รหัส : {code_key.upper()}")
            send_fb_action(target_id, page_id, "image", get_image_url("mahabucha", filename))

    if unknown_codes:
        msg = "⚠️ ขออภัยครับ \n\nไม่พบภาพถาดถวายจากรหัสของท่าน \n\nรบกวนรอแอดมินเข้ามาตรวจสอบให้ซักครู่นะครับ ⏳"
        send_fb_action(target_id, page_id, "text", msg)


def process_muteteam(target_id, text, page_id):
    """
    มูเตทีม — ใช้รหัสการจอง 12 หลัก (YYMMDDHHmmss) เช่น 260519142238
    ค้นหาไฟล์ที่ขึ้นต้นด้วยรหัสนั้น (260519142238_1, _2, _3 ...)
    """
    # ดักจับ pattern 12 หลัก (ตัวเลขล้วน)
    pattern_regex = r'\b(\d{12})\b'
    valid_codes   = re.findall(pattern_regex, text.replace(" ", ""))

    if not valid_codes:
        return  # ไม่ใช่รหัสที่ต้องดักจับ หยุดเงียบๆ

    if not FILES_LOADED:
        with lock:
            if not FILES_LOADED:
                update_file_list()

    current_cache = CACHED_FILES["muteteam"]
    # current_cache key = ชื่อไฟล์ไม่มี extension เช่น "260519142238_1"

    for booking_code in set(valid_codes):  # deduplicate
        # หาไฟล์ทั้งหมดที่ขึ้นต้นด้วย booking_code
        matched_files = [
            (key, filename)
            for key, filename in current_cache.items()
            if key.startswith(booking_code)
        ]
        # เรียงตามชื่อ (_1, _2, _3 ...)
        matched_files.sort(key=lambda x: x[0])

        if matched_files:
            intro = (
                "📸 ขออนุญาตส่งมอบความสิริมงคลผ่านภาพถ่าย ที่ใช้ในงานพิธีในครั้งนี้ครับ\n\n"
                "ร่วมอนุโมทนาและรับชมภาพบรรยากาศได้ที่เพจ \"มูเตทีม\" นะครับ 🙏✨"
            )
            send_fb_action(target_id, page_id, "text", intro)
            for idx, (_, filename) in enumerate(matched_files, 1):
                send_fb_action(target_id, page_id, "text", f"ภาพถาดถวาย {idx}/{len(matched_files)}")
                send_fb_action(target_id, page_id, "image", get_image_url("muteteam", filename))
        else:
            # ยังไม่มีภาพ — แจ้งให้รอ
            msg = (
                "⏳ เรียนผู้มีจิตศรัทธาที่นับถือครับ\n\n"
                "ขณะนี้คณะทีมงานยังอยู่ระหว่างดำเนินการนำถาดถวายของท่าน\n"
                "เข้าสู่พิธีกรรมอย่างเป็นขั้นตอนครับ\n\n"
                "รบกวนรอทีมงานนำฝากถวายให้แล้วเสร็จ\n"
                "แล้วท่านจะได้รับภาพเป็นที่ระลึกจากพิธีนะครับ 🙏✨"
            )
            send_fb_action(target_id, page_id, "text", msg)


def process_message(target_id, text, page_id):
    """Router — แยก process ตามเพจ"""
    if str(page_id) == str(MAHABUCHA_PAGE_ID):
        process_mahabucha(target_id, text, page_id)
    elif str(page_id) == str(MUTETEAM_PAGE_ID):
        process_muteteam(target_id, text, page_id)

# --- 🌐 5. WEBHOOK ---
@app.route('/', methods=['GET'])
def verify():
    if request.args.get("hub.verify_token") == VERIFY_TOKEN:
        return request.args.get("hub.challenge"), 200
    return "🟢 Siamganesh Online Backend is Live", 200

@app.route('/', methods=['POST'])
def webhook():
    data = request.get_json(silent=True)
    if not data or data.get("object") != "page":
        return "ok", 200

    for entry in data.get("entry", []):
        page_id = str(entry.get("id", ""))
        for event in entry.get("messaging", []):
            sender_id = event.get("sender", {}).get("id")
            msg       = event.get("message", {})
            text      = msg.get("text", "")
            metadata  = msg.get("metadata", "")

            # ข้ามข้อความที่บอทส่งเอง
            if metadata == "BOT_SENT_THIS" or not text or not sender_id:
                continue

            threading.Thread(
                target=process_message,
                args=(sender_id, text, page_id),
                daemon=True
            ).start()

    return "ok", 200

# --- 🔍 6. SEARCH API ---
@app.route('/api/search', methods=['GET'])
def search_api():
    global FILES_LOADED
    page = request.args.get('page', '').lower()
    code = request.args.get('code', '').lower().strip()

    if page not in ["mahabucha", "muteteam"] or not code:
        return jsonify({"found": False, "message": "ข้อมูลไม่ครบ"}), 400

    if not FILES_LOADED:
        with lock:
            if not FILES_LOADED:
                update_file_list()

    current_cache = CACHED_FILES.get(page, {})

    if page == "muteteam":
        # มูเตทีม: ค้นหาจาก booking_code (prefix)
        matched = [
            {"code": key.upper(), "image_url": get_image_url(page, filename)}
            for key, filename in sorted(current_cache.items())
            if key.startswith(code)
        ]
        if matched:
            return jsonify({"found": True, "results": matched, "count": len(matched)}), 200
        return jsonify({"found": False, "message": "ไม่พบรูปภาพ"}), 404
    else:
        # มหาบูชา: ค้นหาจาก deity_code ตรงๆ
        if code in current_cache:
            return jsonify({
                "found": True,
                "code": code.upper(),
                "image_url": get_image_url(page, current_cache[code])
            }), 200
        return jsonify({"found": False, "message": "ไม่พบรูปภาพ"}), 404

# --- 🔄 7. RELOAD CACHE API ---
@app.route('/api/reload', methods=['POST'])
def reload_cache():
    """เรียกให้โหลด image list ใหม่จาก GitHub"""
    threading.Thread(target=update_file_list, daemon=True).start()
    return jsonify({"message": "กำลัง reload cache..."}), 200

if __name__ == '__main__':
    update_file_list()
    app.run(debug=False, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
