---
name: feedback_bat_quoting
description: Windows bat files can't pipe/awk/grep inside WSL commands - use temp file approach instead
type: feedback
---

Bat file ไม่สามารถ pipe command ใน WSL ได้ถูกต้อง (awk, grep -oP, cut ฯลฯ) เพราะ quoting ชนกันระหว่าง cmd.exe กับ bash

**Why:** ปัญหาซ้ำหลายรอบ — PG_HOST ได้ค่าว่างทำให้ worker ต่อ DB ไม่ได้
**How to apply:** ใช้วิธีเขียนผลลัพธ์ลงไฟล์ใน WSL แล้วอ่านจากไฟล์ใน bat แทน (`set /p VAR=<file`)
