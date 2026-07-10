---
name: Task Scheduler useless for dev restart
description: Task Scheduler stop/start does NOT kill python processes — must kill PID directly or run from admin terminal
type: feedback
---

Task Scheduler stop/start ไม่ช่วย restart service สำหรับโปรเจคนี้ เพราะ stop task แค่หยุด bat แต่ไม่ฆ่า python process ที่ถูก spawn ออกมา

**Why:** Process เก่าค้างยึด port ทำให้โค้ดใหม่ไม่ถูกโหลด ผู้ใช้เสียเวลาหลายรอบกับ stop/start ที่ไม่ได้ผล

**How to apply:**
- อย่าแนะนำให้ restart ผ่าน Task Scheduler เด็ดขาด
- เมื่อต้อง restart ให้บอกว่าต้องฆ่า python PID โดยตรง (ต้อง admin rights)
- แนะนำให้รัน bat จาก admin terminal แทน Task Scheduler เพื่อ dev/test (Ctrl+C ฆ่าได้ทันที)
- ห้ามใช้ `taskkill /F /IM python.exe` แบบ kill ทุก python — kill เฉพาะ PID ที่ bind port
- Task Scheduler tasks: Speech Text - Web, Speech Text - Worker, SRT - Chatbot
- Worker output ดูไม่ได้จาก cmd → ต้อง log ลงไฟล์
