---
name: voiceprint-quality-gate-needed
description: "Voiceprint auto-enroll from mono recordings produces garbage profiles, need quality gate before enrolling"
metadata: 
  node_type: memory
  type: project
  originSessionId: ffd7b17c-d6a7-459e-8a3c-067330daba57
---

ปัญหา: mono Teams recordings ทำให้ voice sample ของแต่ละคนมีเสียงคนอื่นปน → ยิ่งเก็บเยอะ profile ยิ่งเป็นเสียงเฉลี่ยทุกคน → แนะนำชื่อผิด

**Quality gate ที่ต้องทำ:**
- segment สั้น < 3 วินาที → ไม่เก็บ
- segment ที่น่าจะ overlap กับคนอื่น → ไม่เก็บ
- embedding ที่เป็น outlier ห่างจาก centroid ของ speaker → ไม่เก็บ
- confidence score ต่ำ → ไม่เก็บ

**Why:** ทดสอบกับ ID 142 voiceprint แนะนำ "พัด" ทุก speaker เพราะ profile ถูก contaminate จากเสียง mono mix ได้ถูกแค่ 1/4

**How to apply:** ต้อง focus ทำ quality gate ให้ดีกับ mono (โลกจริงส่วนใหญ่เป็น mono) ไม่ต้องรอ multi-channel

**กฎสำคัญ (Jig ย้ำ 2026-06-15):** voiceprint **ห้าม auto-ใส่ชื่อจริงลง speaker** (commit 386b955 ถอด auto-rename แล้ว) — ชื่อต้อง user กดยืนยัน **manual** เท่านั้น, voiceprint เป็นได้แค่ `voiceprint_suggestions` (โชว์ "Speaker N อาจเป็น X (score)"). **แต่** ใช้ voiceprint ช่วย **diarization** ได้ (auto): match embedding เพื่อ **รวม cluster ที่ spectral ซอยคนเดียวเป็นหลายก้อน** (bench #218: spectral 4 คน แต่ Speaker 1+3 = Anusara 0.83/0.97 → รวมเหลือ 3, label ยัง generic). **แยกชัด: รวม/แยกเสียง=auto ได้, ตั้งชื่อ=manual.** experiment `experiments/voiceprint_anchor.py <tid>` (generic label + suggestion only). DB มี voiceprint 29 ตัว, bench มี 2/4 คนที่ชัด → enroll ครบ/สะอาด = คันโยกหลักดัน diarization mono.

**⚠️ voiceprint auto-merge ไม่น่าเชื่อถือ (2026-06-15):** ลองบน iPhone recording (#223, spectral แยกได้ 4 คนสวย 4/10/7/12) → voiceprint-merge **ดันทั้ง 4 cluster ไปตรง Jirawat หมด (0.77-0.88) → ยุบเหลือ 1 คน = พังยับ**. profile ปนเปื้อน/acoustic ของ iPhone ทำ embedding เบ้. คนละผลกับ bench #218 (cloud) ที่ merge Anusara ถูก → **auto-merge เอาแน่ไม่ได้ ขึ้นกับไฟล์/คุณภาพ profile**. สรุป: **voiceprint = suggestion manual เท่านั้น ห้าม auto-merge/auto-name** (ตรงกับที่ Jig ย้ำ). spectral ดิบ (#223 4 คน) ดีกว่า voiceprint-merged สำหรับไฟล์นี้. ไฟล์อัดจริง iPhone (mic ในห้อง, 65kbps) แยกเสียง local Pathumma ได้ 4 คนสวยกว่า Teams mono mix (bench) ชัด.
