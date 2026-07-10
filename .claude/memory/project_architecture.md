---
name: project_architecture
description: Architecture — FastAPI + React frontend, PostgreSQL, dual pipeline (API + local)
type: project
---

**Web server**: FastAPI, port 8800, `start_web.bat` → `python -m app`
**Frontend**: React 18 + Vite 5 + Tailwind 3 (dev port 3000, proxy to 8800). Also legacy Jinja2 templates still in app/templates/.
**Worker**: Gemini worker (`gemini_worker.py`), runs on Windows
**Database**: PostgreSQL (speech_text DB, localhost:5432)
**GPU**: RTX A4000, CUDA

**Pipelines:**
- Primary (API): Deepgram (speaker+timestamps) + Gemini Flash (text correction) via OpenRouter
- Fallback (local): faster-whisper + pyannote speaker-diarization-3.1

**Deployment:** bat files via Task Scheduler

**How to apply:** คิดเรื่อง port 8800 (web) + 3000 (React dev), process management ผ่าน bat + Task Scheduler
