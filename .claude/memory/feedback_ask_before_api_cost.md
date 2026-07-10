---
name: Always ask before running API calls that cost money
description: Never run transcription/reprocess without asking - each run costs ~15 baht
type: feedback
---

ห้ามรัน process_transcription, transcribe_with_gemini, debug_transcribe หรือ API call ที่เสียเงินโดยไม่ถามก่อน

**Why:** รัน reprocess ซ้ำหลายครั้งโดยไม่ถาม ทำให้ user เสียเงินโดยไม่จำเป็น (~15 บาท/ครั้ง สำหรับไฟล์ 69 นาที)

**How to apply:** ถามก่อนทุกครั้งที่จะเรียก API ที่มี cost บอกให้ชัดว่าจะเสียเท่าไหร่
