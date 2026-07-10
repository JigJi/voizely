---
name: feedback_no_start_processes
description: Never start web server or worker processes directly - user manages via bat files and Task Scheduler
type: feedback
---

ห้าม start web server หรือ worker process เอง ผู้ใช้จัดการผ่าน .bat files และ Task Scheduler เท่านั้น

**Why:** เคยเปิดซ้ำซ้อนจน process ชนกัน ทำให้ระบบพัง
**How to apply:** เวลาแก้โค้ดเสร็จ ให้บอกผู้ใช้ว่าต้อง restart bat ไหน อย่ารัน python/uvicorn/worker เอง ถ้าต้อง kill process เก่าให้ถามก่อน
