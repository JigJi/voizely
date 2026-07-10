---
name: Thai Phinthu U+0E3A in Teams calendar subjects
description: Invisible Thai Phinthu char sometimes prefixes meeting subjects in Outlook/Teams calendar events — breaks string matching
type: project
originSessionId: a986ebf0-8677-4f7a-a853-da13ac4b1b83
---
**Gotcha:** Microsoft Teams/Outlook calendar subjects บางครั้งมี **U+0E3A (Thai Phinthu "ฺ")** ซ่อนนำหน้า (มองไม่เห็นใน UI) เช่น `'ฺBD - Weekly Meeting'` vs filename ที่ parse ออกมา `'BD - Weekly Meeting'` → compare ไม่ตรง

**Why:** เจอวันที่ 2026-04-20 ขณะ debug ว่าทำไม user role ใน Voizely ไม่เห็นประชุมของตัวเอง (admin เห็นหมด) root cause จากการพิมพ์ชื่อประชุมบน Thai keyboard แล้วมี combining char หลุดเข้ามา Outlook ไม่ strip

**Fix ที่ทำแล้ว:**
- `TeamsClient._normalize_subject()` strip: ` \t\n\r\f\v\u00a0\ufeff\u200b\u200c\u200d\u2060\u0e3a` + collapse whitespace ใช้ทั้ง calendar fetch และ filename parse
- Backfill `user_calendar_cache` 4 rows ที่มี ฺ นำหน้า

**How to apply:**
- ถ้า user report "ประชุมไม่ขึ้น" / subject-based matching หลุด — นึกถึง invisible char ก่อนเสมอ
- String compare ที่เกี่ยวกับ Teams/Outlook/OneDrive ให้ normalize ด้วย `TeamsClient._normalize_subject` ทุกครั้ง
- Debug: ตรวจ repr ของ string (`print(repr(subject))`) ถ้าเห็น `\u0e3a` หรือ zero-width chars = เจอตัวการ
