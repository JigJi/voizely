---
name: feedback_accuracy
description: User rates system 80% satisfaction. Accepts imperfect transcript if summary/gist is good. Issues with quiet voice and overlapping speech.
type: feedback
---

ผู้ใช้ประเมินระบบ 80% พอใจ, ยอมรับว่า raw transcript ไม่ต้อง perfect — จับใจความได้ สรุปได้ก็โอเค

ข้อดี:
- พูดคนเดียว ไม่ซ้อนกัน = 90%+ accuracy
- Speaker diarization ทำงานได้ดี

ปัญหาที่เหลือ:
1. เสียงเบา → ถอดไม่ได้ / ผิด
2. พูดพร้อมกัน (overlapping speech) → ถอดไม่ได้

**Why:** ภาษาไทยปนอังกฤษยาก แม้ Google/Microsoft ก็แค่ 55-70%, ข้อจำกัดของ Whisper กับเสียงซ้อน
**How to apply:** โฟกัส usability (สรุป, key points, แก้ไขง่าย) มากกว่าไล่ accuracy ทีละ %
