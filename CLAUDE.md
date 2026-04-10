# Voizely — Speech-to-Text & Meeting Intelligence Platform

Meeting transcription + MoM generation, designed for Thai language meetings.

## Architecture

**2 เครื่องแยก:**

| เครื่อง | หน้าที่ | Spec |
|---|---|---|
| **Backend** | FastAPI + Worker + PostgreSQL + GPU (RTX A4000) | Heavy |
| **Frontend** | React + nginx + ต่อ AD | Light |

- Frontend (port 3000) → proxy API → Backend (port 8800)
- **ห้ามเข้า backend 8800 จาก browser ตรงๆ** — frontend อยู่ port 3000 เสมอ
- Port 8801 คือของเก่า dead ห้ามใช้

## Tech Stack

**Backend (เครื่องนี้):**
- FastAPI + SQLAlchemy + Alembic
- PostgreSQL (`speech_text` DB)
- Workers: `gemini_worker.py`, `teams_worker.py`
- AI: Deepgram (API), Gemini Flash (API), speechbrain (local GPU), Pyannote (local GPU)
- Auth: JWT + AD (ldap3)

**Frontend (เครื่องอื่น):**
- React 18 + Vite 5 + Tailwind
- nginx serve static + proxy `/api` → backend
- เชื่อม AD ได้

## Diarization Pipeline (Winner: spectral+gemini)

ใช้สำหรับ mono Teams recordings ที่ Deepgram แยก speaker ไม่ได้:

1. **Deepgram** → utterances (text + timestamps, ignore speaker label)
2. **speechbrain ECAPA** → สกัด voice embedding ต่อ utterance (GPU ~8 วิ)
3. **Spectral Clustering** (sklearn, n_clusters=4) → จัดกลุ่ม speaker
4. **Gemini audio-correct** → แก้คำผิด (ส่ง audio chunk + Deepgram text)
5. **Post-process**: fix Thai word splits + merge same-speaker

**Cost:** ~10 บาท/ไฟล์ 1 ชม. (Deepgram $0.04 + Gemini $0.01)

**ทำไม Deepgram diarize ไม่ได้กับไฟล์ mono:** Teams/Zoom mix เสียงทุกคนเป็น 1 channel → audio-based diarization (Deepgram, Pyannote) แยกไม่ออก

## Meetings Feature (Teams Integration)

**Flow:**
1. `teams_worker.py` poll OneDrive `/Recordings/` หรือ `/การบันทึก/` ของ user ที่ active ใน DB
2. เจอไฟล์ใหม่ → **เก็บแค่ metadata** (ชื่อ, วันที่, attendees) **ไม่ดาวน์โหลด**
3. User กด "ถอดเสียง" จาก Meetings page → download + process ตอนนั้น
4. **Access control**: เฉพาะ attendees + organizer เห็นไฟล์
5. **Lock**: ใครกดถอดเสียงก่อนเท่านั้นที่ได้ทำ

**สำคัญ:** ห้าม auto-download ทุกไฟล์ทิ้งไว้ — user ต้องกดเอง

## User Rules (สิ่งที่ user ให้จดจำ)

- ตอบเป็น**ภาษาไทย**เสมอ
- **ห้ามแนะนำให้ restart เครื่อง** — มี process เยอะ
- **ห้าม kill Python ทั้งหมด** — user รัน 10+ projects
- **ห้ามเริ่ม server/worker เอง** — user ใช้ Task Scheduler + bat
- **ปิด bat ไม่ kill Python** — ต้อง kill PID ตรงๆ
- **ถามก่อนเรียก API ที่มีค่าใช้จ่าย**
- **ห้าม restart แล้วสั่ง user พัก/หยุด/นอน**
- **ห้าม taskkill /IM python.exe**
- **ห้ามใช้ browser alert/confirm** — ใช้ custom modal
- **อย่าเรียก tool ซ้ำโดยไม่จำเป็น** — memory user บอกหลายครั้ง

## Port Assignments

