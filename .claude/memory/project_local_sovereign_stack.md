---
name: project_local_sovereign_stack
description: "Sovereign tier R&D — replace Deepgram+Gemini with fully-local Thai ASR+MoM. Benchmarks done 2026-06-13, working baseline ~70%, not yet 90%"
metadata: 
  node_type: memory
  type: project
  originSessionId: 18a06d35-f6b0-46bb-987d-641cc222b557
---

**เริ่ม 2026-06-13:** Jig ตัดสินใจชัด — **เลิกพึ่ง Gemini+Deepgram, สร้าง local stack ที่ทำงานได้ 90%+** (มีลูกค้ารัฐรออยู่). เหตุผล: ขายรัฐไม่ได้ถ้าเสียงออก cloud (PDPA ม.28 ข้ามแดน + ชั้นความลับ + ตก security audit). คู่แข่งไทย (Gowajee/iApp/"Wajana") ขายรัฐ/แบงค์ได้เพราะ **เขาทำ ASR เอง+ on-prem** ("ข้อมูลอยู่ในเครื่องท่าน") — เราใช้ทางลัด cloud เลยติดประตูตลาดรัฐ. Sovereign tier (local) = ตั๋วเข้าสนาม. moat เราไม่ใช่ ASR (เขาก็มี) แต่คือ meeting-intelligence layer + IP diarize mono.

**Pipeline เดิม = cloud 3 จุด แต่ diarization local แล้ว → เหลือแทน 2:** ASR (Deepgram) + audio-correct/MoM (Gemini). Diarization (ECAPA+spectral / pyannote 3.1) local อยู่แล้ว ไม่ต้องแตะ. **Insight สำคัญ: คุณภาพ Deepgram+Gemini ส่วนใหญ่มาจากขั้น Gemini audio-correct (มันฟังเสียง) ไม่ใช่ ASR ดิบ** — reference เก็บ English 21/21, base ASR ทุกตัวเก็บ 0-7.

