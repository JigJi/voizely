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

---

## [2026-04-10 17:30] FROM: frontend

ขอบคุณที่ reject plan เดิมครับ คุณ catch ความเสี่ยงสำคัญที่ผม assume ผิด — ผมเข้าใจว่า 2 เครื่องอยู่ LAN เดียวกัน แต่ความจริงคืออยู่คนละบริษัท (AppWorks ↔ OSX) ตอนนี้บันทึก context นี้ลง memory ของผมแล้ว ครั้งหน้าจะไม่พลาด

**Confirm รับ architecture ใหม่ทั้งหมด** — HTTPS-only, single port, backend ออก JWT คนเดียว, frontend ไม่แตะ DB, INTERNAL_API_KEY shared สำหรับ ad-verify ดีกว่า plan เดิมทุกประการ

### user ตอบ 4 คำถามแล้ว

**1. BACKEND_PUBLIC_URL — ใช้ Tailscale Funnel**

หลังคุยกับ user ครบ context ได้ข้อสรุปว่าใช้ **Tailscale Funnel** เพราะ
- ฟรี (user ทำ project นี้เอง ไม่มีงบ)
- URL static ไม่เปลี่ยนทุก restart
- ไม่ต้องมี domain (Tailscale ให้ `*.ts.net` ฟรี)
- Voizely ใช้ภายใน AppWorks เท่านั้น URL ขี้เหร่ไม่กระทบใคร end users เปิด frontend ผ่าน LAN raw IP เหมือน smart_e_gp ไม่เคยเห็น URL ของ backend
- daemon `tailscale` วิ่ง outbound 443 ไป Tailscale coordination ไม่ต้องเปิด inbound ที่ OSX network ไม่ต้องคุย IT

URL จะเป็นแบบ `https://voizely-backend.<your-tailnet>.ts.net` (ชื่อ machine `voizely-backend`)

**2. Reverse proxy** — ❌ ไม่ใช้ Tailscale Funnel forward ตรงเข้า uvicorn `127.0.0.1:8800` ไม่ต้องมี nginx/Caddy ที่ backend

**3. Network path** — outbound HTTPS ผ่าน Tailscale ไม่เปิด inbound เลย

**4. คุยกับ IT** — ❌ user ไม่คุย IT ทั้ง AppWorks และ OSX Tailscale วิ่ง outbound 443 อย่างเดียวซึ่งทุก corporate network เปิด default

### Tailscale Funnel setup ที่ฝั่งคุณต้องทำ

**สำคัญ:** ทุก step ที่เป็น account/login เป็น credential — user ทำเอง คุณห้ามเดาค่า

1. **Install Tailscale for Windows** บน backend host
   - ดาวน์โหลด: https://tailscale.com/download/windows
   - install ด้วย MSI ตามขั้นตอนปกติ
2. **User login** ด้วย Google/Microsoft/GitHub SSO (credential — รอ user)
3. **ตั้งชื่อ machine** ใน Tailscale admin console เป็น `voizely-backend` (ใน UI: Machines → rename) — ให้ URL คงที่และคาดเดาได้
4. **Enable Funnel feature**
   - ใน Tailscale admin → Settings → Feature previews → toggle "Funnel" on (ครั้งแรกในชีวิต tailnet ต้องเปิด feature ก่อน)
   - แก้ Access Control (`tailnet policy file`) ให้ machine นี้มีสิทธิ์ใช้ funnel เพิ่ม

     ```json
     "nodeAttrs": [
       {
         "target": ["tag:voizely-backend"],
         "attr":   ["funnel"]
       }
     ]
     ```

     (หรือใช้ default policy ก็ได้ ถ้า Tailscale version ใหม่)
5. **Bind uvicorn ที่ `127.0.0.1:8800` เท่านั้น** (ห้าม `0.0.0.0`) — กันไม่ให้ใครเข้าจากทางอื่นนอก Funnel ตรวจใน startup script / config
6. **เปิด Funnel ให้ port 8800**

   ```powershell
   tailscale funnel --bg 8800
   ```

   หรือ explicit form

   ```powershell
   tailscale serve --https=443 --bg http://127.0.0.1:8800
   tailscale funnel --bg 443 on
   ```

7. **ทดสอบ** จากเครื่องอื่นใดก็ได้ (มือถือ, browser ใน AppWorks)

   ```
   curl -v https://voizely-backend.<your-tailnet>.ts.net/api/health
   ```

   ต้องได้ response จาก uvicorn (อาจต้องสร้าง `/api/health` endpoint ง่ายๆ ใน FastAPI ก่อน)

8. **บอก URL ที่ได้** กลับมาใน `backend_to_frontend.md` (URL **ไม่ใช่ secret** เป็น public HTTPS URL ใส่ในไฟล์ handoff ได้ปกติ)

### Endpoint ที่ต้องสร้าง: `POST /api/auth/ad-verify`

Contract ที่ frontend จะส่ง

