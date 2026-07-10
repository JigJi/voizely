---
name: feedback_ui_quality
description: Always use custom styled UI, never browser default alert/confirm/prompt
type: feedback
---

ห้ามใช้ browser default alert(), confirm(), prompt() หรือ hx-confirm เด็ดขาด ต้องใช้ custom modal/notification ที่สวยและเข้ากับ theme ของ app เสมอ

**Why:** User ต้องการ UI ที่สวยงาม ใช้งานง่าย ไม่ใช้ของ default ที่ดูไม่ professional

**How to apply:** ใช้ showModal() และ showNotification() ที่สร้างไว้ใน app.js ทุกครั้งที่ต้อง alert/confirm/prompt
