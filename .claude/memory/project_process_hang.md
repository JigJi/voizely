---
name: process_hang_unresolved
description: Python process hangs on port 8800 after stopping bat/Task Scheduler — 5 days unresolved since 2026-03-25
type: project
---

Python web server process ค้างบน port 8800 หลัง stop bat หรือ End Task Scheduler — ปัญหานี้เกิดซ้ำทุกวันตั้งแต่ 2026-03-25 ถึง 2026-03-29 (5 วัน) ยังไม่สามารถแก้ได้

**Why:** Task Scheduler End kills bat/cmd parent แต่ child python process ไม่ตายตาม นอกจากนี้ netstat ยังแสดง phantom PID ค้างแม้ process ไม่มีจริงแล้ว ทำให้ port ค้างและ process ใหม่อาจ bind ไม่ได้หรือโหลดโค้ดเก่า

**สิ่งที่ลองแล้ว:**
- เปลี่ยนจาก Start-Process python เป็นรัน python ตรงๆ ใน bat
- สร้าง Task Scheduler แทน bat manual
- PID file approach
- taskkill /F /PID — บางครั้ง Access Denied
- ปิด uvicorn reload=True

**How to apply:** ปัญหานี้ต้องได้รับการแก้ไขอย่างจริงจัง ก่อนเสนอ solution ใหม่ ต้องทดสอบว่า End Task → process ตายจริง → Start Task → โค้ดใหม่โหลดจริง ครบ cycle
