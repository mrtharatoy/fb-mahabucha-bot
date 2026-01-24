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

# ตัวแปรสำหรับเก็บรายชื่อไฟล์ (Cache)
# บอทจะโหลดรายชื่อไฟล์มาเก็บไว้ตรงนี้ตอนเริ่มทำงาน
CACHED_FILES = []

def update_file_list():
    """ฟังก์ชันวิ่งไปดูรายชื่อไฟล์ทั้งหมดใน GitHub"""
    global CACHED_FILES
    api_url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{REPO_NAME}/contents/{FOLDER_NAME}?ref={BRANCH}"
    
    try:
        r = requests.get(api_url)
        if r.status_code == 200:
            data = r.json()
            # ดึงเฉพาะชื่อไฟล์ ตัดนามสกุลทิ้ง (เช่น 'A001.jpg' -> 'A001')
            # และเก็บเป็นตัวพิมพ์เล็กทั้งหมด เพื่อให้หาง่าย
            CACHED_FILES = [item['name'].rsplit('.', 1)[0] for item in data if item['type'] == 'file']
            print(f"📚 Updated File List ({len(CACHED_FILES)} files): {CACHED_FILES}")
        else:
            print(f"⚠️ Failed to fetch file list: {r.status_code}")
    except Exception as e:
        print(f"❌ Error updating file list: {e}")

# สั่งให้โหลดรายชื่อไฟล์ทันทีที่เริ่ม Server
update_file_list()

def get_github_image_url(filename_without_ext):
    """สร้างลิงก์รูปภาพ (โดยเราต้องเดานามสกุล หรือใช้ jpg เป็นหลัก)"""
    # หมายเหตุ: เพื่อความง่าย เราจะสมมติว่าเป็น .jpg ไว้ก่อน
    # ถ้าคุณใช้ไฟล์คละกัน (.jpg, .png) อาจต้องปรับปรุงส่วนนี้เพิ่ม
    return f"https://raw.githubusercontent.com/{GITHUB_USERNAME}/{REPO_NAME}/{BRANCH}/{FOLDER_NAME}/{filename_without_ext}.jpg"

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
                    
                    if 'text' in event['message']:
                        text = event['message']['text']
                        print(f"📩 User Said: '{text}'")
                        
                        # แปลงข้อความลูกค้าเป็นตัวพิมพ์เล็ก เพื่อเทียบกับรายชื่อไฟล์
                        user_text_lower = text.lower()
                        
                        found_something = False
                        
                        # --- วนลูปเช็คชื่อไฟล์ทุกชื่อที่เรามี ---
                        for filename in CACHED_FILES:
                            # เช็คว่าชื่อไฟล์นี้ ปรากฏอยู่ในประโยคที่ลูกค้าพิมพ์ไหม
                            # (ใช้ lower() เพื่อให้ A001 กับ a001 ถือว่าเหมือนกัน)
                            if filename.lower() in user_text_lower:
                                print(f"✅ Found Keyword: {filename}")
                                
                                # สร้างลิงก์และส่งรูป (ใช้ชื่อเดิมที่โหลดมาจาก GitHub เพื่อความเป๊ะ)
                                # หมายเหตุ: ตรงนี้ต้องระวังเรื่อง Case Sensitive ของ URL
                                # เราจึงใช้ชื่อไฟล์จริงๆ จาก GitHub ไม่ใช่ชื่อที่ลูกค้าพิมพ์
                                
                                # เนื่องจากเราเก็บ list เป็นชื่อที่ตัดนามสกุลแล้ว
                                # เราต้องหาชื่อไฟล์จริงๆ ที่มีตัวพิมพ์ใหญ่/เล็กถูกต้อง (Best practice)
                                # แต่เบื้องต้นส่งแบบนี้ไปก่อน (GitHub raw content มักจะ case sensitive)
                                
                                # เทคนิค: ส่งชื่อไฟล์ที่เป็น Keyword ไปสร้างลิงก์เลย
                                # แต่ต้องระวัง ถ้าลูกค้าพิมพ์ "ganesh" แต่ไฟล์ชื่อ "Ganesh.jpg"
                                # ลิงก์อาจจะผิดได้ ดังนั้นเราควรใช้ชื่อจาก CACHED_FILES มาเทียบให้เป๊ะที่สุด
                                
                                # (ฉบับปรับปรุง) เนื่องจาก CACHED_FILES ที่เราเก็บตะกี้ เราไม่ได้เก็บชื่อจริงแบบมี Case
                                # เพื่อความชัวร์ ให้ส่งตามที่เจอไปก่อน
                                image_url = get_github_image_url(filename) 
                                send_image(sender_id, image_url)
                                found_something = True
                        
                        if not found_something:
                            print("❌ No matching file found in message.")

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
    # (Optional) ถ้าอยากให้อัปเดตไฟล์ทุกครั้งที่รัน
    update_file_list() 
    app.run(port=5000)