| Port | Service |
|---|---|
| 3000 | Frontend (Vite / React) |
| 8800 | Backend API (FastAPI) |
| 8000 | srt_chatbot (PRODUCTION - ngrok, ห้ามใช้) |
| 8100 | data_connect |

## Speaker Profiles

2 ประเภท (`source` field):
- **`ad`** — จาก AD auto-sync ตอน user login **ห้ามแก้/ลบ**
- **`manual`** — user สร้างเอง (vendor/ลูกค้า) แก้/ลบได้

## Auth Flow (AD)

1. User login → POST `/api/auth/login` (username + password)
2. Backend ลอง AD ก่อน (`ldap3`) → fallback fixed user
3. AD success → ดึง displayName, email, department
4. Upsert `users` table + auto-sync `SpeakerProfile` (source=`ad`)
5. Return JWT token

**Config (.env):**
```
AD_ENABLED=True
AD_SERVER=172.x.x.x
AD_DOMAIN=ais.local
AD_BASE_DN=DC=ais,DC=local
```

**Development mode:** `AD_ENABLED=False` → ใช้ `FIXED_USERNAME`/`FIXED_PASSWORD` จาก config

## MoM Generation (Gemini)

**Anti-hallucination rules ใน prompt:**
- ห้ามเพิ่มข้อมูลที่ไม่มีใน transcript (เช่น "Jira" "Spicy")
- ห้ามใช้ชื่อคนในประเด็น/มติ (ใช้ "ทีม"/"ที่ประชุม")
- ห้ามขึ้นต้น bullet ด้วย "มีการ/มีความ/มีปัญหา" → เขียนตรงๆ
- ห้ามขึ้นต้นมติด้วย "ทีมจะ/จะมีการ"
- Action items ต้องมีรายละเอียดว่าทำอะไร ทำไปเพื่ออะไร
- Title ภาษาไทยเท่านั้น

**Post-process (`_fix_mom_style`):** ล้าง "มีการ"/"ทีมจะ" อัตโนมัติถ้า Gemini ยังดื้อ

## Production Deploy Checklist

### Backend machine (เครื่องนี้)
- [x] Security: auth + owner check ทุก endpoint
- [x] SECRET_KEY: random hex (ไม่ใช่ default)
- [x] FIXED_PASSWORD: empty string ใน default (บังคับ set ใน .env)
- [x] QA/test files อยู่ใน .gitignore
- [ ] Alembic: `alembic upgrade head` (migration ล่าสุด: `b8c9d0e1f2a3`)
- [ ] CORS: เปิดให้เครื่อง frontend เข้าได้
- [ ] `.env` production: PG_HOST, DB password, Deepgram key, Gemini key, MS Teams secrets, HF_TOKEN

### Frontend machine
- [ ] nginx config: serve `dist/` + proxy `/api` → `backend_ip:8800`
- [ ] Build: `cd frontend && npm run build`
- [ ] `.env` frontend: AD config (AD_ENABLED, AD_SERVER, AD_DOMAIN, AD_BASE_DN)
- [ ] ทดสอบ AD login จากเครื่อง frontend

## Key Files

**Backend:**
- `gemini_worker.py` — transcription pipeline (spectral+gemini, deepgram+gemini, gemini+gemini)
- `teams_worker.py` — poll OneDrive for new recordings (metadata only)
- `app/routers/transcription.py` — transcription API
- `app/routers/meeting.py` — meeting API (access control by attendees)
- `app/services/auth_service.py` — AD login + SpeakerProfile sync
- `app/services/docx_export.py` — export MoM to DOCX (with speaker profile info)

**Frontend:**
- `frontend/src/pages/TranscriptionPage.jsx` — transcription view (Timeline + Summary tabs)
- `frontend/src/pages/MeetingPage.jsx` — meetings list + download button
- `frontend/src/pages/UploadPage.jsx` — file upload + model selection
- `frontend/src/tabs/MomModal.jsx` — MoM editor (per-section edit, table editor for action items)
