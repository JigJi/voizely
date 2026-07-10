---
name: Handoff mailbox between frontend/backend Claude
description: How to coordinate with the Claude agent on the frontend machine via git-based _handoff/ directory
type: project
originSessionId: a986ebf0-8677-4f7a-a853-da13ac4b1b83
---
**ระบบ:** Voizely deploy 2 เครื่อง — frontend (172.20.0.154) และ backend (เครื่องนี้) มี Claude คนละคนทำงานแต่ละเครื่อง coordinate ผ่าน git repo เดียวกัน

**Path:** `_handoff/` ใน project root
- `README.md` — protocol (ห้ามแก้)
- `frontend_to_backend.md` — frontend เขียนเท่านั้น, backend อ่าน (inbox ของเรา)
- `backend_to_frontend.md` — backend เขียนเท่านั้น, frontend อ่าน (outbox ของเรา)
- `status.md` — state machine ปัจจุบัน (WAITING_BACKEND / WAITING_FRONTEND / BLOCKED_USER / DONE)

**Why:** user ไม่ต้องถือสาร copy/paste เอง ข้อความทุกครั้งมี audit trail, append-only กันเขียนทับ, แยกไฟล์กันคน merge conflict

**How to apply:**
- User พิมพ์ "handoff" / "ทำ handoff" / "ส่งให้ frontend" / "ปกติเราทำงานกันแบบนั้น" = ต้องเขียนข้อความใน `_handoff/backend_to_frontend.md` + update `status.md` + git commit + push
- Workflow:
  1. `git stash push -u -m "wip"` ถ้ามี unstaged
  2. `git pull --rebase`
  3. `git stash pop`
  4. Append message ใน `backend_to_frontend.md` header format `## [YYYY-MM-DD HH:MM] FROM: backend`
  5. Update `status.md` history + current state
  6. `git add _handoff/ <related-code>` แล้ว commit + push
- อย่า commit ไฟล์ที่ไม่ได้แก้เอง (e.g., pre-existing unstaged changes ของ user) — ใช้ `git add` ระบุไฟล์ไม่ใช่ `git add -A`
- ห้ามใส่ secret/password/API key ในไฟล์ handoff
