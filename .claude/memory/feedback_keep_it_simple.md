---
name: Keep solutions simple, don't overcomplicate
description: User experienced frustration from overengineered process management - keep things minimal
type: feedback
---

ห้ามสร้าง tooling/script ที่ไม่จำเป็น เช่น restart.bat, stop.bat ที่ซ้อนกันหลายชั้น

**Why:** เสียเวลาทั้งวันแก้ปัญหา process management ที่ไม่จำเป็น ทั้งที่ FastAPI มี reload=True อยู่แล้ว และ worker แค่ปิด-เปิด cmd ก็จบ user มี 30+ โปรเจค โปรเจคนี้มีปัญหามากที่สุดเพราะ overengineering

**How to apply:** ก่อนสร้างอะไรใหม่ ถามก่อนว่า "จำเป็นจริงไหม?" ถ้าวิธีเดิมใช้ได้อยู่แล้ว อย่าไปยุ่ง
