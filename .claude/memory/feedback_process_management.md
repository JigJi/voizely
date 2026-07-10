---
name: feedback_process_management
description: Kill old processes before restart - Windows/WSL python processes don't die when closing bat
type: feedback
---

ปิด bat file แล้ว python process ไม่ตาย ทั้ง Windows และ WSL — ต้อง kill PID ก่อนเปิดใหม่เสมอ

**Why:** ผู้ใช้เสียเวลา 3 วันเพราะ zombie process ยึด port/GPU อยู่ restart bat ไม่มีผล
**How to apply:** เวลาแนะนำให้ restart ต้อง check process ที่รันอยู่ก่อน (`netstat`, `tasklist`, `wsl ps aux`) แล้ว kill ตัวเก่าให้ด้วย ไม่ใช่แค่บอกให้ restart bat
