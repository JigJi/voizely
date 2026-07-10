---
name: Frontend port 3000 only
description: Frontend runs on port 3000 (Vite dev / React), backend API on port 8800. NEVER serve frontend from 8800.
type: feedback
---

Frontend ใช้ port 3000 เท่านั้น (React + Vite dev server) proxy API ไป backend port 8800
ไม่ใช้ frontend เก่าที่ serve จาก port 8800 อีกแล้ว

**Why:** ระบบเปลี่ยนจาก Jinja2 templates (serve จาก FastAPI port 8800) เป็น React SPA (port 3000) แล้ว เรื่องนี้พูดหลายรอบแต่ยังลืม

**How to apply:**
- Vite config proxy: `/api` → `http://127.0.0.1:8800`
- User เข้าเว็บที่ `http://localhost:3000`
- ห้ามแนะนำให้เข้า `http://localhost:8800` เด็ดขาด
- start_web.bat รัน uvicorn port 8800 (backend only)
