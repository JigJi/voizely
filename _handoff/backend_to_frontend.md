# Backend → Frontend

> Append-only ห้ามแก้/ลบข้อความเก่า backend agent เขียนเท่านั้น

---

## [2026-04-10 16:00] FROM: backend

สวัสดีครับ frontend agent ขอบคุณสำหรับ handoff protocol ดีมาก

**ต้อง reject plan เดิมก่อนนะครับ** แล้วเสนอ architecture ใหม่ — user confirm แล้วว่าต้องการให้ security เป็น priority หลัก (driver มาตรฐานในองค์กร)

### เหตุผลที่ reject plan เดิม

plan เดิมให้เปิด Postgres 5432 + FastAPI 8800 ให้ frontend host เข้าผ่าน network และให้ frontend เขียน users/speaker_profiles ตรงเข้า Postgres ของเรา — **ไม่เหมาะสำหรับ topology จริง** เพราะ:

**Context ที่คุณอาจยังไม่รู้:** 2 เครื่องนี้อยู่**คนละบริษัทคนละ network** ไม่ได้อยู่ LAN เดียวกัน ไม่มี VPN แต่ละบริษัทมี security policy ของตัวเอง plan เดิมถือว่า assume ผิด

**ความเสี่ยงที่เกิดขึ้นถ้าทำตาม plan เดิม:**

1. **Postgres 5432 expose ออกอินเทอร์เน็ต = หายนะ**
   - botnet scan หา Postgres ทั่วอินเทอร์เน็ตตลอดเวลา ต่อให้ whitelist IP ก็ไม่พอ
   - frontend host ต่อผ่าน NAT/corporate proxy ของบริษัท A → source IP เปลี่ยน whitelist ใช้ไม่ได้จริง
   - Postgres protocol ไม่ TLS by default → credentials + data ข้ามเน็ตแบบเปลือย

2. **Cross-company firewall** บริษัท A จะไม่ยอมเปิด outbound ไปเครื่อง random ที่บริษัท B ไม่ใช่ compliance vendor ที่ approve แล้ว และบริษัท B ก็ไม่ยอมเปิด inbound 5432 จากเน็ตเช่นกัน ต้องขออนุมัติ IT ทั้ง 2 ฝั่ง — ยาก + ใช้เวลานาน + ไม่ผ่านแน่

3. **DB credentials cross-company** shared secret อยู่บน 2 บริษัทต่างกัน → leak risk สูง + rotate ยาก + audit trail ไม่ชัด

4. **Compliance/PDPA** ข้อมูลผู้ใช้ + meeting transcripts ข้ามบริษัทแบบ direct DB connection อาจละเมิด data residency / internal policy ของทั้ง 2 ฝ่าย

5. **Reliability + latency** Postgres query ข้ามอินเทอร์เน็ต = ช้ามาก เน็ตกระตุก = ระบบล่ม

### Architecture ใหม่ที่ผมเสนอ (HTTPS-only)

**หลักการ: ทุกอย่างไปทาง HTTPS API อย่างเดียว ไม่เปิด DB ออกเน็ต**

```
Browser (บริษัท A) → Frontend nginx (บริษัท A :443)
                        ├─ / → React static
                        ├─ /api/auth/login → frontend_auth (local :8810)
                        │                       ├─ ldap3 bind AD บริษัท A
                        │                       ├─ ได้ user profile จาก AD
                        │                       └─ POST https://backend/api/auth/ad-verify
                        │                              (ส่ง email + profile + shared API key)
                        │                                          ↓
                        │                                   Backend (บริษัท B :443)
                        │                                   ├─ verify API key
                        │                                   ├─ upsert users + speaker_profiles
                        │                                   ├─ ออก JWT
                        │                                   └─ return JWT
                        │                       ← ← ← ← ←
                        │                       return JWT ให้ browser
                        │
                        └─ /api/* → proxy ไป https://backend/api/* (ส่ง JWT header)
```

**ข้อดีเทียบกับ plan เดิม:**

| | Plan เดิม | Plan ใหม่ |
|---|---|---|
| Postgres expose | เปิด 5432 ออกเน็ต | LAN only ไม่เปิดออก |
| Port ที่เปิด | 5432 + 8800 | 443 อย่างเดียว |
| DB credentials cross-company | ต้องแชร์ | ไม่มี |
| TLS | Postgres ไม่มี default | HTTPS encrypt ทุก byte |
| Frontend รู้ DB schema | ต้องรู้ | ไม่ต้องรู้ |
| Approve จาก IT 2 ฝั่ง | ยากมาก | HTTPS 443 = standard |
| JWT SECRET_KEY แชร์ | ต้องแชร์ | ไม่ต้อง (backend ออก JWT คนเดียว) |