**Bench bake-off (ไฟล์ Teams จริง audio #160 = BD weekly, 15 นาทีแรก, เทียบ reference #159 Deepgram+spectral+Gemini). โค้ดอยู่ `experiments/` (bench_whisper.py, bench_pathumma_fw.py, correct_*.py, mom_typhoon.py, score_bench.py):**
- **Pathumma-whisper-large-v3 (NECTEC, Apache2)** = ดีสุดสำหรับ base. ผ่าน faster-whisper (CT2 float16): **1.9x realtime, timestamps ใช้ได้, English 7/21, เลขอารบิก**. ⚠️ large-v3 = 128 mel bins ต้อง save AutoFeatureExtractor ลง CT2 dir ไม่งั้น shape error (80 vs 128). + narrative "โมเดล NECTEC ของรัฐ" ขายรัฐแรงสุด.
- Qwen3-ASR-1.7B (Apache2, pip `qwen-asr` ติด `--no-deps` เลี่ยงอัป fastapi/starlette ของ backend): **25x realtime เร็วสุด, เบา**, แต่ไทยหยาบสุด + English 0/21 + timestamp พัง. เหมาะ realtime ไม่เหมาะ batch MoM.
- Monsoon-medium (SCB10X): 4.4x, แต่ render เลขเป็นเลขไทย ๓๔๐ + English 0/21 = ไม่เหมาะ.
- NVIDIA Parakeet/Canary, Sortformer = ตัดทิ้ง (ไทยไม่รองรับ / max 4 speakers).

**Correction layer — ผลทดสอบ:**
- **rule-based ฟรี (dict+เลข+dedup+pythainlp word_tokenize)**: ช่วยน้อย (7→8 English) เพราะ faster-whisper พ่น English เป็น English อยู่แล้ว + error ที่เหลือเป็นคำไทยมั่วระดับเสียง (อินเทอร์โน่=Internal, ดีพร=Deploy) dict จับไม่ได้.
- **Typhoon 2.5 4B (`scb10x/typhoon2.5-qwen3-4b`) text-correct**: ❌ FAIL — ไม่กู้ English, ไม่แปลงเลข, หลอน loop ซ้ำ. text-LLM ตาบอด แก้ acoustic error ไม่ได้.
- **สรุป: ทางไป 90% ไม่ใช่ text post-process — คือ ASR ที่ดี + (residual) audio-LLM ฟังเสียงซ้ำ.**

**MoM local (Typhoon 4B จาก transcript Pathumma/fw):** ✅ pipeline local ทำงาน end-to-end $0 cloud. จับ ~70% ของประเด็นใน 15-นาที clip (ALPR 60→40, Cloud budget 3เดือน≤15k+Dashboard, AD/VPN, Compact/Feedback, กล้อง). ❌ แต่: หลอน deadline/ชื่อทีม/「40บาท」, ลาก ASR garble "ดีพร" มาเป็นหัวข้อ, **ช้า 18 นาที/MoM** (bf16 greedy — ต้อง vLLM/Q4 GGUF). **ยังไม่ถึง 90%.**

**คันโยกไป 90% — ทดสอบครบแล้ว 2026-06-13:**
- ✅ **ข้อ 2 (chunked extract→merge MoM) + ข้อ 3 (speed) ทำแล้ว ได้ผล**: `experiments/mom_typhoon_chunked.py`. **speed fix = `attn_implementation="sdpa"`** (ต้นเหตุช้า 18นาที คือ eager attention กับ prompt ยาว ไม่ใช่ thinking-mode) → 4 นาที/MoM, **coverage 4→15 หัวข้อ ~85%** ไม่ต้องใช้ vLLM/GGUF (ไม่ได้ติดตั้ง). ไม่ต้องใช้ chunked extract→merge ของ production ก็ได้ — เขียนเองง่ายกว่า.
- ⚠️ **ข้อ 1 (speaker labels) ติด granularity**: faster-whisper segment ยาว ~25วิ/อัน (หลายคนปน) → ECAPA ให้ 1 speaker/segment = หยาบ (เหลือ 5 ก้อน). ต้องหั่น utterance สั้นก่อน (word_timestamps) เหมือน Deepgram. ยังไม่แก้.
- ❌ **glossary ฟรี (faster-whisper `initial_prompt`)**: marginal (7→8) + หลอน English ใหม่ ("Pvasya","Phase Edition"). ไม่ช่วย.
- ❌ **ข้อ 4 audio-LLM = ผลลบชี้ขาด**: Qwen2.5-Omni-7B (Thinker-only 4-bit, ฟิต 6.3GB) ทำ Thai ASR ซื่อตรงไม่ได้ — **paraphrase แทนถอด + วน loop + Thai อ่อน**, ไม่กู้ garble. Qwen3-Omni-30B ไม่ฟิต 16GB. (`experiments/omni_asr.py`)

**🎯 CEILING FINDING (สำคัญสุด): บน A4000 16GB วันนี้ ปิด audio-correct gap ของ Gemini ไม่ได้.** text-LLM ตาบอด, audio-LLM (Qwen-Omni) Thai อ่อน+paraphrase. คุณภาพ Deepgram+Gemini ~30-40% มาจากขั้น Gemini audio-correct ที่ local แทนไม่ได้ตอนนี้.
**3-way bench ในกลุ่ม "ทดสอบ" (admin, ไฟล์ bench_15min เดียวกัน) 2026-06-15:** #216 Pathumma (local $0, 669s, 35seg/4spk, 21 action+owner) / #217 Qwen (local $0, 151s, **1seg/1spk** owner รวมคนเดียว) / #218 **Cloud spectral+gemini ($0.071=~2.5บาท, 80s, 61seg/4spk, 8 action+owner)**. Cloud ชนะคุณภาพชัด: English ถูกหมด (Deploy/Internal/Feedback/ALPR/Performance/API/VPN/AI) + **voiceprint แมพชื่อจริง** (Kraiwit/Jirawat/Anusara/Charanpat) ซึ่ง local ยังไม่มี (local_worker ไม่เรียก voiceprint_service). **คันโยก local ถัดไป: เติม voiceprint suggestion ใน local_worker → owner เป็นชื่อจริงได้.** Cloud เร็วสุดเพราะ ASR/MoM เป็น API (local แบกบน GPU).
**Best achievable local = Pathumma/fw ASR + chunked Typhoon MoM (sdpa) = MoM ~85% coverage, $0 cloud** แต่มี garbled domain terms (On-Premise→บอลพิมพ์, Knowledge→No-Rate) หลุดเข้า MoM.
**ทางดันต่อ (ไม่ใช่ audio-LLM):** (a) fine-tune Pathumma บน audio domain ลูกค้า, (b) per-tenant glossary curation (คนแก้ครั้งเดียว ระบบจำ), (c) hardware ใหญ่ขึ้น (A6000 48GB → Qwen3-Omni-30B), (d) ลอง Typhoon-Audio (ยังไม่ทดสอบ). **ขายรัฐ: 85%-local ชนะ 0% (เขาใช้ cloud ไม่ได้เลย) — competitor ก็ไม่มี magic.**

**Test harness (เซฟไว้ให้ Jig เลือกโมเดลเองทดสอบ, 2026-06-13):** `experiments/run_local.py --audio X --asr pathumma|qwen|monsoon [--diarize] [--mom] [--glossary "..."]` → out/<file>__<asr>/ (transcript.txt/json, mom.md). **ไม่แตะ production.** README ใน experiments/. ⚠️⚠️ **2 Windows gotcha (เสียเวลา debug นานมาก อย่าซ้ำ):** (1) ctranslate2(faster-whisper)+torch+speechbrain โหลดรวม interpreter เดียว = hard-abort `Fatal Python error: Aborted` rc 0xC0000409; (2) faster-whisper `transcribe()` **ใน function = abort, ที่ module-level = ผ่าน**. แก้: run_local เป็น orchestrator บางๆ เรียก `_stage.py` เป็น **subprocess ต่อ stage** (1 CUDA lib/process, โค้ด model รัน module-level ไม่ใส่ def). อย่ารวมกลับเป็น in-process script เด็ดขาด.

**Productionize — WIRED IN 2026-06-15 (admin test mode):** ทำแล้วตามแผน worker แยก.
- `local_worker.py` (root, ลอกโครง gemini_worker): poll `status=pending AND model_size LIKE 'local%'` → เรียก `experiments/run_local.py` เป็น subprocess (--asr pathumma --diarize --mom --outdir tmp --max-sec) → อ่าน transcript.json+mom.md เขียนลง DB (segments/summary/mom_full/full_text), cost=0. มี `_ProgressTicker` thread (own DB session) creep 10→95%. respawn loop + code-mtime restart เหมือน gemini_worker.
- **gemini_worker.main() เพิ่ม filter `sa.func.coalesce(model_size,'').notlike('local%')`** เพื่อไม่แย่ง local job (NULL-safe). cloud pipeline ไม่ถูกแตะเลย.
- model routing: frontend select diarization='local' → `model_size='local+gemini'` → local_worker จับ prefix 'local' (ส่วน transcription part ไม่สน รัน pathumma+typhoon เสมอ).
- **ตัด 15 นาที (Jig ขอ): `--max-sec` ใน run_local.py (ffmpeg -t) + env `LOCAL_MAX_SEC` default 900** (0=เต็มไฟล์). ตั้งใน start_local_worker.bat.
- frontend: option `🧪 Local Sovereign (ทดสอบ)` ใน UploadPage + MeetingPage diarization dropdown, **admin-only** (`getUser()?.role==='ADMIN'`). build dist แล้ว (index-DqFTMedX.js).
- `start_local_worker.bat` สร้างแล้ว (pattern เดียวกับ start_gemini_worker.bat). **Jig ต้องเปิด worker เอง** (ผมไม่สตาร์ท).
- **END-TO-END GPU TEST ผ่านจริง 2026-06-15** (bench_15min.wav): ASR Pathumma 35 seg/500s → diarize 4 speakers → MoM Typhoon 160s, รวม ~11 นาที, exit 0, MoM ~85% (จับ GPU 3เดือน≤15k, ALPR 60→40, AD/VPN, กล้อง, Feedback; เพี้ยน "ดอก/เบ๊งควัน"). refactor `write_local_result(db,t,outdir,elapsed)` ใน local_worker = worker+ingest ใช้ร่วมกัน. `experiments/ingest_admin_test.py` สร้าง transcription จาก output dir เข้า DB. **ingest แล้ว: transcription #216 ในกลุ่ม "ทดสอบ" (group19) ของ admin (user1)**, status=completed, model_size=local+gemini, cost=0, dur=900s, 35 seg + MoM ครบ → Jig รีวิวใน UI ได้เลย /transcriptions/216.
- ⚠️ local MoM ยังไม่รับ group custom_instructions (gemini_worker รับ) — เพิ่มทีหลังได้.
- **ผู้รับผิดชอบ (owner) ใน action items (fix 2026-06-15):** local MoM เดิม owner หายหมด เพราะ MoM stage รับ text ไม่มี speaker label. แก้: run_local ป้อน **transcript ที่มี Speaker label** ให้ MoM stage (เมื่อ --diarize), prompt Typhoon ให้ขึ้นต้น bullet สิ่งที่ต้องทำ ด้วย `(ผู้รับผิดชอบ: Speaker N)`. ⚠️ gotcha: Typhoon ขึ้นบรรทัดด้วย tag ตรงๆ **ไม่ใส่ "-" นำหน้า** → parser ต้องรับทั้ง bullet และ owner-tag line (`_is_owner_tag`, `_parse_action_bullet` ดึง owner ออกจาก tag). `experiments/remom_local.py <outdir> <tid>` = re-run แค่ MoM stage จาก transcript เดิม (ไม่ re-ASR). ผล: #216 Pathumma 21 action items กระจาย Speaker1/2/3 (diarize 4 คน), #217 Qwen 5 items Speaker1 หมด (Qwen ได้ segment เดียว = ยืนยันว่า diarize ดีจำเป็นต่อ owner). owner = "Speaker N" (ยังไม่ map ชื่อจริงจาก voiceprint เหมือน cloud).
- **สิ่งที่ต้องทำ = ตาราง (fix 2026-06-15):** MomModal/docx parse "### สิ่งที่ต้องทำ" เป็น markdown table `| ลำดับ | รายละเอียด | กำหนดการ | ผู้รับผิดชอบ |` (cloud Gemini พ่นตารางอยู่แล้ว deadline=TBC owner=Speaker). local MoM (Typhoon) พ่น bullet → ตารางว่าง. แก้ที่ backend ฟรี deterministic: `mom_actions_to_table()` แปลง bullet→table + `_split_mom_sections()` populate JSON `topics/key_decisions/action_items[{task,deadline:TBC,owner:-}]/summary_short` (เหมือน cloud) ใน write_local_result. ไม่แตะ frontend. fix #216/#217 ใน DB แล้ว (inline script). MomModal อ่าน `mom_full||summary`.
- **เลือก ASR ได้แล้ว 2026-06-15:** model_size prefix → ASR. `local`/`local_pathumma`=Pathumma, `local_qwen`=Qwen, `local_monsoon`=Monsoon (`_ASR_MAP` ใน local_worker, `_asr_from_model_size`). dropdown มี option Pathumma + Qwen (admin). bottom-right TranscriptionPage โชว์ ASR จริง (head.startsWith('local')). gemini_worker filter `notlike('local%')` ครอบทุกตัว.
- **Qwen เทสต์จริง #217** (เทียบ Pathumma #216 ไฟล์เดียวกัน): Qwen **เร็วกว่ามาก 151s vs 669s** แต่ **ASR ได้ 1 segment** (timestamp อ่อน → diarize เหลือ 1 speaker, ไม่มีแยกผู้พูดจริง) + MoM เพี้ยนกว่า (งบ 15k เป็น "ต่อเดือน" แทน total, โมเอฟ/คอมแผงออโต้/ฟินแบก/โปรดิวชัน). **สรุป: Pathumma ดีกว่าชัดสำหรับ batch MoM + diarization; Qwen เหมาะ realtime/เร็วเท่านั้น** — ตรงกับ bench เดิม. `ingest_admin_test.py` รับ args (outdir, audio, model_size, title) reuse ได้.

**Group dedup bug fix (พบระหว่างทาง 2026-06-15):** admin (user1) มี "ทดสอบ" ซ้ำ 2 อัน (+ user13 MOF/Personal ซ้ำ) แก้ไม่ได้เพราะ `create_group` ไม่กันชื่อซ้ำ + auto-dedup ทำเฉพาะ default group. ลบตัวซ้ำว่างเปล่าออก (0 trans ทุกอัน) + patch `create_group` คืนกลุ่มเดิมถ้าชื่อซ้ำใน (tenant,user).

**Env:** RTX A4000 16GB, torch 2.6+cu124, transformers 4.57.6, faster-whisper 1.2.1, ctranslate2 4.7.1, pythainlp 5.0.4, qwen-asr 0.0.6, bitsandbytes 0.43.2. ⚠️ /tmp ของ Git-Bash กับ Windows-python คนละที่ + **PyAV/libav abort กับ backslash path** — เขียน/ส่ง path เป็น forward-slash ใน project folder.

เกี่ยวกับ [[project_multitenancy]] [[project_diarization_pipeline]] [[project_product_direction]] [[feedback_dont_reinvent]] [[feedback_ask_before_api_cost]].
