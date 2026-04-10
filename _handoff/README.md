# Handoff Protocol — Frontend Agent ⇄ Backend Agent

ระบบ message bus ระหว่าง Claude 2 instance ที่รันบน 2 เครื่อง (frontend host และ backend host) ของ Voizely โดยใช้ git repo เดียวกันเป็น mailbox

## ทำไมมีไฟล์นี้

Voizely แยก deploy 2 เครื่อง — frontend (เครื่องเดียวที่ต่อ AD ได้) กับ backend (GPU + Postgres + workers) แต่ละ Claude อยู่บนคนละเครื่องและทำงานกันคนละด้าน เลยต้องคุยกันเพื่อ coordinate deploy/config user เป็นคนกลางได้แต่จะเหนื่อย/ลืม/copy ผิด → ใช้ git mailbox แทน

## โครงสร้าง

```
_handoff/
├── README.md                  ← ไฟล์นี้ (protocol — ห้ามแก้)
├── frontend_to_backend.md     ← FRONTEND agent เขียนเท่านั้น, BACKEND อ่าน
├── backend_to_frontend.md     ← BACKEND agent เขียนเท่านั้น, FRONTEND อ่าน
└── status.md                  ← state machine ปัจจุบัน
```

## กฎเหล็ก

### 1. Append-only

**ห้ามลบหรือแก้ข้อความเก่าใน `*_to_*.md`** เพิ่มข้อความใหม่ที่ท้ายไฟล์เสมอ คั่นด้วย `---` เพื่อให้มี audit trail ของบทสนทนาทั้งหมด agent ที่กลับมาอ่านทีหลัง (หลัง memory เคลียร์, หลัง restart) จะเข้าใจ context ได้จากไฟล์เลย

### 2. แต่ละฝั่งเขียนคนละไฟล์

- **Frontend agent** — เขียนเฉพาะ `frontend_to_backend.md` ห้ามแตะ `backend_to_frontend.md` (อ่านได้อย่างเดียว)
- **Backend agent** — เขียนเฉพาะ `backend_to_frontend.md` ห้ามแตะ `frontend_to_backend.md` (อ่านได้อย่างเดียว)
- **`status.md`** — แก้ได้ทั้ง 2 ฝั่ง แต่ต้องระบุ sender + timestamp ทุกครั้ง

ทำแบบนี้เพื่อให้ **ไม่มี merge conflict** ต่อให้ 2 ฝั่ง push ชนกัน git rebase ก็ผ่านเพราะแก้คนละไฟล์

### 3. Format ข้อความ

ทุกข้อความใหม่ต้องขึ้นด้วย header ตามนี้

```markdown
---

## [YYYY-MM-DD HH:MM] FROM: <frontend|backend>

<เนื้อหา>
```

ตัวอย่าง

```markdown
---

## [2026-04-10 14:32] FROM: frontend

@backend ช่วยเช็คให้หน่อยว่า alembic head ตรงกับ b8c9d0e1f2a3 มั้ย ขอบคุณ
```

### 4. ห้ามใส่ secret ในไฟล์ handoff

`_handoff/` อยู่ใน git history และ push ขึ้น GitHub ห้าม paste

- password, SECRET_KEY, JWT, API keys
- AD bind password
- private IP ที่อ่อนไหว (ถ้าจำเป็นใช้ก็พอ แต่ระวัง)

ถ้าต้องส่งค่าลับ ให้เขียนแบบนี้แทน

> ค่า SECRET_KEY ผมเขียนไว้ใน `.env` ของเครื่อง backend แล้ว เหมือนเดิม — ไม่ต้องเปลี่ยน

หรือบอก path ที่อีกฝั่งจะไปอ่านเอง

### 5. Workflow ของแต่ละ agent

**ก่อนอ่าน inbox** (เพื่อรับข้อความใหม่)

```bash
cd C:/deploy/voizely
git pull --rebase
cat _handoff/<inbox>.md   # ดูข้อความล่าสุด (ใต้ --- บล็อกท้าย)
cat _handoff/status.md    # ดู state ปัจจุบัน
```

**หลังเขียน outbox** (ส่งข้อความใหม่ + อัพเดต status)

```bash
cd C:/deploy/voizely
# 1. แก้ outbox ของตัวเอง (append เท่านั้น)
# 2. แก้ status.md ถ้าเปลี่ยน state
git add _handoff/
git commit -m "handoff: <ฝั่ง> → <ทำอะไร>"
git pull --rebase    # กันกรณีอีกฝั่งเพิ่ง push
git push
```

ถ้า rebase แล้ว conflict (ไม่น่าเกิด เพราะแยกไฟล์) → หยุด รายงาน user ห้ามแก้เอง

### 6. State machine ใน `status.md`

ค่าที่ใช้ได้

- `WAITING_BACKEND` — frontend ส่งคำขอแล้ว รอ backend ตอบ
- `WAITING_FRONTEND` — backend ส่งคำขอ/รายงานแล้ว รอ frontend ตอบ
- `BACKEND_WORKING` — backend agent กำลังทำ task อยู่
- `FRONTEND_WORKING` — frontend agent กำลังทำ task อยู่
- `BLOCKED_USER` — ต้องการ user ตัดสินใจ ทั้ง 2 ฝั่งหยุด
- `DONE` — งานปัจจุบันเสร็จ

ทุกครั้งที่เปลี่ยน state ให้ใส่ timestamp + sender + reason สั้นๆ

### 7. ทำตามกฎ CLAUDE.md ของ project ปกติ

- ภาษาไทยเสมอ
- ห้ามแนะนำ restart เครื่อง / kill python ทั้งหมด
- ห้ามเริ่ม service เอง — ให้ user ทำ
- confirm กับ user ก่อนทำ shared infra (Postgres config, firewall)
- ถาม user ก่อนเรียก API ที่มีค่าใช้จ่าย

## วิธีเริ่มใช้ (ฝั่ง backend agent อ่านนี่)

ถ้าคุณคือ Claude ที่เพิ่งถูกเรียกให้เช็ค handoff บนเครื่อง backend

1. `git pull --rebase` — sync ล่าสุด
2. อ่าน `CLAUDE.md` ของ project (ถ้ายังไม่ได้อ่าน)
3. อ่านไฟล์นี้ (`_handoff/README.md`) จบ
4. อ่าน `_handoff/status.md` ดูว่าตอนนี้อยู่ state ไหน
5. ถ้า `WAITING_BACKEND` → อ่าน `_handoff/frontend_to_backend.md` block ล่าสุด แล้วทำตาม
6. รายงาน plan ให้ user ก่อน execute (ตามกฎ confirm shared infra)
7. ทำเสร็จ → append ข้อความใหม่ใน `_handoff/backend_to_frontend.md` + อัพเดต `status.md` เป็น `WAITING_FRONTEND` + commit + push

## วิธีเริ่มใช้ (ฝั่ง frontend agent อ่านนี่)

เหมือนกัน แต่สลับ inbox/outbox

1. `git pull --rebase`
2. อ่าน `_handoff/status.md`
3. ถ้า `WAITING_FRONTEND` → อ่าน `_handoff/backend_to_frontend.md` block ล่าสุด
4. ทำตาม → append `_handoff/frontend_to_backend.md` + อัพเดต status → commit + push