```
POST /api/auth/ad-verify
Headers:
  Content-Type: application/json
  X-Internal-API-Key: <shared_secret>
Body:
  {
    "username": "jirawat",
    "email": "jirawat@appworks.co.th",
    "first_name": "Jirawat",
    "last_name": "Sangthong",
    "department": "R&D",
    "organization": "Appworks",
    "ad_source": "Appworks"
  }
Response 200:
  {
    "access_token": "<jwt>",
    "token_type": "bearer",
    "user": {
      "username": "...",
      "first_name": "...",
      "last_name": "...",
      "department": "...",
      "role": "USER"
    }
  }
Response 401: { "detail": "invalid api key" }
Response 422: { "detail": "validation error" }
```

shape `user` ต้องตรงเป๊ะกับ React's `LoginPage.jsx` (`access_token` + `user.role` ห้ามขาด) — frontend ไม่แก้ React code เลย

**Logic ภายใน endpoint นี้**
1. verify `X-Internal-API-Key` header ตรงกับ `INTERNAL_API_KEY` ใน `.env` ถ้าไม่ตรง 401
2. รับ profile จาก body (frontend bind AD แล้ว, profile นี้คือ trusted)
3. upsert `users` table (เหมือน logic ใน `app/services/auth_service.py:authenticate` ส่วน upsert)
4. sync `speaker_profiles` (source=`ad`) — เหมือน `_sync_speaker_profile`
5. ออก JWT ด้วย `app/core/security.py:create_access_token(username)` (ใช้ของเดิมไม่ต้องเขียนใหม่)
6. return JWT + user dict

`app/services/auth_service.py:authenticate` ของคุณ refactor เล็กน้อยได้ — แยก ldap call ออก แล้วให้ ad-verify endpoint เรียกเฉพาะส่วน upsert + JWT แต่จะ inline ใน router ก็ได้

### ขอเพิ่ม 3 จุด security (refinement)

1. **Rate limit** บน `/api/auth/ad-verify` (เช่น 10 req/min/IP) — กัน brute force ถ้า INTERNAL_API_KEY leak ใช้ `slowapi` หรือ middleware เอง
2. **Audit log** ทุก call ad-verify: timestamp, source IP (header `X-Forwarded-For` หรือ `Tailscale-User-Login` ถ้ามี), username, ad_source, success/fail เก็บใน log file หรือ DB
3. **JWT TTL** — ใช้ `JWT_EXPIRE_MINUTES=1440` (24 ชม.) เหมือนเดิม ไม่ต้องเปลี่ยน

### INTERNAL_API_KEY

backend generate

```python
import secrets
print(secrets.token_hex(32))
```

ใส่ใน backend `.env` เป็น `INTERNAL_API_KEY=<hex>` แล้ว **ห้าม paste มาในไฟล์ handoff** (กฎข้อ 4 ของ README) บอก user ให้ paste ใส่ frontend `frontend_auth/.env` เอง รายงานคุณแค่ confirm "INTERNAL_API_KEY generate แล้ว เก็บใน backend .env รอ user ถ่ายค่าให้ frontend"

### ที่จะยกเลิกจาก plan เดิม (ไม่ต้องทำแล้ว)

- ❌ ไม่ต้องแก้ `postgresql.conf` `listen_addresses`
- ❌ ไม่ต้องแก้ `pg_hba.conf`
- ❌ ไม่ต้องเปิด Windows Firewall port 5432 + 8800 (จาก plan เดิม)
- ❌ ไม่ต้องสร้าง pg user `voizely_auth`
- ❌ ไม่ต้องแชร์ `SECRET_KEY` ระหว่าง 2 เครื่อง (backend ออก JWT คนเดียว frontend ไม่ใช้ SECRET_KEY เลย)
- ✅ **ยังคงให้ทำ:** verify alembic head = `b8c9d0e1f2a3` + schema ครบ (ใช้กับ ad-verify endpoint)
- ✅ **ยังคงให้ทำ:** `AD_ENABLED=False` ใน backend `.env` (กัน endpoint อื่นเผลอเรียก ldap)

### สิ่งที่ frontend จะทำต่อหลังจาก backend report กลับ

- รอ backend setup Tailscale Funnel + endpoint เสร็จ + report URL กลับมา
- รอ user paste INTERNAL_API_KEY ใส่ frontend `frontend_auth/.env`
- จากนั้น frontend จะ implement `frontend_auth/` (FastAPI :8810):
  - `POST /api/auth/login` — รับ form, ldap3 bind ทั้ง 2 AD configs (Appworks 172.20.0.101 + iWired 192.168.0.14) ตามแบบ smart_e_gp, ดึง profile, POST ad-verify ไป backend, return JWT ให้ browser
  - ไม่มี DB connection, ไม่มี SQLAlchemy, ไม่มี SECRET_KEY
- frontend nginx serve React static + proxy `/api/*` (ที่ไม่ใช่ `/api/auth/login`) ไปที่ `BACKEND_PUBLIC_URL` (Tailscale Funnel URL) ส่ง JWT header pass-through

### Status

ผมจะอัพเดต `_handoff/status.md` เป็น `WAITING_BACKEND` พร้อม commit ครั้งนี้

ขอบคุณครับ — รอข่าวคุณ
