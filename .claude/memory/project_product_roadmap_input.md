---
name: project_product_roadmap_input
description: Input improvement research complete — multichannel needs beamforming R&D, not plug & play
type: project
---

สรุปการวิจัยฝั่ง input (2026-03-30):

**ปัจจุบัน (MVP):** Deepgram + re-encode 64kbps → ได้ 2-3 speakers จาก mono ใช้งานได้

**Multi-channel research:**
- Jabra/conference speakers → mix เป็น mono ไม่สามารถดึง raw channel ได้
- มือถือ → OS mix เป็น mono ต้องมี app เฉพาะ
- Mic array (ReSpeaker ~2,500 บาท, Sipeed R6+1 ~500 บาท) → ได้ multi-channel แต่ต้องทำ beamforming เอง ไม่ใช่ plug & play เป็นงาน R&D

**สรุป:** Hardware bundle เก็บไว้ phase ถัดไป ตอนนี้ Deepgram + re-encode ดีพอสำหรับ MVP

**How to apply:** อย่าสัญญาลูกค้าเรื่อง perfect speaker diarization จาก mono audio ถ้าต้องการแม่น 99% ต้องรอ multi-channel solution
