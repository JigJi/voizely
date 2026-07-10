---
name: project_speaker_profile
description: Speaker Profile DB table exists, migration from JSON files planned
type: project
---

Speaker Profile (approved 2026-04-04):

**สถานะ:**
- DB table `speaker_profiles` สร้างแล้ว (id, nickname, full_name, organization, department, position, embedding, total_seconds, num_sessions)
- Model อยู่ใน app/models/transcription.py
- React SpeakerPage ✓

**ยังไม่ได้ทำ:**
- ย้ายข้อมูลจาก voiceprints/*.json → DB table
- แก้ voiceprint_service.py ให้ใช้ DB แทน JSON file
- Dropdown แสดง "กอล์ฟ (IT - นายสมชาย)" ถ้าชื่อซ้ำ

**Why:** ชื่อเล่นเป็น key → ชื่อซ้ำ (เช่น กอล์ฟ 4 คน) ชนกัน ต้องใช้ ID เป็น key
**How to apply:** เหลือ migration จาก JSON → DB และแก้ service layer
