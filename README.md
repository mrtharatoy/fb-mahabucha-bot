# Siamganesh Online Backend

Flask backend สำหรับรับ-ส่งภาพพิธีกรรมผ่าน Facebook Messenger อัตโนมัติ รองรับ 2 เพจ ได้แก่ **มหาบูชา** และ **มูเตทีม**

---

## สถาปัตยกรรมโดยรวม

```
Facebook Messenger
       │  (Webhook POST)
       ▼
  app.py (Flask)
       │
       ├── process_mahabucha()   ← เพจมหาบูชา (รหัสองค์เทพ)
       │       └── ค้น CACHED_FILES["mahabucha"] → ส่งภาพ
       │
       ├── process_muteteam()    ← เพจมูเตทีม (รหัสจอง 12 หลัก)
       │       ├── ค้น CACHED_FILES["muteteam"] → ส่งภาพ
       │       ├── Supabase → ดึงชื่อผู้ศรัทธา
       │       └── Gemini AI → สร้างข้อความขอบคุณ
       │
       └── CACHED_FILES (in-memory)
               └── โหลดจาก GitHub API (images/mahabucha/, images/muteteam/)
```

---

## Tech Stack

| รายการ | รายละเอียด |
|--------|-----------|
| Runtime | Python 3 |
| Framework | Flask + Flask-CORS |
| Web Server | Gunicorn |
| Image Storage | GitHub Repository (`images/`) |
| Database | Supabase (ข้อมูลการจอง) |
| AI | Google Gemini 1.5 Flash (สร้างข้อความ) |
| Bot Channel | Facebook Messenger (Graph API v19.0) |

---

## โครงสร้างไฟล์

```
siamganesh-online-backend/
├── app.py              # แอปหลัก (Flask)
├── requirements.txt    # Python dependencies
└── images/
    ├── mahabucha/      # ภาพถาดถวายเพจมหาบูชา
    │   └── <deity_code>.jpg
    └── muteteam/       # ภาพถาดถวายเพจมูเตทีม
        └── <booking_code>_<n>.webp
```

---

## Environment Variables

ต้องตั้งค่า environment variables ต่อไปนี้ก่อน deploy:

| ตัวแปร | คำอธิบาย |
|--------|---------|
| `MAHABUCHA_PAGE_ID` | Facebook Page ID ของเพจมหาบูชา |
| `MAHABUCHA_TOKEN` | Page Access Token ของเพจมหาบูชา |
| `MUTETEAM_PAGE_ID` | Facebook Page ID ของเพจมูเตทีม |
| `MUTETEAM_TOKEN` | Page Access Token ของเพจมูเตทีม |
| `VERIFY_TOKEN` | Token สำหรับ verify Facebook Webhook |
| `GITHUB_TOKEN` | GitHub Personal Access Token (สำหรับอ่าน/เขียนไฟล์ภาพ) |
| `GEMINI_API_KEY` | Google Gemini API Key |
| `SUPABASE_URL` | Supabase Project URL |
| `SUPABASE_KEY` | Supabase Service Key |

---

## API Endpoints

### `GET /`
Health check และ Facebook Webhook verification

```
?hub.verify_token=<VERIFY_TOKEN>&hub.challenge=<challenge>
```

---

### `POST /`
Facebook Webhook — รับ messaging events จาก Messenger

**Flow มหาบูชา:** ดักข้อความที่มีรหัสรูปแบบ `(269|999)[a-z]{2}01-20[0-9]{3}` เช่น `269aa01234`
→ ค้นหาภาพจาก cache → ส่งภาพกลับ

**Flow มูเตทีม:** ดักข้อความที่มีรหัสจอง 12 หลัก `YYMMDDHHmmss` เช่น `260519142238`
→ ค้นหาภาพทุก index (_1, _2, _3...) → ดึงชื่อจาก Supabase → ให้ Gemini สร้างข้อความ → ส่งภาพ

---

### `GET /api/search`
ค้นหาภาพตามรหัส

| Parameter | ค่า |
|-----------|-----|
| `page` | `mahabucha` หรือ `muteteam` |
| `code` | รหัสองค์เทพ หรือรหัสจอง |

**ตัวอย่าง:**
```
GET /api/search?page=muteteam&code=260519142238
GET /api/search?page=mahabucha&code=269aa01234
```

**Response (พบ):**
```json
{
  "found": true,
  "results": [
    { "code": "260519142238_1", "image_url": "https://raw.githubusercontent.com/..." }
  ],
  "count": 3
}
```

---

### `POST /api/reload`
บังคับโหลด image list ใหม่จาก GitHub (background thread)

```json
{ "message": "กำลัง reload cache..." }
```

---

### `POST /api/upload-image`
อัปโหลดภาพเข้า `images/muteteam/` บน GitHub

**Request Body:**
```json
{
  "booking_code": "260519142238",
  "images": [
    { "index": 1, "ext": "webp", "data": "<base64>" },
    { "index": 2, "ext": "webp", "data": "<base64>" }
  ]
}
```

**Response:**
```json
{
  "success": true,
  "uploaded": ["260519142238_1.webp", "260519142238_2.webp"],
  "errors": [],
  "message": "อัปโหลดสำเร็จ 2/2 รูป"
}
```

---

### `GET /api/generate-message`
สร้างข้อความขอบคุณส่วนตัวด้วย Gemini AI

```
GET /api/generate-message?booking_code=260519142238
```

**Response:**
```json
{
  "success": true,
  "booking_code": "260519142238",
  "person1_name": "สมชาย",
  "person2_name": "สมหญิง",
  "message": "📸 ขออนุญาตส่งมอบความสิริมงคลแด่คุณสมชายและสมหญิงครับ ..."
}
```

---

### `GET /api/debug-gemini`
ทดสอบการเชื่อมต่อ Gemini API โดยตรง

```
GET /api/debug-gemini?booking_code=260519142238
```

---

## รูปแบบรหัสภาพ

### มหาบูชา
- Pattern: `(269|999)[a-z]{2}(01-20)[0-9]{3}`
- ตัวอย่าง: `269aa01234`, `999bc15001`
- ไฟล์: `images/mahabucha/<code>.jpg`

### มูเตทีม
- Pattern: 12 หลัก `YYMMDDHHmmss`
- ตัวอย่าง: `260519142238` → ไฟล์ `260519142238_1.webp`, `260519142238_2.webp`, ...
- ไฟล์: `images/muteteam/<booking_code>_<n>.webp`

---

## Image Cache

- ภาพทั้งหมดถูก serve จาก GitHub Raw Content (`raw.githubusercontent.com`)
- Bot โหลด file list จาก GitHub API เมื่อเริ่มต้น และ refresh ทุกครั้งที่มีการ upload
- `CACHED_FILES` เก็บ mapping `{name_no_ext: filename}` แยกตามเพจ

---

## Local Development

```bash
# ติดตั้ง dependencies
pip install -r requirements.txt

# ตั้งค่า environment variables
export MAHABUCHA_PAGE_ID=...
export MAHABUCHA_TOKEN=...
export MUTETEAM_PAGE_ID=...
export MUTETEAM_TOKEN=...
export VERIFY_TOKEN=...
export GITHUB_TOKEN=...
export GEMINI_API_KEY=...
export SUPABASE_URL=...
export SUPABASE_KEY=...

# รัน development server
python app.py

# หรือรัน production-like ด้วย Gunicorn
gunicorn app:app --bind 0.0.0.0:5000
```

---

## Dependencies

```
Flask
requests
gunicorn
flask-cors
```
