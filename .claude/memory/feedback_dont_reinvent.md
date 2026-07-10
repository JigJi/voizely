---
name: Don't reinvent working solutions when scaling
description: When adapting working code for larger scale, keep the exact same flow - just chunk it
type: feedback
---

เมื่อ pipeline ใช้ได้ดีแล้ว อย่าเปลี่ยน flow ตอน scale up ให้แค่หั่นงานเป็นท่อนสั้นๆ แล้วใช้ flow เดิมทุกประการ

**Why:** ตอนทำ chunking สำหรับไฟล์ยาว ไปเปลี่ยน timestamp เป็น relative, เพิ่ม function assign speaker ใหม่ ทำให้พัง ทั้งที่ flow เดิม (absolute timestamp + Gemini follow guide) ใช้ได้ดีอยู่แล้ว

**How to apply:** ถ้าของเดิมใช้ได้ → แค่หั่น + loop ด้วย flow เดิม อย่าสร้าง logic ใหม่
