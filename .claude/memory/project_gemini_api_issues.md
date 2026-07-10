---
name: project_gemini_api_issues
description: Gemini API sometimes returns truncated/invalid JSON — mitigations applied
type: project
---

Gemini API ผ่าน OpenRouter มีปัญหาเป็นระยะ (เจอ 2026-04-03):

**ปัญหา:**
- Response ถูกตัดก่อนจบ → JSON parse fail (Unterminated string)
- Response มี control character → Invalid control character
- บาง chunk ค้าง timeout ไม่ตอบ

**แก้ไขที่ทำแล้ว:**
- `json.loads(raw, strict=False)` — รับ control character ได้
- Chunk size ลดจาก 10 นาที → 5 นาที — ลด output ต่อ chunk
- API timeout ลดจาก 600s → 180s — ไม่ค้างนาน
- Retry 3 ครั้ง + JSON recovery (rsplit) — กู้ truncated JSON

**How to apply:** ถ้าเจอ error "Unterminated string" หรือ "Invalid control character" ให้ลอง retry ก่อน อาจเป็นปัญหาชั่วคราวของ API
