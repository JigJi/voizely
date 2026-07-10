---
name: feedback_never_restart
description: NEVER suggest restarting the machine — hundreds of tasks/projects running simultaneously
type: feedback
---

ห้ามแนะนำให้ restart เครื่องเด็ดขาด เครื่องนี้เป็น server ที่มี process และ project รันพร้อมกันเป็นร้อย

**Why:** user มี Task Scheduler tasks, services, และ project อื่นๆ ทำงานอยู่ตลอดเวลา restart เครื่องจะกระทบทุกอย่าง

**How to apply:** ต้องหาทางแก้ปัญหาโดยไม่ restart เครื่อง เสมอ
