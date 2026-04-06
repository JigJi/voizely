"""LLM post-processing: correct transcription + generate meeting summary."""

import json
import logging
import time
import urllib.request
from dataclasses import dataclass

from app.config import settings

logger = logging.getLogger(__name__)

CORRECTION_PROMPT = """คุณเป็นผู้เชี่ยวชาญแก้ไขข้อความถอดเสียงภาษาไทย

กรุณาแก้ไขข้อความด้านล่าง:
1. แก้คำถอดเสียงผิด โดยเฉพาะศัพท์เทคนิคและชื่อเฉพาะ
2. เพิ่มเครื่องหมายวรรคตอน (จุด, คอมม่า) ให้อ่านง่าย
3. แบ่งย่อหน้าตามหัวข้อ
4. คงความหมายเดิม ห้ามเพิ่มเนื้อหาที่ไม่ได้พูด
{vocab_section}
ข้อความ:
---
{text}
---

ข้อความที่แก้ไขแล้ว:"""

SUMMARY_PROMPT = """คุณเป็นผู้เชี่ยวชาญสรุปการประชุมภาษาไทย

จากข้อความถอดเสียงการประชุมด้านล่าง กรุณาสรุปเป็น Markdown:

## หัวข้อที่พูดคุย
- (สรุปหัวข้อหลักแต่ละข้อ)

## สิ่งที่ตัดสินใจ
- (decisions ที่ได้ข้อสรุป)

## Action Items
- [ ] (สิ่งที่ต้องทำ + ผู้รับผิดชอบ ถ้ามี)

ข้อความ:
---
{text}
---

สรุป:"""


SEGMENT_CORRECTION_PROMPT = """คุณเป็นผู้เชี่ยวชาญแก้ไขข้อความถอดเสียงภาษาไทย

ด้านล่างคือข้อความถอดเสียงจากการประชุม แต่ละบรรทัดมีรูปแบบ: [เลข] ข้อความ

กรุณาแก้ไขข้อความแต่ละบรรทัดให้ถูกต้อง:
- แก้เฉพาะคำที่ผิดชัดเจน เช่น คำผิดสะกด ศัพท์เทคนิคที่ฟังผิด
- ถ้าไม่แน่ใจว่าคำไหนผิด ให้คงคำเดิมไว้ ห้ามเดา
- ห้ามเพิ่มหรือลบเนื้อหา ห้ามเรียบเรียงประโยคใหม่
- คงจำนวนบรรทัดเท่าเดิม ห้ามรวมหรือแยกบรรทัด
- ตอบเฉพาะข้อความที่แก้แล้ว รูปแบบเดิม [เลข] ข้อความ
{vocab_section}
ข้อความ:
---
{text}
---

ข้อความที่แก้ไขแล้ว:"""


SPEAKER_ID_PROMPT = """จากข้อความถอดเสียงการประชุมด้านล่าง แต่ละ segment มี label ผู้พูด (Speaker 1, Speaker 2, ...)

กรุณาวิเคราะห์ว่าแต่ละ Speaker คือใคร โดยดูจาก:
- การเรียกชื่อกัน เช่น "พี่เบน", "คุณสมชาย", "น้องปุ๋ย"
- การแนะนำตัว เช่น "ผมชื่อ...", "สวัสดีครับ ผม..."
- บริบทการพูด เช่น ใครเป็นผู้นำเสนอ ใครถาม

ตอบเป็น JSON เท่านั้น ห้ามมีข้อความอื่น:
{{"Speaker 1": "ชื่อจริงหรือชื่อเล่น", "Speaker 2": "ชื่อจริงหรือชื่อเล่น"}}

ถ้าไม่แน่ใจว่าชื่ออะไร ให้ใส่ "ผู้พูด 1" หรือบทบาท เช่น "ผู้นำเสนอ", "ผู้ถาม"

ข้อความ:
---
{text}
---

JSON:"""


