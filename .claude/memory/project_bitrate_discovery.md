---
name: project_bitrate_discovery
description: Low bitrate (32kbps) audio kills Deepgram diarization — re-encode to 64kbps+ fixes it
type: project
---

ค้นพบ 2026-03-30: Jabra บันทึกไฟล์ที่ bitrate ต่ำมาก (32kbps AAC 16kHz) ซึ่งทำลาย voiceprint จน Deepgram แยก speaker ไม่ได้ (ได้ 1 speaker)

แค่ re-encode เป็น 64kbps+ ที่ 16kHz ก็ได้ 2 speakers ทันที

**Why:** ปัญหาไม่ใช่ Jabra normalize เสียง แต่เป็น bitrate ต่ำเกินไปตอนบันทึก

**How to apply:** ก่อนส่ง Deepgram ควร re-encode audio ให้ bitrate อย่างน้อย 64kbps เสมอ Pyannote ยังดีกว่า (5 speakers vs 2) แต่ Deepgram ก็ใช้ได้ถ้า re-encode ก่อน
