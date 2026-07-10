---
name: product_direction
description: API-first approach (Deepgram + Gemini Flash via OpenRouter), local models as fallback for privacy
type: project
---

เริ่มต้นด้วย local models only แต่ pivot เป็น API-first ตั้งแต่ ~2026-03-27

**Current approach:** Deepgram (speaker+timestamps) + Gemini Flash (text correction) ผ่าน OpenRouter
**Fallback:** เก็บ local pipeline (Whisper + pyannote) ไว้สำหรับ privacy-sensitive use cases

**Why:** Local pipeline ทำงานได้แต่ maintenance cost สูงเกินไป — WSL/Windows conflicts, GPU memory, zombie processes, LLM timeout — Gemini Flash ทำได้ใน 1 API call
**How to apply:** Default แนะนำ API approach, ถามก่อนเสมอถ้าจะ build local pipeline ใหม่
