---
name: feedback_fix_before_retest
description: Fix bugs before user retests, don't wait until after
type: feedback
---

ถ้ารู้ว่ามี bug ต้องแก้ ให้แก้ก่อนที่ user จะกด retest ไม่ใช่รอให้ process เสร็จแล้วค่อยแก้ เสียเวลา user ซ้ำซ้อน

**Why:** User ต้องรอ process นาน (ไฟล์ 1 ชม.) ถ้าไม่แก้ก่อน retest ก็ต้องรอใหม่อีกรอบ
**How to apply:** เมื่อ user จะกด retry/retest ให้แก้ bug ที่รู้อยู่แล้วให้หมดก่อน แล้วค่อยให้ user กด