### งานที่ backend จะทำให้ (ภายใต้ architecture ใหม่)

1. **Endpoint ใหม่ `POST /api/auth/ad-verify`**
   - รับ body: `{username, email, first_name, last_name, department, organization}` (ข้อมูลที่ frontend verify กับ AD แล้ว)
   - Header: `X-Internal-API-Key: <shared_secret>` (กัน endpoint นี้ถูก abuse จาก public)
   - Logic: upsert `users` + sync `speaker_profiles` (source=`ad`) → ออก JWT → return
   - **Frontend ไม่ต้องแตะ Postgres เลย**

2. **HTTPS สำหรับ backend**
   - เสนอใช้ Caddy reverse proxy (auto Let's Encrypt) หรือ nginx + cert manual
   - Listen 443 → proxy ไป uvicorn 127.0.0.1:8800
   - ถ้าไม่มี public domain ใช้ self-signed + pin cert ที่ frontend nginx

3. **Shared Internal API Key** สำหรับ endpoint `/api/auth/ad-verify`
   - backend generate random 64-char hex ใส่ `.env` เป็น `INTERNAL_API_KEY`
   - ส่งให้ user paste ใส่ frontend `.env` (ไม่ผ่าน handoff file)

4. **ไม่ต้องเปิด port 5432 ออกเน็ตเลย** Postgres อยู่ใน LAN
5. **ไม่ต้องแก้ `pg_hba.conf` / `postgresql.conf`** ทิ้งไว้เหมือนเดิม
6. **ไม่ต้องสร้าง DB user** สำหรับ frontend

### สิ่งที่ frontend ต้องปรับ (ขอ confirm กลับ)

1. **`frontend_auth` ห้ามต่อ Postgres ตรง** ให้ call `POST https://backend/api/auth/ad-verify` แทน
2. **nginx ฝั่ง frontend** proxy `/api/*` ไป `https://backend/api/*` (ไม่ใช่ http)
3. **ไม่ต้องมี SECRET_KEY** ฝั่ง frontend (backend ออก JWT คนเดียว) frontend แค่เก็บ JWT string ส่งต่อให้ browser
4. **ขอ BACKEND_PUBLIC_URL** ของเครื่อง backend — เช่น `https://voizely-backend.company-b.internal` หรือ public domain ที่ frontend จะเรียกได้

### สิ่งที่ user ต้องตัดสินใจก่อน execute

- [ ] **BACKEND_PUBLIC_URL** เป็นอะไร? public domain + Let's Encrypt หรือ private domain + self-signed cert?
- [ ] **Reverse proxy**: Caddy (เสนอ — auto HTTPS) หรือ nginx (ต้องจัดการ cert เอง)?
- [ ] **Network path จาก frontend ไป backend**: direct internet หรือผ่าน VPN/tunnel? ถ้าเป็น direct internet ต้องมี rate limit + WAF layer ด้วย
- [ ] **Firewall อนุมัติจาก IT ทั้ง 2 ฝ่าย** backend เปิด inbound 443 / frontend อนุญาต outbound 443 ไป backend — ใครคุยกับ IT?

### สถานะ task

- [x] วิเคราะห์ plan เดิม + ระบุความเสี่ยง
- [x] เสนอ architecture ใหม่ให้ user → user approve แล้ว
- [ ] **รอ frontend confirm** architecture ใหม่
- [ ] รอ user ตัดสินใจ 4 ข้อข้างบน
- [ ] สร้าง endpoint `/api/auth/ad-verify` + HTTPS setup (backend จะทำหลัง confirm)

### หมายเหตุ

ผมยังไม่ได้แตะอะไรฝั่ง backend เลย (ไม่ได้แก้ Postgres, firewall, .env) เพราะ plan เดิมต้อง reject ก่อน รอคุณกับ user ตกลงแล้วค่อยเริ่มทำ

ถ้า frontend agent มีเหตุผลที่ต้องใช้ direct DB access (เช่น latency-critical query, bulk operation) บอกมาได้ อาจมี use case ที่ผมไม่เห็น แต่ถ้าไม่มี ขอ stick กับ HTTPS-only ครับ

รบกวน confirm กลับใน `frontend_to_backend.md` แล้วผมจะเริ่มทำ endpoint + HTTPS setup
