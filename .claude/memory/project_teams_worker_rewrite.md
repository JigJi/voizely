---
name: Teams worker rewrite needed
description: Current teams_worker scans OneDrive folders per user — misses meetings where user didn't record. Need to rewrite to query from meeting perspective
type: project
---

**ปัญหา:** `teams_worker.py` ปัจจุบัน scan `OneDrive/Recordings/` ของแต่ละ user ที่ login Voizely → assume ว่า user = คนอัด แต่จริงๆ role คนละคน ทำให้ user A เข้าประชุมกับ B และ B อัด → A เห็นไฟล์ไม่ได้เลย

**Context ที่ discover ปัญหา:** 2026-04-10 จิ๊กหาไฟล์ประชุม `Test-20260410_134622` ไม่เจอ ปรากฏว่า Ponglit Viriyapong เป็นคนอัด (ไม่อยู่ใน users DB) → worker ไม่ poll OneDrive ของเขา → หาย

**ทางแก้ที่ถูก:** เปลี่ยน query pattern จาก OneDrive folder → meeting perspective ผ่าน Graph API

Permission ที่ Appworks Azure app มีครบแล้ว (ยืนยัน 2026-04-10):
- OnlineMeetings.Read.All
- OnlineMeetingRecording.Read.All
- OnlineMeetingTranscript.Read.All ← bonus ใช้ transcript แทน download audio ได้
- CallRecords.Read.All
- Chat.Read.All
- Calendars.Read + ReadBasic.All

**Approach:**
```
สำหรับแต่ละ user ที่ active ใน DB:
  GET /users/{email}/events หรือ /users/{email}/onlineMeetings
  → list meetings ที่ user นี้เป็น attendee
  → สำหรับ meeting ที่มี recording: เก็บ metadata + attendees (ไม่ download)
  → User login ใน Voizely จะเห็นทุก meeting ที่ตัวเองเข้าร่วม ไม่ว่าใครอัด
```

**Bonus path:** ถ้า Teams transcribe ไว้ให้แล้ว ใช้ `OnlineMeetingTranscript.Read.All` ดึง transcript ตรงๆ → ไม่ต้องเรียก Deepgram+Gemini (ลดต้นทุน + เร็ว) แต่ต้องเช็คคุณภาพ transcript ภาษาไทยของ Teams ก่อน

**Why:** scalability (ไม่ต้อง bulk sync 200 users), ครอบคลุม (user ที่ไม่เคย login Voizely อัดก็เห็นได้), ตรงกับที่ Teams UI แสดงให้ user

**How to apply:** งานใหญ่ rewrite `teams_worker.py` + `app/services/meeting_platforms/teams_client.py` ทำหลัง frontend deploy เสร็จ
