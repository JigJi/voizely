---
name: feedback_process_hang_failure
description: Claude Code has failed to solve the python process hanging issue for 9 consecutive days
type: feedback
---

Claude Code ไม่สามารถแก้ปัญหา python process ค้างได้เลย ตลอด 9 วัน (2026-03-25 ถึง 2026-04-02) ทั้ง web server และ worker

**Why:** ทุกวิธีที่ลอง ไม่มีอันไหนแก้ได้จริง:
- bat แก้ไข ❌
- Task Scheduler End/Start ❌
- PID file ❌
- taskkill ❌
- ปิด uvicorn reload=True ❌
- เปลี่ยนเป็น python -m uvicorn ตรงๆ ❌
- kill port ก่อน start ❌
- kill PID แล้วให้ bat restart → port phantom ค้าง ❌
- PowerShell kill by CommandLine ❌
- uvicorn --reload → crash loop ❌
- worker os.execv auto-restart → ยังไม่ได้ทดสอบ

user ต้อง kill PID เอง + End/Start ใน Task Scheduler ทุกครั้งที่แก้โค้ด Python

**How to apply:** ห้ามอ้างว่าแก้ได้แล้ว ห้ามให้ข้อมูลที่ขัดแย้งกัน ห้ามใช้ --reload เพราะทำให้ crash ปัญหานี้ยังไม่มี solution จริง วันที่ 9 แล้ว
