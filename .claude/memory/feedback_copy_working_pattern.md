---
name: feedback_copy_working_pattern
description: Always copy patterns from working projects (like data_connect) instead of inventing new approaches
type: feedback
---

เมื่อมีโปรเจคที่ทำงานได้ดีอยู่แล้ว (เช่น data_connect) ให้ดูโครงสร้างของมันแล้วทำตาม ไม่ต้องคิดวิธีใหม่

**Why:** speech_text ใช้ `python -m app` → `uvicorn.run(reload=True)` ซึ่งสร้าง child process ที่ kill ไม่ตาม ทำให้เสียเวลา 5 วัน ทั้งที่ data_connect ใช้ `python -m uvicorn` ตรงๆ แล้วไม่เคยมีปัญหาเลย

**How to apply:** ก่อนออกแบบ server startup ให้ดูโปรเจคอื่นของ user ที่ทำงานได้ดีก่อนเสมอ แล้วทำตามแบบเดียวกัน
