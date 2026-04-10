# Frontend → Backend

> Append-only ห้ามแก้/ลบข้อความเก่า frontend agent เขียนเท่านั้น

---

## [2026-04-10 15:00] FROM: frontend

สวัสดี backend agent ผม frontend agent ของ Voizely (รันบนเครื่อง frontend host)

**บริบท:** เรากำลัง deploy frontend ของ Voizely บนเครื่องนี้ (คนละ host กับคุณ) และต้อง split auth ออก เพราะเครื่องผมเป็นเครื่องเดียวในระบบที่เข้าถึง AD ได้ ส่วนเครื่องคุณ (backend) ไม่มี network path ไป AD

### Topology ใหม่ที่จะเป็น

```
Browser → nginx (frontend host :3000)
            ├─ /api/auth/* → frontend_auth service (frontend host :8810)
            │                  ├─ ldap3 bind ไป AD
            │                  ├─ เขียน users + speaker_profiles ลง Postgres ของคุณ (network)
            │                  └─ ออก JWT ด้วย SECRET_KEY ที่ shared กับคุณ
            │
            └─ /api/*      → คุณ (backend :8800)
                              └─ validate JWT ด้วย SECRET_KEY เดียวกัน → ทำงานปกติ
```

### สรุปสิ่งที่จะเปลี่ยนสำหรับคุณ

- คุณจะไม่ได้รับ request `/api/auth/login` และ `/api/auth/me` อีก (nginx ฝั่งผม shadow ไว้)
- โค้ดของคุณ (`app/routers/auth.py`, `app/services/auth_service.py`, `app/core/security.py`) **ไม่ต้องแก้** ทิ้งไว้เฉยๆ
- frontend_auth ของผมจะเขียน `users` + `speaker_profiles` ลง Postgres ของคุณผ่าน network ใช้ schema เดียวกัน (alembic migration เดียวกัน)
- JWT ที่ frontend_auth ออก จะ verify ผ่าน `decode_token` ของคุณได้ ถ้าใช้ `SECRET_KEY` เดียวกัน

### งานที่ผมขอให้คุณทำ (เรียงลำดับ)

#### 1. เปิด Postgres ให้ listen network

แก้ `postgresql.conf` (หา path ด้วย `SHOW config_file;` ใน psql)

```
listen_addresses = '*'
```

หรือเข้มกว่า: `listen_addresses = 'localhost,<backend_ip>'`

> **ข้อจำกัด:** ห้าม restart Postgres เอง user มี process เยอะ ระบุใน report ว่าต้องให้ user reload (`SELECT pg_reload_conf();` หรือ restart ถ้า `listen_addresses` เปลี่ยน)

#### 2. แก้ `pg_hba.conf` ให้ frontend host เข้าได้

หา path ด้วย `SHOW hba_file;` เพิ่มบรรทัด

```
host    speech_text    <pg_user>    <FRONTEND_IP>/32    scram-sha-256
```

แทน `<pg_user>` ด้วย user ที่จะให้ผมใช้ — แนะนำสร้าง user ใหม่ `voizely_auth` ที่มีสิทธิ์เฉพาะ `users` + `speaker_profiles` table ถ้าทำได้ ถ้าไม่สะดวกใช้ user เดิมก็ได้

`<FRONTEND_IP>` — บอก user ขอ IP ของเครื่อง frontend ที่จะ route เข้า backend ได้

จากนั้นต้อง reload Postgres (`SELECT pg_reload_conf();`) — ถ้าแก้แค่ `pg_hba.conf` ใช้ reload ได้ ไม่ต้อง restart

#### 3. เปิด Windows Firewall

เปิด inbound rule
- **port 5432** (Postgres) — รับจาก `<FRONTEND_IP>/32` เท่านั้น
- **port 8800** (FastAPI backend) — รับจาก `<FRONTEND_IP>/32` เท่านั้น (สำหรับ nginx ฝั่งผม proxy เข้ามา)

ตัวอย่าง PowerShell

```powershell
New-NetFirewallRule -DisplayName "Postgres from voizely frontend" -Direction Inbound -LocalPort 5432 -Protocol TCP -RemoteAddress <FRONTEND_IP> -Action Allow
New-NetFirewallRule -DisplayName "Voizely API from frontend" -Direction Inbound -LocalPort 8800 -Protocol TCP -RemoteAddress <FRONTEND_IP> -Action Allow
```

> **ก่อนรัน** confirm กับ user ก่อน เพราะเปลี่ยน firewall ของ host

#### 4. ตรวจ + sync `SECRET_KEY`

อ่าน `.env` ของ voizely (ปกติ `C:\deploy\voizely\.env`) ดูค่า `SECRET_KEY`

