---
name: Never kill all python processes
description: Never suggest taskkill /IM python.exe - user runs many projects simultaneously
type: feedback
---

ห้ามแนะนำ `taskkill /F /IM python.exe` เด็ดขาด เพราะ user รันหลายโปรเจคพร้อมกัน (10+ โปรเจค) การ kill python ทั้งหมดจะทำให้โปรเจคอื่นพังด้วย

**Why:** แนะนำไปแล้วทำให้โปรเจคอื่นพังหมด เป็นความผิดร้ายแรง

**How to apply:** ต้อง kill เฉพาะ PID เท่านั้น ใช้ `taskkill /F /PID <xxx>` หรือ kill ผ่าน port ที่รู้
