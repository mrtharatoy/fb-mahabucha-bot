import os
import json
from flask import Flask, request
import requests

app = Flask(__name__)

# โหลดข้อมูลสินค้าจากไฟล์ json
with open('products.json', encoding='utf-8') as f:
    PRODUCT_DATA = json.load(f)

# ดึงค่ารหัสผ่านจาก Server Environment (เดี๋ยวเราไปตั้งค่าใน Render)
PAGE_ACCESS_TOKEN = os.environ.get('PAGE_ACCESS_TOKEN')
VERIFY_TOKEN = os.environ.get('VERIFY_TOKEN')

@app.route('/', methods=['GET'])
def verify():
    # Facebook ตรวจสอบยืนยันตัวตน
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
                        user_message = event['message']['text'].strip()
                        
                        # ตรวจสอบว่ามีคีย์เวิร์ดในฐานข้อมูลไหม
                        if user_message in PRODUCT_DATA:
                            image_url = PRODUCT_DATA[user_message]
                            send_image(sender_id, image_url)
                        else:
                            print(f"User sent: {user_message} (Not found)")
                            # ถ้าอยากให้ตอบกลับเมื่อหาไม่เจอ ให้เปิดบรรทัดล่างนี้
                            # send_text(sender_id, "ไม่พบสินค้ารหัสนี้นะครับ")
                            
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

def send_text(recipient_id, text):
    params = {"access_token": PAGE_ACCESS_TOKEN}
    data = {
        "recipient": {"id": recipient_id},
        "message": {"text": text}
    }
    requests.post("https://graph.facebook.com/v18.0/me/messages", params=params, json=data)

if __name__ == '__main__':
    app.run(port=5000)