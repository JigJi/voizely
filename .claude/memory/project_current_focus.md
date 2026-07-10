---
name: project_current_focus
description: Deepgram default diarization with re-encode, no GPU dependency preferred
type: project
---

Pipeline ปัจจุบัน (2026-03-30):
1. Re-encode audio → 64kbps 16kHz (ป้องกัน low bitrate ทำลาย diarization)
2. Deepgram Nova-3 → diarization (default, API)
3. Gemini 2.5 Flash → transcription + MoM

User ไม่อยากใช้ GPU (Pyannote) เพราะคุมยากและค่าใช้จ่ายสูงกว่า ชอบ API-based มากกว่า

**Why:** ผลิตภัณฑ์ต้องการระบุว่าใครพูดอะไร re-encode เป็น step สำคัญที่ค้นพบว่าแก้ปัญหา diarization ล้มเหลวจาก low bitrate audio
**How to apply:** Deepgram เป็น default, re-encode ทุกไฟล์ก่อนส่ง
