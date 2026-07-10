---
name: project_multitenancy
description: "Multi-tenant rollout to sell Voizely to other orgs (gov SaaS) — Phase 0 schema done, app layer pending"
metadata: 
  node_type: memory
  type: project
  originSessionId: dd7c3a5c-7d67-4ec0-a5f7-12867b60e0b3
---

เริ่ม 2026-06-12: Jig จะเอา Voizely (เดิมทำให้บริษัทเดียว) ไปขายองค์กรอื่น เลือก **SaaS cloud กลาง (โฮสต์เอง) + ลูกค้ากลุ่มแรก = ราชการ/รัฐวิสาหกิจ**.

ตัดสินใจ: **ไม่ fork repo** — ใช้ codebase เดียว เติม tenant layer. ของเดิม = tenant_id=1 (legacy).

จุดขายแก้ปม data sovereignty ราชการ: ใช้ dual pipeline ที่มีอยู่แล้ว ทำเป็น tier — `pipeline_mode='cloud'` (Deepgram+Gemini) vs `'local'` (GPU บนเครื่อง เสียงไม่ออก = "Sovereign tier").

**Phase 0 (เสร็จแล้ว เขียนโค้ด + validate offline, ยังไม่รัน upgrade จริง):**
- model ใหม่ `app/models/organization.py` (organizations table: name, slug, is_active, pipeline_mode, ad_config JSON, branding JSON)
- เติม `tenant_id` FK 8 ตาราง: users, audio_files, transcriptions, transcription_groups, speaker_profiles, correction_dict, meeting_recordings, user_calendar_cache (transcription_segments เว้นไว้ — derive ผ่าน transcription_id)
- migration `d1a2b3c4e5f6_add_multitenancy.py` (down_revision=caad2a2c5ca0 = head เดิม). server_default='1' = transitional ให้ app เดิมยังทำงานระหว่างทำ middleware
- เปลี่ยน unique: users (username→tenant_id+username), correction_dict (wrong→tenant_id+wrong)
- ⚠️ ก่อนรันจริงต้อง verify ชื่อ constraint `correction_dict_wrong_key` ตรงกับ DB จริง (auto-name) — ของ users `uq_users_username` ชื่อชัวร์

**DEPLOYED LIVE 2026-06-12**: รัน migration จริง + restart backend (kill PID เก่า → start_web.bat :loop respawn uvicorn, ไม่มี --reload). verify บน production ผ่าน: /voiceprints=React SPA (ไม่ leak Jinja), bad-login→401, unknown-org→401, /api/health ok. login บริษัทเดิม (tenant1/ad_verify) ไม่กระทบ. ⚠️ kill PID ต้องใช้ admin terminal (process รันยกสิทธิ์ — `!` bash kill ไม่ได้). worker 2 ตัวยังโค้ดเก่า=ok (server_default=1).

**Phase 0 app layer (เสร็จแล้ว 2026-06-12, compile+import ผ่าน):**
- `core/security.py`: token พก `tid` (tenant_id), decode_token คืน dict {username, tenant_id}; legacy token ไม่มี tid → fallback username-only
- `core/tenancy.py` (ใหม่): `resolve_user`, `tenant_query`, `same_tenant`
- `auth.py`: get_current_user filter (tenant_id, username); login ส่ง tenant_id เข้า token
- `transcription.py`: `_check_owner` เช็ค tenant ก่อน (คืน 404 ข้าม tenant, scope ADMIN ด้วย); list_speakers/voiceprints/corrections/start_transcription/start_with_config tenant-scoped + set tenant_id ตอนสร้าง
- `meeting.py`: list + 8 single-object lookup เติม tenant filter; insert audio/transcription set จาก m.tenant_id
- `group.py`: ปิดรู auth เดิม (update/delete/assign_group ไม่มี get_current_user เลย) + tenant-scope ทุก endpoint + default group per-tenant
- `audio.py`: ปิดรู auth เดิมที่ /api/audio/upload (ไม่มี auth) + ส่ง tenant_id; save_upload/create_transcription สืบ tenant

**Migration ลง DB จริงแล้ว 2026-06-12** (`alembic upgrade head` → version e2b3c4d5f6a7). backfill ครบทุกแถว=tenant 1 (users15/transcriptions27/audio37/speakers227/corrections26/meetings136). ⚠️ DB จริงชื่อ constraint ไม่ตรงไฟล์เดิม — แก้เป็น `uq_correction_user_wrong`(composite user_id,wrong) + เจอ `users_email_key` เพิ่ม → ทำ email เป็น per-tenant ด้วย. brand ใหม่จะเป็น **speez.ai** (CEO กำลังจดโดเมน).

**ข้อ B เสร็จ:** ถอด `pages.router` ออกจาก main.py (UI เก่า Jinja ไม่มี auth) → path ตกไป SPA catch-all (React)

