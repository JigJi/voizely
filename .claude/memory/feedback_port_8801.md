---
name: Port architecture
description: 8801=FastAPI backend+old Jinja frontend, 3000=new React frontend (Vite). User uses 3000.
type: feedback
---

- **8801** = FastAPI backend, also serves OLD Jinja template pages (legacy)
- **3000** = NEW React frontend (Vite dev server), proxies /api → 8801
- User works on port 3000 (the new React app)
- Don't direct user to 8801 for frontend — that's the old UI

**Why:** User clarified the dual-frontend setup.
**How to apply:** Always reference port 3000 for frontend testing. Vite proxy to 8801 is correct for API calls.
