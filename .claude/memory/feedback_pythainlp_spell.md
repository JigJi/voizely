---
name: feedback_pythainlp_spell
description: PyThaiNLP spell.correct breaks text - removes spaces, adds garbage chars. Only use word_tokenize.
type: feedback
---

`pythainlp.spell.correct()` ทำพังมากกว่าช่วย — ลบ space เพิ่ม "กา" ระหว่างคำ ใช้ไม่ได้กับ speech-to-text output

**Why:** ทดสอบแล้ว "อยู่หรือเปล่า" → "อยู่มือเปล่ากา" เพราะ correct ทำทีละคำไม่ดูบริบท
**How to apply:** ใช้แค่ `pythainlp.tokenize.word_tokenize` สำหรับ fix speaker boundary เท่านั้น ห้ามใช้ `spell.correct` กับ transcription text
