import os
import json
from flask import Flask, request
import requests

app = Flask(__name__)

# โหลดข้อมูลสินค้า
try:
    with open('products.json', encoding='utf-8') as f:
        PRODUCT_DATA = json.load(f)
    print(f"✅ Loaded {len(PRODUCT_DATA)} products.")
except Exception as e:
    print(f"❌ Error loading products.json: {e}")
    PRODUCT_DATA = {}

PAGE_ACCESS_TOKEN = os.environ.get('PAGE_ACCESS_TOKEN')
VERIFY_TOKEN = os.environ.get('VERIFY_TOKEN')

@app.route('/', methods=['GET'])
def verify():
    if request.args.get("hub.mode") == "subscribe" and request.args.get("hub.challenge"):
        if request.args.get("hub.verify_token") == VERIFY_TOKEN:
            return request.args.get("hub.challenge"), 200
    return "Bot is running!", 200

@app.route('/', methods=['POST'])
def webhook():
    data = request.json
    # print(f"DEBUG: Received Event: {data}") # เปิดบรรทัดนี้ถ้าอยากเห็นข้อมูลดิบทั้งหมด
    
    if data['object'] == 'page':
        for entry in data['entry']:
            for event in entry['messaging']:
                if 'message' in event:
                    sender_id = event['sender']['id']
                    
                    if 'text' in event['message']:
                        user_message = event['message']['text'].strip()
                        print(f"📩 User Typed: '{user_message}'") # ดูว่าบอทเห็นข้อความเป็นตัวอะไร
                        
                        # เช็คสินค้า (ลองเทียบแบบไม่สนตัวพิมพ์เล็กใหญ่)
                        # เช่น user พิมพ์ a001 แต่ในไฟล์เป็น A001 ก็จะเจอ
                        found_key = None
                        for key in PRODUCT_DATA:
                            if key.lower() == user_message.lower():
                                found_key = key
                                break
                        
                        if found_key:
                            print(f"✅ Found match! Key: {found_key}")
                            send_image(sender_id, PRODUCT_DATA[found_key])
                        else:
                            print(f"❌ Not found in database.")
                            # ปริ้นท์ตัวอย่างกุญแจในระบบออกมาดู 5 ตัวแรก
                            keys_sample = list(PRODUCT_DATA.keys())[:5]
                            print(f"   (Sample keys in DB: {keys_sample})")

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
    
    # ส่งข้อมูลและปรินท์ผลลัพธ์ว่า Facebook ตอบว่าอะไร
    r = requests.post("https://graph.facebook.com/v18.0/me/messages", params=params, json=data)
    print(f"📤 Sending Image Result: Status {r.status_code}")
    print(f"   Response: {r.text}")

if __name__ == '__main__':
    app.run(port=5000)
