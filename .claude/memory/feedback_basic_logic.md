---
name: feedback_basic_logic
description: Don't overcomplicate simple problems, think through basic logic before implementing
type: feedback
---

ห้ามทำเรื่องง่ายให้ซับซ้อน เช่น progress bar ที่กระโดด 20→30→90 ควรคิดได้ทันทีว่าต้องแก้ที่ต้นทาง (worker ส่ง % จริง) ไม่ใช่ไป fake ที่ frontend

**Why:** User หงุดหงิดมากเมื่อ basic logic ผิด เรื่องยากไม่ว่า แต่เรื่องง่ายห้ามพลาด
**How to apply:** คิดให้จบก่อน implement อย่า patch ไปเรื่อย ถ้าปัญหาอยู่ที่ backend ให้แก้ที่ backend ไม่ใช่ workaround ที่ frontend
