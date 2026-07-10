# สำหรับคนที่รับงานต่อ (ทำงานกับ Claude Code)

โฟลเดอร์นี้คือ **memory / บริบทของโปรเจกต์** ที่ Claude Code สะสมไว้ระหว่างพัฒนา
เอาไว้ให้ Claude เข้าใจโปรเจกต์เร็วขึ้น ไม่ต้องอธิบายใหม่ทุกครั้ง

## มีอะไรบ้าง

- `CLAUDE.md` (อยู่ที่ root ของ repo) — คู่มือโปรเจกต์: architecture, pipeline, กฎการทำงาน อ่านอันนี้ก่อน
- `.claude/memory/MEMORY.md` — สารบัญ memory ทั้งหมด (1 บรรทัด/เรื่อง)
- `.claude/memory/*.md` — memory รายเรื่อง เช่น
  - `project_*` — สิ่งที่กำลังทำ, ทิศทาง, สถาปัตยกรรม, ปัญหาที่รู้แล้ว
  - `feedback_*` — บทเรียน/กฎที่เจ้าของเดิมสรุปไว้ (เช่น ห้าม kill python ทั้งหมด, ถามก่อนเรียก API ที่มีค่าใช้จ่าย)

## ใช้ยังไง

**ทางง่าย (แนะนำ):** เปิด Claude Code ในโปรเจกต์นี้ แล้วสั่งว่า
> "อ่าน .claude/memory/MEMORY.md แล้วไล่อ่านไฟล์ที่เกี่ยวข้องก่อนเริ่มงาน"

Claude จะดึงบริบททั้งหมดมาเข้าใจโปรเจกต์ทันที

**ทางให้ auto-load จริง (optional):** memory ของ Claude Code ผูกกับ path เครื่อง
ถ้าอยากให้มันโหลดเองอัตโนมัติทุก session ให้ก๊อปไฟล์ในโฟลเดอร์นี้ไปวางที่:

```
C:\Users\<ชื่อ user>\.claude\projects\<ชื่อ-path-โปรเจกต์-ของเครื่องคุณ>\memory\
```

`<ชื่อ-path-โปรเจกต์>` = path ของโปรเจกต์บนเครื่องคุณ แทน `\` และ `:` ด้วย `-`
เช่นถ้า clone ไว้ที่ `D:\work\speech_text` จะได้ `D--work-speech-text`
(หาโฟลเดอร์ที่ถูกต้องได้ง่ายๆ โดยเปิด Claude Code ในโปรเจกต์ 1 ครั้ง แล้ว Claude จะสร้าง path ให้เอง)

## setup โปรเจกต์ (สรุปสั้น)

1. `git clone` แล้ว **ขอไฟล์ `.env` แยกจากเจ้าของเดิม** (ไม่อยู่ใน git เพราะมี API key + DB password)
2. Backend: สร้าง venv → `pip install -r requirements.txt` → `alembic upgrade head`
3. Frontend: `cd frontend && npm install`
4. อ่าน `CLAUDE.md` section "Port Assignments" + "Production Deploy Checklist" ก่อนรัน
