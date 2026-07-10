---
name: project_diarization_critical
description: Deepgram wins diarization test vs Pyannote after re-encode fix — Pyannote over-splits speakers
type: project
---

ทดสอบ diarization 2026-03-30 (ห้องประชุม 4 คน, realistic 2-3 speakers):

**Deepgram (re-encode 64kbps)** → 2 speakers ✓ ถูกต้อง
**Pyannote** → 5 speakers ✗ แยกเกินซ้ำซ้อน

Deepgram ชนะทั้ง Jabra และ iPhone source (คลิป 10 นาที)

**Key discovery:** ปัญหา Deepgram ได้ 1 speaker เกิดจาก bitrate ต่ำ (32kbps) ไม่ใช่ Jabra normalize เสียง แค่ re-encode เป็น 64kbps ก็แก้ได้

**How to apply:** ใช้ Deepgram เป็น default + re-encode ก่อนส่งเสมอ ไม่ต้องพึ่ง GPU/Pyannote
