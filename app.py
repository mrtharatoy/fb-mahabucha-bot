{\rtf1\ansi\ansicpg874\cocoartf2867
\cocoatextscaling0\cocoaplatform0{\fonttbl\f0\fswiss\fcharset0 Helvetica;}
{\colortbl;\red255\green255\blue255;}
{\*\expandedcolortbl;;}
\paperw11900\paperh16840\margl1440\margr1440\vieww11520\viewh8400\viewkind0
\pard\tx720\tx1440\tx2160\tx2880\tx3600\tx4320\tx5040\tx5760\tx6480\tx7200\tx7920\tx8640\pardirnatural\partightenfactor0

\f0\fs24 \cf0 import os\
import json\
from flask import Flask, request\
import requests\
\
app = Flask(__name__)\
\
# \uc0\u3650 \u3627 \u3621 \u3604 \u3586 \u3657 \u3629 \u3617 \u3641 \u3621 \u3626 \u3636 \u3609 \u3588 \u3657 \u3634 \u3592 \u3634 \u3585 \u3652 \u3615 \u3621 \u3660  json\
with open('products.json', encoding='utf-8') as f:\
    PRODUCT_DATA = json.load(f)\
\
# \uc0\u3604 \u3638 \u3591 \u3588 \u3656 \u3634 \u3619 \u3627 \u3633 \u3626 \u3612 \u3656 \u3634 \u3609 \u3592 \u3634 \u3585  Server Environment (\u3648 \u3604 \u3637 \u3659 \u3618 \u3623 \u3648 \u3619 \u3634 \u3652 \u3611 \u3605 \u3633 \u3657 \u3591 \u3588 \u3656 \u3634 \u3651 \u3609  Render)\
PAGE_ACCESS_TOKEN = os.environ.get('PAGE_ACCESS_TOKEN')\
VERIFY_TOKEN = os.environ.get('VERIFY_TOKEN')\
\
@app.route('/', methods=['GET'])\
def verify():\
    # Facebook \uc0\u3605 \u3619 \u3623 \u3592 \u3626 \u3629 \u3610 \u3618 \u3639 \u3609 \u3618 \u3633 \u3609 \u3605 \u3633 \u3623 \u3605 \u3609 \
    if request.args.get("hub.mode") == "subscribe" and request.args.get("hub.challenge"):\
        if request.args.get("hub.verify_token") == VERIFY_TOKEN:\
            return request.args.get("hub.challenge"), 200\
    return "Bot is running!", 200\
\
@app.route('/', methods=['POST'])\
def webhook():\
    data = request.json\
    if data['object'] == 'page':\
        for entry in data['entry']:\
            for event in entry['messaging']:\
                if 'message' in event:\
                    sender_id = event['sender']['id']\
                    if 'text' in event['message']:\
                        user_message = event['message']['text'].strip()\
                        \
                        # \uc0\u3605 \u3619 \u3623 \u3592 \u3626 \u3629 \u3610 \u3623 \u3656 \u3634 \u3617 \u3637 \u3588 \u3637 \u3618 \u3660 \u3648 \u3623 \u3636 \u3619 \u3660 \u3604 \u3651 \u3609 \u3600 \u3634 \u3609 \u3586 \u3657 \u3629 \u3617 \u3641 \u3621 \u3652 \u3627 \u3617 \
                        if user_message in PRODUCT_DATA:\
                            image_url = PRODUCT_DATA[user_message]\
                            send_image(sender_id, image_url)\
                        else:\
                            print(f"User sent: \{user_message\} (Not found)")\
                            # \uc0\u3606 \u3657 \u3634 \u3629 \u3618 \u3634 \u3585 \u3651 \u3627 \u3657 \u3605 \u3629 \u3610 \u3585 \u3621 \u3633 \u3610 \u3648 \u3617 \u3639 \u3656 \u3629 \u3627 \u3634 \u3652 \u3617 \u3656 \u3648 \u3592 \u3629  \u3651 \u3627 \u3657 \u3648 \u3611 \u3636 \u3604 \u3610 \u3619 \u3619 \u3607 \u3633 \u3604 \u3621 \u3656 \u3634 \u3591 \u3609 \u3637 \u3657 \
                            # send_text(sender_id, "\uc0\u3652 \u3617 \u3656 \u3614 \u3610 \u3626 \u3636 \u3609 \u3588 \u3657 \u3634 \u3619 \u3627 \u3633 \u3626 \u3609 \u3637 \u3657 \u3609 \u3632 \u3588 \u3619 \u3633 \u3610 ")\
                            \
    return "ok", 200\
\
def send_image(recipient_id, image_url):\
    params = \{"access_token": PAGE_ACCESS_TOKEN\}\
    headers = \{"Content-Type": "application/json"\}\
    data = \{\
        "recipient": \{"id": recipient_id\},\
        "message": \{\
            "attachment": \{\
                "type": "image",\
                "payload": \{"url": image_url, "is_reusable": True\}\
            \}\
        \}\
    \}\
    requests.post("https://graph.facebook.com/v18.0/me/messages", params=params, json=data)\
\
def send_text(recipient_id, text):\
    params = \{"access_token": PAGE_ACCESS_TOKEN\}\
    data = \{\
        "recipient": \{"id": recipient_id\},\
        "message": \{"text": text\}\
    \}\
    requests.post("https://graph.facebook.com/v18.0/me/messages", params=params, json=data)\
\
if __name__ == '__main__':\
    app.run(port=5000)}