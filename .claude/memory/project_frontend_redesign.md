---
name: project_frontend_redesign
description: React frontend nearly complete — core pages done, polish remaining
type: project
---

Frontend redesign สถานะ 2026-04-06:

**Tech:** React 18 + Vite 5 + Tailwind CSS 3 + React Router + Lucide icons
**Style:** Linear.app bright theme
**Port:** React dev → 3000, FastAPI → 8800 (proxy via vite.config.js)
**Path:** D:/0_product_dev/speech_text/frontend/
**Note:** Node.js 20.17.0 → ต้องใช้ Vite 5 (ไม่ใช่ 8)

**เสร็จแล้ว:**
- Layout + Sidebar (grouped list, upload, create group, collapse) ✓
- Modal / Notification / ProgressSteps components ✓
- TranscriptionPage ✓
- AudioConfigPage ✓
- SpeakerPage ✓
- CorrectionPage ✓
- GroupSettingsPage ✓
- UploadPage ✓
- MomModal (edit, export, regenerate) ✓
- LandingPage (/home) ✓
- API client (src/api.js) ✓
- Backend CORS middleware ✓

**How to apply:** Core pages ครบแล้ว อาจเหลือ polish (animations, responsive) และ features ย่อยใน TranscriptionPage