**ข้อ C เสร็จ (tenant-aware login, gov pilot ใช้ email/password):**
- migration `e2b3c4d5f6a7`: เพิ่ม `users.password_hash` (nullable, AD user=NULL)
- `core/passwords.py` (ใหม่): bcrypt ตรงๆ (ไม่ผ่าน passlib เลี่ยง warning bcrypt 4.x)
- `auth_service.authenticate(username, password, db, org_slug="default")`: resolve org by slug → AD (per-tenant ad_config / global env สำหรับ default) → local password_hash → fixed-password fallback (default org เท่านั้น). `_authenticate_ad` รับ cfg dict; `upsert_user_from_profile`/`_sync_speaker_profile` รับ tenant_id (default 1 → ad_verify tenant1 ไม่พัง)
- `/login` รับ field `org` (frontend ส่ง, ภายหลัง derive จาก subdomain *.speez.ai); default 'default'=tenant1
- `manage_tenant.py` (CLI): create-org / create-user / set-password / list-orgs
- เทสต์ end-to-end ผ่าน 6/6 (correct/wrong-pw/wrong-org/unknown-org/JWT-tenant/same-username-2-tenants)

**ข้อ ก เสร็จ 2026-06-12 (frontend ส่ง org):** `lib/auth.js login(u,p,org)` ส่ง field org; `LoginPage.jsx` อ่าน org จาก `?org=<slug>` URL หรือ localStorage('org_slug'), ช่อง "รหัสองค์กร" ซ่อนสำหรับ company (มีลิงก์ "เข้าสู่ระบบสำหรับองค์กร" toggle), จำ org ตอน re-login. gov ใช้ลิงก์ `/login?org=<slug>`. `npm run build` ผ่าน (asset index-B9X27VSa.js) → dist อัปเดต (port 3000 serve จาก dist; hard-refresh ถ้าเห็นของเก่า). verify HTTP จริง: login org=zz-pilot→200 tid=4, user รัฐ+org=default→401. manage_tenant ยังไม่มี delete-org (ลบด้วย inline python).

**Email-domain login 2026-06-12 (Jig อยากให้จำ tenant จาก @domain ไม่ต้องกรอก org code):** migration `f3c4d5e6a7b8` เพิ่ม `organizations.email_domains` (JSON list). `auth_service._resolve_org(db, username, org_slug)`: explicit non-default slug ชนะ → ไม่งั้นดึงโดเมนจาก username (officer@doh.go.th → org ที่มี doh.go.th) → ไม่งั้น default. manage_tenant create-org รับ `--domains doh.go.th` + คำสั่ง `set-domains`. LoginPage ช่อง org ซ่อน default (พิมพ์ email พอ), ลิงก์ "ระบุองค์กรเอง" เป็น fallback. onboard ใหม่: create-org --domains → create-user username=email → user พิมพ์ email+pw เข้า tenant ถูกเอง.

**VERIFIED LIVE ผ่าน HTTP จริง 2026-06-12** (หลัง Jig restart backend): สร้าง test org qa-emaildomain (id=6, domain qa-verify.test) + user → `POST /api/auth/login` ด้วย email อย่างเดียว ไม่ส่ง org → decode JWT `tid`=6 ถูก tenant + /api/auth/me ยืนยัน. negative: wrong-pw→401, control: email domain ไม่ตรง (ghost@nowhere.test)→ตกไป default+401 (พิสูจน์ว่าไม่ใช่ทุก email หลุดเข้า tenant). ลบ test org ทิ้งกลับสู่สภาพเดิม (default 15 users). **gotcha cleanup:** User↔Organization ไม่มี ORM relationship() → ลบ org ตรงๆ FK violation; ต้อง bulk-delete users + `db.flush()` ก่อนลบ org (manage_tenant ยังไม่มี delete-org).

**⚠️ ยังเหลือ:**
- frontend: ภายหลัง derive org จาก subdomain *.speez.ai ได้อีกชั้น
- **worker** (gemini_worker/teams_worker) สร้าง record ต้องสืบ tenant (ตอนนี้ server_default=1 → tenant1)
- **admin sync-ad-speakers** ยัง tenant1 เท่านั้น (ยังไม่รับ tenant param)
- legacy htmx endpoints ใน transcription.py (/htmx/*) ยัง orphan/ไม่มี auth บางตัว
- drop server_default='1' หลัง middleware คุมครบ; onboarding UI/branding/quota, audit log, PDPA retention
- เปลี่ยนชื่อ org id=1 จาก "Default Organization" เป็นชื่อบริษัทจริง (optional)

**Phase 1+:** onboarding, branding/quota ต่อ tenant, audit log + PDPA retention. **ยังไม่ทำ:** separate DB ต่อ tenant, billing อัตโนมัติ, self-serve signup.

เกี่ยวกับ [[project_architecture.md]] [[project_diarization_pipeline.md]] [[feedback_keep_it_simple]].