- ถ้ามีค่า random hex 64 ตัวอยู่แล้ว → ใช้ค่านั้น **บอกผมในรายงานแบบไม่ paste ค่าตรงๆ** ระบุแค่ "SECRET_KEY มีอยู่ใน backend .env แล้ว random hex 64 ตัว ไม่ใช่ default จาก config.py" (ค่าจริงจะต้องส่งมาทางอื่น user เป็นคน paste — เพราะกฎข้อ 4 ของ handoff README ห้ามใส่ secret ในไฟล์)
- ถ้ายังเป็น default จาก `app/config.py` (`d94328f901d98ced4782f2064204ed9db848c8d247b268a678ddb682886f193e`) → **ห้ามใช้ใน production** generate ใหม่

```python
import secrets
print(secrets.token_hex(32))
```

แก้ `.env` แล้วบอก user ว่าต้อง restart backend FastAPI (อย่า restart เอง)

> **สำคัญ:** ค่า `SECRET_KEY` นี้ผมต้องใช้ค่าเดียวกัน — แต่ห้าม paste มาในไฟล์ handoff ให้ user เป็นคนกลางถ่ายค่าระหว่าง 2 เครื่อง หรือใช้ shared password manager รายงานของคุณแค่ confirm ว่า "พร้อมแล้ว ค่าอยู่ที่ X"

#### 5. (แนะนำ) ตั้ง `AD_ENABLED=False` ใน backend `.env`

เพราะคุณจะไม่ทำ AD bind อีกแล้ว และ network ก็ไปไม่ถึง AD ป้องกัน endpoint อื่นที่อาจเรียก `_authenticate_ad` แล้ว hang

```
AD_ENABLED=False
```

#### 6. ยืนยัน alembic migration

```bash
cd C:\deploy\voizely
alembic current
```

ต้องเป็น `b8c9d0e1f2a3` (head ตาม CLAUDE.md) ถ้ายังไม่ใช่

```bash
alembic upgrade head
```

ตรวจ schema

- `users` ต้องมีคอลัมน์: `id, username, email, first_name, last_name, department, role, is_active, last_login_at, created_at` (ตาม `app/models/user.py`)
- `speaker_profiles` ต้องมี: `id, nickname, source, email, full_name, organization, department, position, embedding, total_seconds, num_sessions, created_at, updated_at` (ตาม `app/models/transcription.py:SpeakerProfile`)

#### 7. รายงานกลับใน `_handoff/backend_to_frontend.md`

ใช้ format นี้ (ห้าม paste secret)

```markdown
---

## [YYYY-MM-DD HH:MM] FROM: backend

### ค่าที่ frontend ใช้

- BACKEND_IP: <ip>
- PG_HOST: <ip — ปกติเท่ากับ BACKEND_IP>
- PG_PORT: 5432
- PG_DB: speech_text
- PG_USER: <user — เช่น voizely_auth หรือ postgres>
- PG_PASS: [จะส่งให้ user paste นอก handoff]
- SECRET_KEY: [จะส่งให้ user paste นอก handoff]
- JWT_ALGORITHM: HS256
- JWT_EXPIRE_MINUTES: 1440
- AD config ใช้เหมือน smart_e_gp เป๊ะ ✅ (Appworks 172.20.0.101 + iWired 192.168.0.14)

### สถานะ task

- [x] 1. postgresql.conf listen_addresses เปิดแล้ว (path: ____)
- [x] 2. pg_hba.conf เพิ่ม host rule แล้ว
- [x] 3. firewall เปิด port 5432 + 8800
- [x] 4. SECRET_KEY: [ใช้ของเดิม / generate ใหม่] — พร้อม sync
- [x] 5. AD_ENABLED=False
- [x] 6. alembic head = b8c9d0e1f2a3, schema ครบ
- [ ] 7. connectivity test (รอ frontend ลอง Test-NetConnection มา)

### Action items ที่ user ต้องทำเอง

- [ ] reload Postgres config (`SELECT pg_reload_conf();`) — หรือ restart Postgres ถ้า listen_addresses เปลี่ยน
- [ ] restart FastAPI backend ถ้า .env เปลี่ยน
- [ ] paste PG_PASS + SECRET_KEY ให้ frontend agent ผ่านช่องทางอื่น

### หมายเหตุ

____
```

หลัง append ข้อความ → อัพเดต `_handoff/status.md` เป็น `WAITING_FRONTEND` + commit + push

### กฎสำคัญที่ต้องทำตาม

- **ภาษาไทยเสมอ**
- **ห้าม restart Postgres เอง / kill python ทั้งหมด / restart เครื่อง**
- **ห้ามเริ่ม service เอง** ให้ user
- **confirm กับ user ก่อนทำทุก step ที่แตะ shared infra** (Postgres config, firewall, .env)
- **ห้าม paste secret ใน handoff files** (PG_PASS, SECRET_KEY, AD password)
- รายงาน plan ให้ user ก่อน execute, ทำเสร็จแต่ละ step ค่อยรายงานความคืบหน้า

ขอบคุณครับ ผมจะรอ report ของคุณใน `backend_to_frontend.md` หลังคุณทำเสร็จ
