---
name: Always memo work done + next steps
description: User wants me to save memory every session about what was done and what's pending — not rely on conversation context which disappears between sessions
type: feedback
originSessionId: a986ebf0-8677-4f7a-a853-da13ac4b1b83
---
ทุกครั้งที่ทำงานเสร็จหรือก่อนจบ session ให้ **save memory สรุปสั้นๆ** ว่า:
- ทำอะไรไปบ้าง (โดยเฉพาะสิ่งที่ไม่ได้อยู่ใน git log / handoff file)
- ยังเหลืออะไรต้องทำ / รออะไร
- เกร็ดที่ไม่ชัดจาก code (gotchas, non-obvious decisions)

**Why:** user บอกตรงๆว่า "คุณต้อง memo ไว้เสมอนะ ว่าทำอะไรไปบ้าง ต้องทำไง ไม่งั้นคุณลืมตัวเองตลอด" — เคยเจอปัญหาที่ผมกลับมา session ใหม่แล้วเดาใหม่เพราะไม่มี memory เก่าช่วย

**How to apply:**
- ก่อนจบ session ที่มีการแก้ bug / deploy / handoff — write project memory อย่างน้อย 1 ไฟล์
- ถ้า user ให้ feedback เรื่องพฤติกรรม (วิธีคิด/วิธีตอบ/สิ่งที่ทำซ้ำ) — write feedback memory ทันที
- ไม่ต้อง duplicate สิ่งที่อยู่ใน `_handoff/` หรือ CLAUDE.md แล้ว — memo เฉพาะสิ่งที่ไม่มีที่อื่น