@dataclass
class LLMResult:
    text: str
    time_seconds: float
    tokens_in: int = 0
    tokens_out: int = 0


def _call_openrouter(prompt: str) -> LLMResult:
    payload = json.dumps({
        "model": settings.OPENROUTER_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 8000,
        "temperature": 0.1,
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {settings.OPEN_ROUNTER}",
            "Content-Type": "application/json",
        },
    )

    t0 = time.time()
    with urllib.request.urlopen(req, timeout=settings.LLM_TIMEOUT) as resp:
        result = json.loads(resp.read().decode("utf-8"))
    elapsed = time.time() - t0

    usage = result.get("usage", {})
    return LLMResult(
        text=result["choices"][0]["message"]["content"],
        time_seconds=elapsed,
        tokens_in=usage.get("prompt_tokens", 0),
        tokens_out=usage.get("completion_tokens", 0),
    )


def _call_ollama(prompt: str) -> LLMResult:
    payload = json.dumps({
        "model": settings.OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.1,
            "num_predict": 4000,
            "repeat_penalty": 1.3,
            "repeat_last_n": 256,
        },
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{settings.OLLAMA_BASE_URL}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    t0 = time.time()
    with urllib.request.urlopen(req, timeout=settings.LLM_TIMEOUT) as resp:
        result = json.loads(resp.read().decode("utf-8"))
    elapsed = time.time() - t0

    return LLMResult(
        text=result.get("response", ""),
        time_seconds=elapsed,
        tokens_in=result.get("prompt_eval_count", 0),
        tokens_out=result.get("eval_count", 0),
    )


def _call_llm(prompt: str, provider: str) -> LLMResult:
    if provider == "openrouter":
        return _call_openrouter(prompt)
    elif provider == "ollama":
        return _call_ollama(prompt)
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")


def _clean_repetition(text: str) -> str:
    """Remove repeated phrases/words from LLM output."""
    # Detect and truncate at repetition (e.g., "AI, AI, AI, AI...")
    import re
    # Find any word/phrase repeated more than 5 times consecutively
    cleaned = re.sub(r'(\b\S+\b(?:,?\s*)){5,}?\1(?:,?\s*\1){4,}', r'\1', text)
    # Also truncate if the same short pattern repeats
    for length in range(2, 20):
        pattern = text[-length:]
        if text.count(pattern) > 10 and len(pattern.strip()) > 0:
            # Find where repetition starts
            first_repeat = text.find(pattern + " " + pattern)
            if first_repeat > 0 and first_repeat < len(text) * 0.8:
                cleaned = text[:first_repeat + length]
                break
    return cleaned.strip()


def correct_text(
    raw_text: str, provider: str, custom_vocab: str | None = None
) -> LLMResult:
    vocab_section = ""
    if custom_vocab and custom_vocab.strip():
        vocab_section = f"\nคำศัพท์เฉพาะทางที่ควรใช้: {custom_vocab.strip()}\n"

    # Truncate input if too long (avoid context overflow)
    if len(raw_text) > 6000:
        raw_text = raw_text[:6000]

    prompt = CORRECTION_PROMPT.format(text=raw_text, vocab_section=vocab_section)
    logger.info("LLM correction via %s (%d chars input)", provider, len(raw_text))
    result = _call_llm(prompt, provider)
    result.text = _clean_repetition(result.text)
    logger.info("LLM correction done in %.1fs (%d tokens out)", result.time_seconds, result.tokens_out)
    return result


def generate_summary(raw_text: str, provider: str) -> LLMResult:
    if len(raw_text) > 6000:
        raw_text = raw_text[:6000]

    prompt = SUMMARY_PROMPT.format(text=raw_text)
    logger.info("LLM summary via %s", provider)
    result = _call_llm(prompt, provider)
    result.text = _clean_repetition(result.text)
    logger.info("LLM summary done in %.1fs", result.time_seconds)
    return result


def correct_segments(
    segments: list[dict], provider: str, custom_vocab: str | None = None
) -> dict[int, str]:
    """Correct text per segment. Returns {index: corrected_text}."""
    vocab_section = ""
    if custom_vocab and custom_vocab.strip():
        vocab_section = f"\nคำศัพท์เฉพาะทางที่ควรใช้: {custom_vocab.strip()}\n"

    # Build numbered lines
    lines = []
    for seg in segments:
        idx = seg.get("index", 0)
        text = seg.get("text", "").strip()
        if text:
            lines.append(f"[{idx}] {text}")

    # Batch in chunks (max ~1500 chars per batch for faster response)
    batches = []
    cur_batch = []
    cur_len = 0
    for line in lines:
        if cur_len + len(line) > 1500 and cur_batch:
            batches.append(cur_batch)
            cur_batch = []
            cur_len = 0
        cur_batch.append(line)
        cur_len += len(line)
    if cur_batch:
        batches.append(cur_batch)

    import re
    result_map = {}
    for batch in batches:
        batch_text = "\n".join(batch)
        prompt = SEGMENT_CORRECTION_PROMPT.format(text=batch_text, vocab_section=vocab_section)

        # Extract indices from batch for fallback
        batch_indices = []
        for line in batch:
            m = re.match(r'\[(\d+)\]', line)
            if m:
                batch_indices.append(int(m.group(1)))

        try:
            llm_result = _call_llm(prompt, provider)
            cleaned = _clean_repetition(llm_result.text)

            # Try parsing [idx] text lines
            parsed = {}
            for match in re.finditer(r'\[(\d+)\]\s*(.+)', cleaned):
                idx = int(match.group(1))
                text = match.group(2).strip()
                parsed[idx] = text

            if parsed:
                result_map.update(parsed)
            elif len(batch_indices) == 1 and cleaned.strip():
                # Single segment batch, LLM returned plain text without [idx]
                result_map[batch_indices[0]] = cleaned.strip()
            else:
                # Multi-segment batch, LLM returned without [idx] format
                # Try splitting by newlines and matching by position
                result_lines = [l.strip() for l in cleaned.strip().split("\n") if l.strip()]
                for i, idx in enumerate(batch_indices):
                    if i < len(result_lines):
                        line = re.sub(r'^\[\d+\]\s*', '', result_lines[i])
                        result_map[idx] = line
                logger.info("Fallback parsing: matched %d lines for %s", min(len(result_lines), len(batch_indices)), provider)

        except Exception as e:
            logger.warning("Segment correction batch failed: %s", e)

    logger.info("Corrected %d/%d segments via %s", len(result_map), len(lines), provider)
    return result_map


def identify_speakers(
    segments: list[dict], provider: str
) -> dict[str, str]:
    """Identify speaker names from transcript context.

    Returns mapping like {"Speaker 1": "พี่เบน", "Speaker 2": "คุณจี๊ด"}
    """
    # Build transcript with speaker labels
    lines = []
    for seg in segments:
        speaker = seg.get("speaker", "Unknown")
        text = seg.get("text", "")[:200]
        start = seg.get("start", 0)
        lines.append(f"[{speaker}] ({start:.0f}s) {text}")

    transcript = "\n".join(lines)
    prompt = SPEAKER_ID_PROMPT.format(text=transcript)

    logger.info("LLM speaker identification via %s", provider)
    result = _call_llm(prompt, provider)
    logger.info("LLM speaker ID done in %.1fs", result.time_seconds)

    # Parse JSON from response
    try:
        raw = result.text.strip()
        # Extract JSON if wrapped in markdown code block
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        mapping = json.loads(raw)
        if isinstance(mapping, dict):
            logger.info("Speaker mapping: %s", mapping)
            return mapping
    except (json.JSONDecodeError, IndexError) as e:
        logger.warning("Failed to parse speaker mapping: %s — raw: %s", e, result.text[:200])

    return {}
