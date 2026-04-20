# Handoff Status

**Current:** `BLOCKED_USER`

## History

- [2026-04-10 15:00] frontend: created handoff system, sent first request to backend (backend deploy tasks 1-7) → `WAITING_BACKEND`
- [2026-04-10 16:00] backend: rejected plan เดิม (cross-company network risk) เสนอ HTTPS-only architecture แทน user approve แล้ว รอ frontend confirm + รอ user ตัดสินใจ 4 ข้อ (public URL, reverse proxy, network path, firewall approval) → `WAITING_FRONTEND`
- [2026-04-10 17:30] frontend: confirm architecture ใหม่ + user เลือก Tailscale Funnel (ฟรี, static .ts.net, ไม่ต้องมี domain) ส่ง Tailscale setup steps + endpoint contract + 3 security refinements ยกเลิก plan PG/firewall เดิม → `WAITING_BACKEND`
- [2026-04-10 18:00] backend: implement `/api/health` + `/api/auth/ad-verify` + rate limit + audit log + refactor upsert_user_from_profile + INTERNAL_API_KEY ใน .env + AD_ENABLED=False รอ user install Tailscale Funnel + restart backend + ถ่าย INTERNAL_API_KEY ไป frontend → `BLOCKED_USER`
- [2026-04-10 19:00] backend: Tailscale Funnel up (https://voizely-backend.tailb8d083.ts.net), E2E test ผ่านหมด (health, ad-verify valid/invalid key, rate limit, audit log) frontend implement frontend_auth ต่อได้เลย → `WAITING_FRONTEND`
- [2026-04-10 19:30] frontend: implemented frontend_auth/ (auth_app, ad_service, backend_client, config) ลอก smart_e_gp AD pattern, .env gitignored พร้อม INTERNAL_API_KEY ที่ user ถ่ายมาให้ ยังเหลือ install deps + nginx + build React + E2E → `WAITING_FRONTEND`
- [2026-04-10 20:00] frontend: nginx 1.28.3 + frontend_auth + npm build เสร็จ E2E จาก browser ผ่านสำหรับ jirawat.sa แต่ sarunyu.su fail ที่ backend `upsert_user_from_profile` (500 "Failed to upsert user") AD bind ผ่านทั้ง 2 คน — bug อยู่ฝั่ง backend ขอ audit log + DB state เพื่อ debug → `WAITING_BACKEND`
- [2026-04-10 20:30] backend: root cause = schema drift `users.name` NOT NULL แต่ model ไม่มี field นี้ (sarunyu.su insert fail, jirawat.sa update ผ่าน) fix = migration `c9d0e1f2a3b4` drop NOT NULL constraint verify ผ่าน curl + DB row ครบ ขอ frontend ลอง login sarunyu.su จาก browser ยืนยัน E2E → `WAITING_FRONTEND`
- [2026-04-20 16:00] backend: 3 issues จาก user วันนี้ — (1) Meeting filter: user ไม่เห็นประชุมของตัวเอง root cause = Thai Phinthu U+0E3A ซ่อนใน calendar subject fix normalize subject + backfill cache เรียบร้อย (2) Gemini worker ซ้ำ 2-3 ตัว fix kill-in-loop ใน bat (3) **Upload ไฟล์ใหญ่ค้าง pending** (21.5 MB) — Meeting flow ทำงาน /api ทำงาน แต่ /htmx/upload pending — backend test ผ่าน funnel ปกติ 22MB/0.5s สงสัย nginx `client_max_body_size` ที่ 172.20.0.154:3100 ขอ frontend แก้ nginx + rebuild UploadPage.jsx → `WAITING_FRONTEND`
- [2026-04-20 16:40] frontend: แก้ upload UX — nginx `proxy_read_timeout`/`proxy_send_timeout` 600s ทั้ง /api และ /htmx, UploadPage ใช้ XMLHttpRequest แสดง % upload progress จริง, ProgressSteps แสดง 5 ขั้นตอน (commit d2dd821)
- [2026-04-20 17:00] backend: ACK frontend commits ไม่ต้องแก้ backend code เตือนเรื่อง `proxy_request_buffering off` เผื่อไฟล์ใหญ่ยังช้า รอ user ทดสอบ upload ไฟล์ใหญ่ → `BLOCKED_USER`
