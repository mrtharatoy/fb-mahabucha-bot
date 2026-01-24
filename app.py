import os
import requests
from flask import Flask, request

app = Flask(__name__)

# ตั้งค่า GitHub
GITHUB_USERNAME = "mrtharatoy" 
REPO_NAME = "fb-mahabucha-bot"
BRANCH = "main"
FOLDER_NAME = "images"  # <--- ชื่อโฟลเดอร์ที่เก็บรูป (เปลี่ยนได้ตามใจชอบ)

PAGE_ACCESS_TOKEN = os.environ.get('PAGE_ACCESS_TOKEN')
VERIFY_TOKEN = os.environ.get('VERIFY_TOKEN')

def get_github_image_url(product_code):
    # ลิงก์จะหน้าตาเป็น .../main/images/A001.jpg
    return f"https://raw.githubusercontent.com/{GITHUB_USERNAME}/{REPO_NAME}/{BRANCH}/{FOLDER_NAME}/{product_code}.jpg"

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
                        user_message = event['message']['text'].strip().upper()
                        print(f"📩 User Typed: '{user_message}'")
                        
                        image_url = get_github_image_url(user_message)
                        
                        # เช็คว่ามีรูปจริงไหม (เพื่อความชัวร์)
                        check = requests.head(image_url)
                        if check.status_code == 200:
                            print(f"✅ Found image in folder '{FOLDER_NAME}': {image_url}")
                            send_image(sender_id, image_url)
                        else:
                            print(f"❌ Image not found in folder: {image_url}")
                            # (Optional) ถ้าอยากแจ้งเตือนลูกค้าเมื่อหาไม่เจอ ให้เปิดบรรทัดล่างนี้
                            # send_text(sender_id, "ไม่พบข้อมูลสินค้านี้ครับ")

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