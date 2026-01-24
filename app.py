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

def convert_drive_link(url):
    # ฟังก์ชันแปลงลิงก์ Google Drive ให้เป็น Direct Link
    if "drive.google.com" in url and "/file/d/" in url:
        try:
            # ดึง ID ออกมาจากลิงก์
            file_id = url.split('/file/d/')[1].split('/')[0]
            # สร้างลิงก์ใหม่แบบ Direct Download
            return f"https://drive.google.com/uc?export=view&id={file_id}"
        except:
            return url
    return url

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
                        user_message = event['message']['text'].strip()
                        print(f"📩 User Typed: '{user_message}'")
                        
                        # ค้นหาในฐานข้อมูล
                        found_key = None
                        for key in PRODUCT_DATA:
                            if key.lower() == user_message.lower():
                                found_key = key
                                break
                        
                        if found_key:
                            original_url = PRODUCT_DATA[found_key]
                            # แปลงลิงก์ก่อนส่ง
                            direct_url = convert_drive_link(original_url)
                            
                            print(f"✅ Found match! Sending image...")
                            print(f"   Original: {original_url}")
                            print(f"   Converted: {direct_url}")
                            
                            send_image(sender_id, direct_url)
                        else:
                            print(f"❌ Not found: {user_message}")

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
    app.run(port=5000)