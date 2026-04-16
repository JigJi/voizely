"""
Hybrid Worker: Pyannote (Speaker Diarization) + Gemini (Thai Transcription)
Pyannote → Speaker Timeline Guide → Gemini listens & transcribes
"""
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import time
import base64
import urllib.request
import threading
import sqlalchemy as sa

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s %(message)s")
logger = logging.getLogger("worker")


class ProgressTicker:
    """ค่อยๆ เพิ่ม progress ทีละ 1% ระหว่างรอ long-running task."""

    def __init__(self, db, transcription, start_pct, end_pct, message, interval=3):
        self.db = db
        self.t = transcription
        self.transcription_id = transcription.id
        self.current = start_pct
        self.end = end_pct
        self.message = message
        self.interval = interval
        self._stop = threading.Event()
        # Set initial progress on main session
        transcription.progress_percent = start_pct
        transcription.status_message = message
        db.commit()

    def __enter__(self):
        self._thread = threading.Thread(target=self._tick, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *args):
        self._stop.set()
        self._thread.join(timeout=2)
        # Refresh main session to see ticker's updates
        self.db.refresh(self.t)
        self.t.progress_percent = self.end
        self.db.commit()

    def _tick(self):
        """ใช้ DB session แยกเพื่อไม่ชนกับ main thread."""
        from app.database import SessionLocal
        tick_db = SessionLocal()
        try:
            while not self._stop.is_set():
                self._stop.wait(self.interval)
                if self._stop.is_set():
                    break
                if self.current < self.end - 1:
                    self.current += 1
                    try:
                        tick_db.execute(
                            sa.text("UPDATE transcriptions SET progress_percent = :pct WHERE id = :tid"),
                            {"pct": self.current, "tid": self.transcription_id},
                        )
                        tick_db.commit()
                    except Exception:
                        tick_db.rollback()
        finally:
            tick_db.close()

from app.database import SessionLocal
from app.models.audio import AudioFile, AudioStatus
from app.models.transcription import (
    Transcription, TranscriptionSegment, TranscriptionStatus,
)
from app.config import settings


# === Pyannote Model (loaded once) ===

_pyannote_pipeline = None


def _get_pyannote():
    global _pyannote_pipeline
    if _pyannote_pipeline is None:
        import torch
        original_load = torch.load
        def patched_load(*args, **kwargs):
            kwargs['weights_only'] = False
            return original_load(*args, **kwargs)
        torch.load = patched_load
        from pyannote.audio import Pipeline
        logger.info("Loading Pyannote model...")
        _pyannote_pipeline = Pipeline.from_pretrained(
            'pyannote/speaker-diarization-3.1', use_auth_token=True
        )
        _pyannote_pipeline.to(torch.device('cuda'))
        logger.info("Pyannote model loaded")
    return _pyannote_pipeline


# === Step 1: Pyannote → Speaker Timeline Guide ===

def build_timeline_guide(audio_path):
    """Run Pyannote diarization, return timeline guide string + segments."""
    pipeline = _get_pyannote()

    # Convert to WAV for Pyannote
    wav_path = audio_path + ".pyannote.wav"
    subprocess.run([
        "ffmpeg", "-y", "-i", audio_path,
        "-ar", "16000", "-ac", "1", wav_path,
    ], capture_output=True, check=True)

    # Get duration
    probe = subprocess.run([
        "ffprobe", "-v", "quiet", "-show_entries", "format=duration",
        "-of", "csv=p=0", audio_path,
    ], capture_output=True, text=True)
    duration = float(probe.stdout.strip())

    try:
        diarization = pipeline(wav_path)
    finally:
        if os.path.exists(wav_path):
            os.remove(wav_path)

    # Convert pyannote output to segments
    raw_segments = []
    speaker_map = {}
    speaker_idx = 0
    for turn, _, speaker in diarization.itertracks(yield_label=True):
        if speaker not in speaker_map:
            speaker_map[speaker] = speaker_idx
            speaker_idx += 1
        raw_segments.append({
            "start": turn.start,
            "end": turn.end,
            "speaker": speaker_map[speaker],
        })

    if not raw_segments:
        raise RuntimeError("Pyannote returned no speaker segments")

    # Merge consecutive same-speaker segments
    merged = [raw_segments[0]]
    for seg in raw_segments[1:]:
        if seg["speaker"] == merged[-1]["speaker"] and seg["start"] - merged[-1]["end"] < 1.0:
            merged[-1]["end"] = seg["end"]
        else:
            merged.append(dict(seg))

    # Build timeline guide with gap detection
    guide_lines = []
    segments = []

    for i, seg in enumerate(merged):
        if i > 0:
            prev_end = merged[i - 1]["end"]
            gap = seg["start"] - prev_end
            if gap > 2.0:
                guide_lines.append(
                    f"{_fmt(prev_end)} - {_fmt(seg['start'])} : [Gap - Please listen carefully for any speech]"
                )
                segments.append({
                    "start": prev_end,
                    "end": seg["start"],
                    "speaker": -1,
                    "is_gap": True,
                })

        guide_lines.append(
            f"{_fmt(seg['start'])} - {_fmt(seg['end'])} : Speaker {seg['speaker'] + 1}"
        )
        segments.append({
            "start": seg["start"],
            "end": seg["end"],
            "speaker": seg["speaker"],
            "is_gap": False,
        })

    # Gap at end
    if merged and duration > 0 and (duration - merged[-1]["end"]) > 2.0:
        guide_lines.append(
            f"{_fmt(merged[-1]['end'])} - {_fmt(duration)} : [Gap - Please listen carefully for any speech]"
        )
        segments.append({
            "start": merged[-1]["end"],
            "end": duration,
            "speaker": -1,
            "is_gap": True,
        })

    num_speakers = len(speaker_map)
    guide = "[Speaker Timeline Guide]\n\n" + "\n\n".join(guide_lines)
    logger.info("Pyannote: %d segments, %d speakers, %.0fs", len(segments), num_speakers, duration)
    return guide, segments, duration, num_speakers


def build_timeline_guide_deepgram(audio_path):
    """Call Deepgram for diarization, return timeline guide string + segments."""
    import httpx

    # Re-encode to ensure bitrate >= 64kbps (low bitrate kills diarization)
    re_encoded = audio_path + ".re.m4a"
    subprocess.run([
        "ffmpeg", "-y", "-i", audio_path,
        "-ar", "16000", "-ac", "1", "-b:a", "64k", re_encoded,
    ], capture_output=True, check=True)

    with open(re_encoded, "rb") as f:
        audio = f.read()

    content_type = "audio/mp4"

    try:
        response = httpx.post(
            "https://api.deepgram.com/v1/listen",
            params={"model": "nova-3", "language": "th", "diarize": "true", "utterances": "true", "smart_format": "true"},
            headers={"Authorization": f"Token {settings.DEEPGRAM_API_KEY}", "Content-Type": content_type},
            content=audio, timeout=300,
        )
        response.raise_for_status()
        result = response.json()
    finally:
        if os.path.exists(re_encoded):
            os.remove(re_encoded)

    utterances = result.get("results", {}).get("utterances", [])
    duration = result.get("metadata", {}).get("duration", 0)

    if not utterances:
        raise RuntimeError("Deepgram returned no utterances")

    # Merge consecutive same-speaker
    merged = []
    for u in utterances:
        speaker = u["speaker"]
        if merged and merged[-1]["speaker"] == speaker:
            merged[-1]["end"] = u["end"]
        else:
            merged.append({"start": u["start"], "end": u["end"], "speaker": speaker})

    guide_lines = []
    segments = []
    for i, seg in enumerate(merged):
        if i > 0:
            gap = seg["start"] - merged[i - 1]["end"]
            if gap > 2.0:
                guide_lines.append(f"{_fmt(merged[i-1]['end'])} - {_fmt(seg['start'])} : [Gap]")
                segments.append({"start": merged[i-1]["end"], "end": seg["start"], "speaker": -1, "is_gap": True})
        guide_lines.append(f"{_fmt(seg['start'])} - {_fmt(seg['end'])} : Speaker {seg['speaker'] + 1}")
        segments.append({"start": seg["start"], "end": seg["end"], "speaker": seg["speaker"], "is_gap": False})

    num_speakers = len(set(s["speaker"] for s in segments if not s.get("is_gap")))
    guide = "[Speaker Timeline Guide]\n\n" + "\n\n".join(guide_lines)
    return guide, segments, duration, num_speakers


def build_timeline_guide_llm(audio_path, model="google/gemini-2.5-flash"):
    """Use LLM (Gemini/GPT) for diarization only, return timeline guide."""
    compressed = _compress_audio(audio_path)

    # Get duration
    probe = subprocess.run([
        "ffprobe", "-v", "quiet", "-show_entries", "format=duration",
        "-of", "csv=p=0", audio_path,
    ], capture_output=True, text=True)
    duration = float(probe.stdout.strip())

    # Cut into 5-min chunks for diarization
    chunk_dur = 300
    all_segments = []
    t = 0
    chunk_idx = 0
    while t < duration:
        end = min(t + chunk_dur, duration)
        chunk_path = compressed + f".diar{chunk_idx}.mp3"
        subprocess.run([
            "ffmpeg", "-y", "-i", compressed,
            "-ss", str(t), "-to", str(end), "-c", "copy", chunk_path,
        ], capture_output=True)

        with open(chunk_path, "rb") as f:
            audio_b64 = base64.b64encode(f.read()).decode()

        prompt = f"""ฟังไฟล์เสียงนี้ ระบุเฉพาะช่วงเวลาและผู้พูด ห้ามถอดคำ
แยกผู้พูดจากน้ำเสียง ตั้งชื่อ Speaker 1, 2, ...

กฎสำคัญ:
- รวมคำพูดต่อเนื่องของคนเดียวกันเป็น segment เดียวเสมอ ห้ามซอยทีละวินาที
- แต่ละ segment ควรยาวอย่างน้อย 5-10 วินาที ยกเว้นคนพูดสั้นมาก
- สนใจแค่ว่าใครพูดช่วงไหน ไม่ต้องใส่ข้อความ

ตอบ JSON array เท่านั้น:
[{{"start": "MM:SS", "end": "MM:SS", "speaker": "Speaker 1"}}]"""

        content = [
            {"type": "text", "text": prompt},
            {"type": "input_audio", "input_audio": {"data": audio_b64, "format": "mp3"}},
        ]

        payload = json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": content}],
            "max_tokens": 8000,
            "temperature": 0,
        }).encode("utf-8")

        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/chat/completions",
            data=payload,
            headers={
                "Authorization": f"Bearer {settings.OPEN_ROUNTER}",
                "Content-Type": "application/json",
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                result = json.loads(resp.read().decode("utf-8"))
            raw = result["choices"][0]["message"]["content"].strip()
            if raw.startswith("```"):
                raw = "\n".join(raw.split("\n")[1:-1])
            raw = re.sub(r'[\x00-\x1f\x7f]', lambda m: '' if m.group() not in '\n\r\t' else m.group(), raw)
            try:
                chunk_segs = json.loads(raw, strict=False)
            except json.JSONDecodeError:
                # Truncated JSON - try to recover
                raw = raw.rsplit("}", 1)[0] + "}]"
                chunk_segs = json.loads(raw, strict=False)

            # Offset timestamps back to absolute
            for seg in chunk_segs:
                start_sec = _parse_time(str(seg.get("start", "0:0"))) + t
                end_sec = _parse_time(str(seg.get("end", "0:0"))) + t
                all_segments.append({
                    "start": start_sec,
                    "end": end_sec,
                    "speaker_name": seg.get("speaker", "Speaker 1"),
                })
        except Exception as e:
            logger.warning("LLM diarization chunk %d failed: %s", chunk_idx, e)

        if os.path.exists(chunk_path):
            os.remove(chunk_path)
        t = end
        chunk_idx += 1

    if os.path.exists(compressed):
        os.remove(compressed)

    if not all_segments:
        raise RuntimeError("LLM diarization returned no segments")

    # Map speaker names to indices
    speaker_map = {}
    speaker_idx = 0
    for seg in all_segments:
        name = seg["speaker_name"]
        if name not in speaker_map:
            speaker_map[name] = speaker_idx
            speaker_idx += 1

    # Build guide
    guide_lines = []
    segments = []
    for seg in all_segments:
        spk_idx = speaker_map[seg["speaker_name"]]
        guide_lines.append(f"{_fmt(seg['start'])} - {_fmt(seg['end'])} : Speaker {spk_idx + 1}")
        segments.append({"start": seg["start"], "end": seg["end"], "speaker": spk_idx, "is_gap": False})

    num_speakers = len(speaker_map)
    guide = "[Speaker Timeline Guide]\n\n" + "\n\n".join(guide_lines)
    return guide, segments, duration, num_speakers


def _fmt(seconds):
    """Format seconds to MM:SS.ss"""
    m, s = divmod(seconds, 60)
    return f"{int(m):02d}:{s:05.2f}"


# === Step 2: Gemini Transcription ===

GEMINI_PROMPT = """คุณคือผู้เชี่ยวชาญด้านการถอดความ ภารกิจของคุณคือฟังไฟล์เสียงที่แนบมา และถอดความเป็นข้อความที่ถูกต้อง 100% โดยใช้ Speaker Timeline Guide ที่เตรียมไว้ให้เป็นโครงสร้างหลัก

นี่คือไฟล์เสียงประชุม และนี่คือ Speaker Timeline Guide:

{timeline}

กฎเหล็กในการทำงาน:
1. ยึดเวลาตาม Guide: ห้ามเดาช่วงเวลาใหม่ ให้ถอดความตามวินาทีที่ระบุไว้
2. เติมเต็มช่วงที่หาย: ในช่วง [Gap] ให้ตั้งใจฟังเป็นพิเศษ หากมีคนพูดให้ถอดความออกมาและระบุเป็น Speaker ที่เหมาะสม
3. แก้คำสะกด: แก้ไขศัพท์เทคนิคให้ถูกต้อง
4. ถอดความตามภาษาที่ผู้พูดใช้จริง (ไทย อังกฤษ หรือปนกัน) ถ้าเป็นภาษาไทยให้เขียนแบบปกติไม่เว้นวรรคระหว่างคำ เว้นเฉพาะรอบคำอังกฤษ
5. ถ้าเป็นภาษาไทยถิ่น ให้แปลงเป็นภาษาไทยกลางมาตรฐาน
6. ถอดความทุกช่วงเวลาตั้งแต่ต้นจนจบ ห้ามข้าม
7. ห้ามเขียนคำซ้ำ: หากพบว่าตัวเองกำลังเขียนคำหรือวลีเดิมซ้ำเกิน 2 ครั้ง ให้หยุดทันทีและข้ามไป Segment ถัดไป ห้ามพยายามเติมคำในช่วงเงียบ

ตอบเป็น JSON array เท่านั้น ห้ามมีข้อความอื่น:
[
  {{"start": "00:00.00", "end": "00:29.27", "speaker": "Speaker 1", "text": "ข้อความ"}},
  {{"start": "00:29.27", "end": "00:44.08", "speaker": "Speaker 2", "text": "ข้อความ"}}
]"""


def _load_voice_samples():
    """Load reference voice samples from voice_samples/ folder."""
    voice_dir = os.path.join(os.path.dirname(__file__), "voice_samples")
    samples = []
    if not os.path.isdir(voice_dir):
        return samples
    for f in os.listdir(voice_dir):
        if f.lower().endswith((".m4a", ".mp3", ".wav", ".ogg", ".flac", ".webm")):
            name = os.path.splitext(f)[0]
            path = os.path.join(voice_dir, f)
            with open(path, "rb") as fh:
                b64 = base64.b64encode(fh.read()).decode()
            ext = os.path.splitext(f)[1].lstrip(".")
            if ext == "m4a":
                ext = "mp4"
            samples.append({"name": name, "b64": b64, "format": ext})
    return samples


def _compress_audio(audio_path):
    """Convert audio to mono 16kHz mp3 for smaller payload."""
    out_path = audio_path + ".compressed.mp3"
    subprocess.run([
        "ffmpeg", "-y", "-i", audio_path,
        "-ac", "1", "-ar", "16000", "-b:a", "48k",
        out_path,
    ], capture_output=True, check=True)
    return out_path


def _cut_audio(audio_path, start_sec, end_sec, out_path):
    """Cut a segment from audio file using ffmpeg."""
    subprocess.run([
        "ffmpeg", "-y", "-i", audio_path,
        "-ss", str(start_sec), "-to", str(end_sec),
        "-c", "copy", out_path,
    ], capture_output=True, check=True)
    return out_path


def _build_chunks(dg_segments, duration, max_chunk_sec=300):
    """Split Deepgram segments into chunks of ~max_chunk_sec, cutting at speaker boundaries.
    Falls back to time-based splitting if no speaker boundaries exist."""
    non_gap = [s for s in dg_segments if not s.get("is_gap")]

    # Force time-based splitting if segments are too few or any segment is too long
    has_long_seg = any((s["end"] - s["start"]) > max_chunk_sec for s in non_gap)
    if len(non_gap) <= 1 or has_long_seg:
        chunks = []
        t = 0
        while t < duration:
            end = min(t + max_chunk_sec, duration)
            chunks.append({
                "start": t,
                "end": end,
                "segments": [s for s in non_gap if s["start"] < end and s["end"] > t],
            })
            t = end
        return chunks

    chunks = []
    current_start = 0
    current_segs = []

    for seg in non_gap:
        current_segs.append(seg)
        # Check if chunk is long enough and we're at a speaker boundary
        chunk_dur = seg["end"] - current_start
        if chunk_dur >= max_chunk_sec:
            chunks.append({
                "start": current_start,
                "end": seg["end"],
                "segments": current_segs,
            })
            current_start = seg["end"]
            current_segs = []

    # Remaining
    if current_segs:
        chunks.append({
            "start": current_start,
            "end": duration,
            "segments": current_segs,
        })

    return chunks


def _build_chunk_guide(chunk):
    """Build timeline guide for a single chunk, with timestamps relative to chunk start."""
    offset = chunk["start"]
    lines = []
    for seg in chunk["segments"]:
        lines.append(f"{_fmt(seg['start'] - offset)} - {_fmt(seg['end'] - offset)} : Speaker {seg['speaker'] + 1}")
    return "[Speaker Timeline Guide]\n\n" + "\n\n".join(lines)


def transcribe_chunked(audio_path, dg_segments, duration):
    """Compress audio, split into chunks, transcribe each with Gemini."""
    logger.info("Compressing audio...")
    compressed = _compress_audio(audio_path)
    compressed_size = os.path.getsize(compressed) / 1024 / 1024
    logger.info("Compressed: %.1f MB", compressed_size)

    chunks = _build_chunks(dg_segments, duration)
    logger.info("Split into %d chunks", len(chunks))

    all_segments = []
    total_usage = {"prompt_tokens": 0, "completion_tokens": 0}

    try:
        for i, chunk in enumerate(chunks):
            logger.info("Chunk %d/%d: %.0f-%.0fs", i + 1, len(chunks), chunk["start"], chunk["end"])

            # Cut audio for this chunk
            chunk_audio = compressed + f".chunk{i}.mp3"
            _cut_audio(compressed, chunk["start"], chunk["end"], chunk_audio)

            # Build guide for this chunk
            guide = _build_chunk_guide(chunk)

            try:
                # Retry up to 2 times on parse errors
                segments = None
                usage = {}
                for attempt in range(3):
                    try:
                        segments, usage = transcribe_with_gemini(chunk_audio, guide)
                        break
                    except (json.JSONDecodeError, KeyError) as e:
                        logger.warning("Chunk %d attempt %d failed: %s", i + 1, attempt + 1, e)
                        if attempt == 2:
                            logger.error("Chunk %d failed after 3 attempts, skipping", i + 1)
                            segments = []

                # Offset relative timestamps back to absolute
                for seg in (segments or []):
                    if "start" in seg and "end" in seg:
                        start_sec = _parse_time(str(seg["start"])) + chunk["start"]
                        end_sec = _parse_time(str(seg["end"])) + chunk["start"]
                        # Clamp to chunk bounds
                        start_sec = min(start_sec, chunk["end"])
                        end_sec = max(start_sec, min(end_sec, chunk["end"]))
                        seg["start"] = _fmt(start_sec)
                        seg["end"] = _fmt(end_sec)
                # Override speakers from Deepgram timeline
                segments = _assign_speakers_from_timeline(segments, dg_segments)
                all_segments.extend(segments)
                total_usage["prompt_tokens"] += usage.get("prompt_tokens", 0)
                total_usage["completion_tokens"] += usage.get("completion_tokens", 0)
            finally:
                if os.path.exists(chunk_audio):
                    os.remove(chunk_audio)
    finally:
        if os.path.exists(compressed):
            os.remove(compressed)

    return all_segments, total_usage


def transcribe_with_gemini(audio_path, timeline_guide):
    """Send audio + timeline guide + voice references to Gemini."""
    with open(audio_path, "rb") as f:
        audio_b64 = base64.b64encode(f.read()).decode()

    voice_samples = _load_voice_samples()

    prompt = GEMINI_PROMPT.format(timeline=timeline_guide)

    # Add voice identification instruction if samples exist
    if voice_samples:
        names = ", ".join(s["name"] for s in voice_samples)
        prompt += f"\n\n## Speaker Identification\nด้านล่างนี้คือเสียงตัวอย่างของผู้พูดที่รู้จัก: {names}\nให้เทียบเสียงในไฟล์ประชุมกับเสียงตัวอย่าง แล้วใส่ชื่อจริงแทน Speaker X ถ้าจับคู่ไม่ได้ให้ใช้ Unknown"

    content = [
        {"type": "text", "text": prompt},
    ]
    # Add reference voice clips
    for s in voice_samples:
        content.append({"type": "text", "text": f"เสียงตัวอย่างของ {s['name']}:"})
        content.append({"type": "input_audio", "input_audio": {"data": s["b64"], "format": s["format"]}})
    # Add meeting audio last
    ext = os.path.splitext(audio_path)[1].lstrip(".").lower()
    audio_fmt = {"mp3": "mp3", "wav": "wav", "m4a": "mp4", "ogg": "ogg", "flac": "flac"}.get(ext, "mp3")
    content.append({"type": "text", "text": "ไฟล์เสียงประชุม:"})
    content.append({"type": "input_audio", "input_audio": {"data": audio_b64, "format": audio_fmt}})

    payload = json.dumps({
        "model": "google/gemini-2.5-flash",
        "messages": [{"role": "user", "content": content}],
        "max_tokens": 65000,
        "temperature": 0,
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {settings.OPEN_ROUNTER}",
            "Content-Type": "application/json",
        },
    )

    with urllib.request.urlopen(req, timeout=180) as resp:
        result = json.loads(resp.read().decode("utf-8"))

    raw = result["choices"][0]["message"]["content"].strip()
    usage = result.get("usage", {})

    # Extract JSON
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1])
    raw = re.sub(r'[\x00-\x1f\x7f]', lambda m: '' if m.group() not in '\n\r\t' else m.group(), raw)

    segments = json.loads(raw, strict=False)

    # Clean Thai spacing
    for seg in segments:
        if "text" in seg:
            seg["text"] = re.sub(r'(?<=[\u0E00-\u0E7F])\s+(?=[\u0E00-\u0E7F])', '', seg["text"])

    # Remove repetition hallucinations
    for seg in segments:
        if "text" in seg:
            seg["text"] = _dedup_text(seg["text"])

    return segments, usage


def _dedup_text(text):
    """Detect and remove repeated phrases from hallucinated output."""
    # Try phrase lengths from 20 chars down to 3 chars
    for length in range(20, 2, -1):
        for i in range(len(text) - length * 3):
            phrase = text[i:i + length]
            # Count consecutive repeats of this phrase
            repeat_count = 1
            pos = i + length
            while pos + length <= len(text) and text[pos:pos + length] == phrase:
                repeat_count += 1
                pos += length
            if repeat_count >= 3:
                # Keep phrase once, remove the rest
                text = text[:i + length] + text[pos:]
                break
    return text.strip()


def _map_text_to_deepgram_timeline(gemini_segments, dg_segments, duration):
    """Normalize Gemini output: parse time strings to float + assign speakers from Deepgram.

    Gemini segments come back with string times ("MM:SS") and sometimes without speakers.
    This converts them to the flat dict format the DB expects (start/end as floats, speaker string).
    """
    # Ensure speakers assigned (idempotent — if already assigned from chunked path, no-op)
    gemini_segments = _assign_speakers_from_timeline(gemini_segments, dg_segments)

    result = []
    for seg in gemini_segments:
        text = (seg.get("text") or "").strip()
        if not text:
            continue
        start = _parse_time(str(seg.get("start", "0:0")))
        end = _parse_time(str(seg.get("end", "0:0")))
        if end <= start:
            end = start + 0.5
        end = min(end, duration)
        speaker = seg.get("speaker") or "Speaker 1"
        result.append({
            "start": float(start),
            "end": float(end),
            "speaker": speaker,
            "text": text,
        })
    return result


def _assign_speakers_from_timeline(gemini_segments, dg_segments):
    """Override Gemini speaker assignments with Deepgram timeline speakers."""
    for seg in gemini_segments:
        start = _parse_time(str(seg.get("start", "0:0")))
        mid = start + (_parse_time(str(seg.get("end", "0:0"))) - start) / 2

        # Find best matching Deepgram segment by midpoint
        best = None
        best_overlap = 0
        for dg in dg_segments:
            if dg.get("is_gap"):
                continue
            if dg["start"] <= mid <= dg["end"]:
                best = dg
                break
            # Fallback: closest segment
            overlap = min(dg["end"], _parse_time(str(seg.get("end", "0:0")))) - max(dg["start"], start)
            if overlap > best_overlap:
                best_overlap = overlap
                best = dg

        if best:
            seg["speaker"] = f"Speaker {best['speaker'] + 1}"

    return gemini_segments


def _parse_time(time_str):
    """Parse MM:SS.ss to seconds."""
    try:
        parts = time_str.split(":")
        return int(parts[0]) * 60 + float(parts[1])
    except Exception:
        return 0.0


ANALYSIS_PROMPT = """จากบทถอดความการประชุมต่อไปนี้ ให้วิเคราะห์และสรุปเป็น JSON:
วันที่ประชุม: {meeting_date}

{transcript}

ตอบเป็น JSON เท่านั้น ห้ามมีข้อความอื่น:
{{
  "title": "ชื่อการประชุมสั้นๆ ภาษาไทยเท่านั้น เช่น สรุปความคืบหน้าโปรเจกต์ AI",
  "summary_short": "สรุป 1-2 ประโยคสั้นๆ ว่าประชุมเรื่องอะไร",
  "mom": "### สรุปภาพรวม\\nสรุปใจความสำคัญและวัตถุประสงค์ของการประชุม 2-3 ประโยค\\n\\n### ประเด็นที่พูดคุย\\n- **หัวข้อ 1**\\n  - รายละเอียดข้อ 1\\n  - รายละเอียดข้อ 2\\n- **หัวข้อ 2**\\n  - รายละเอียดข้อ 1\\n\\n### มติที่ประชุม\\n- ข้อสรุป 1\\n- ข้อสรุป 2\\n\\n### สิ่งที่ต้องทำ\\n\\n| ลำดับ | รายละเอียด | กำหนดการ | ผู้รับผิดชอบ |\\n|------|-----------|---------|------------|\\n| 1 | งาน 1 | TBC | ชื่อ |\\n| 2 | งาน 2 | TBC | ชื่อ |",
  "sentiment": "positive|neutral|negative|mixed",
  "meeting_tone": "โทนการประชุมสั้นๆ 2-3 คำ",
  "meeting_type": "ประเภทการประชุม เช่น Sprint Planning, Brainstorm, Status Update",
  "topics": ["หัวข้อ 1", "หัวข้อ 2"],
  "action_items": [
    {{"task": "สิ่งที่ต้องทำ", "owner": "ชื่อผู้รับผิดชอบ", "deadline": "กำหนดส่ง หรือไม่ระบุให้เว้นว่าง"}}
  ],
  "key_decisions": ["การตัดสินใจ 1", "การตัดสินใจ 2"],
  "open_questions": ["คำถามที่ยังค้าง 1"],
  "audio_quality": 85,
  "speaker_suggestions": [
    {{"speaker": "Speaker 1", "suggested_name": "ชื่อที่เดา", "reason": "เหตุผลสั้นๆ"}}
  ]
}}

กฎเหล็ก:
- ห้ามเพิ่มข้อมูลที่ไม่มีใน transcript เด็ดขาด ห้ามเดา ห้ามแต่งเติม ถ้าไม่มีพูดถึงก็ห้ามใส่
- ห้ามใส่ชื่อเครื่องมือ แพลตฟอร์ม หรือคำใดๆ ที่ไม่ปรากฏใน transcript เช่น ถ้าไม่มีใครพูดว่า "Jira" ห้ามเขียน "Jira"
- สิ่งที่ต้องทำ: ต้องเป็นงานจริงๆ ที่มีคนพูดมอบหมายใน transcript เท่านั้น ห้ามใส่สิ่งทั่วไปที่ไม่ใช่งาน เช่น "ปิดการประชุม" "เตรียมตัววันหยุด" "ติดตามความคืบหน้า" รายละเอียดต้องชัดเจนว่าทำอะไร ทำไป เพื่ออะไร เช่น แทน "รัน ALPR" ให้เขียน "รัน ALPR บน Server ใหม่เพื่อทดสอบ Performance กับกล้อง AOT" แทน "ไปคุยกับพี่ต้น" ให้เขียน "หารือกับพี่ต้นเรื่องแผนการจัดสรร Server Resource สำหรับโปรเจกต์ AI"
- ตอบภาษาไทย คำศัพท์เทคนิค/ภาษาอังกฤษให้เขียนเป็นอังกฤษตรงๆ ห้ามแปลงเป็นภาษาไทยแบบทับศัพท์ เช่น ใช้ "crack" ไม่ใช่ "แคร็ก", ใช้ "execute" ไม่ใช่ "เอ็กซิคิวท์"
- mom เป็น Markdown ต้องมี 4 section ตามลำดับ: "สรุปภาพรวม" (2-3 ประโยค), "ประเด็นที่พูดคุย", "มติที่ประชุม", "สิ่งที่ต้องทำ" ห้ามข้าม section ใดทั้งสิ้น
- ประเด็นที่พูดคุย: สรุปเป็นหัวข้อใหญ่ แต่ละหัวข้อมี bullet ย่อย แต่ละ bullet เขียน 1-2 ประโยคกระชับตรงประเด็น บอกข้อเท็จจริงและรายละเอียดสำคัญ ถ้ารวมกลุ่มได้ให้รวม ไม่สำคัญให้ตัดออก ห้ามใส่ชื่อบุคคลใดทั้งสิ้น ใช้ "ทีม" หรือ "ที่ประชุม" แทน
  สำคัญมาก: ห้ามขึ้นต้นประโยคด้วยคำต่อไปนี้เด็ดขาด: "มีการ" "มีความ" "มีปัญหา" "มีข้อเสนอ" "มีการ์ด" "มีความท้า" ถ้าเจอตัวเองกำลังจะเขียน "มี..." ให้หยุดแล้วเขียนใหม่
  ตัวอย่างที่ผิด → ถูก:
  ผิด: "มีการพัฒนา Search Agent" → ถูก: "Search Agent ค้นหาข้อมูลจากเว็บภายนอกได้ โดยใช้ Tavily"
  ผิด: "มีปัญหาเรื่อง Server" → ถูก: "Server Resource ไม่เพียงพอสำหรับการทดสอบโมเดล AI"
  ผิด: "มีความกังวลเรื่อง Security" → ถูก: "ยังไม่มีมาตรการป้องกันการ Execute Script จาก User Input"
  ผิด: "มีข้อเสนอให้ทำงานแบบ Cross-functional" → ถูก: "เสนอให้จัดคู่ Buddy สำหรับงานระยะยาว เพื่อลดความเสี่ยงเมื่อมีคนลา"
- มติที่ประชุม: เขียนเป็นข้อสรุปที่ตัดสินใจแล้ว ห้ามใส่ชื่อบุคคลใดทั้งสิ้น
  ห้ามขึ้นต้นด้วย: "ทีมจะ" "จะมีการ" "จะดำเนินการ"
  ตัวอย่างที่ผิด → ถูก:
  ผิด: "ทีมจะดำเนินการพัฒนา X" → ถูก: "ดำเนินการพัฒนา X ต่อ โดยเน้นเรื่อง..."
  ผิด: "จะมีการหารือกับ Y" → ถูก: "รอผลหารือเรื่อง Z ก่อนตัดสินใจ"
  ผิด: "กำหนด Owner ให้เป็นพัด" → ถูก: "กำหนด Owner ของโปรเจกต์เรียบร้อยแล้ว"
- สิ่งที่ต้องทำ: เป็น Markdown table มี 4 คอลัมน์: ลำดับ, รายละเอียด, กำหนดการ, ผู้รับผิดชอบ ผู้รับผิดชอบต้องเป็นชื่อ Speaker ตามที่ปรากฏก่อน : ใน transcript เท่านั้น (เช่น Speaker 1, Speaker 2) ห้ามใช้คำกว้างๆ เช่น "ทีมพัฒนา" "ทีม" "ที่ประชุม" กำหนดการต้องเป็นวันที่จริง (เช่น 04/04/2026) คำนวณจากวันที่ประชุมที่ให้ไว้ ห้ามใช้คำว่า "สัปดาห์นี้" "จันทร์หน้า" ถ้าไม่ระบุให้ใส่ TBC
- ถ้าไม่มีข้อมูลในหัวข้อใดให้เขียน "ไม่มี" ห้ามเดา
- sentiment เลือก 1 จาก: positive, neutral, negative, mixed
- topics, action_items, key_decisions, open_questions เป็น array ถ้าไม่มีให้ใส่ []
- title สั้นกระชับ ไม่เกิน 50 ตัวอักษร ภาษาไทยเท่านั้น ห้ามใช้ภาษาอังกฤษในหัวข้อ
- ใช้ชื่อผู้พูดตามที่ปรากฏก่อน : ใน transcript เท่านั้น (อาจเป็น Speaker 1 หรือชื่อจริง เช่น แอ้, กอล์ฟ) ห้ามเดาหรือเปลี่ยนชื่อเอง ห้ามใส่ชื่อในวงเล็บ
- speaker_suggestions: เดาชื่อจริงของแต่ละ Speaker จากบริบทในบทสนทนา เช่น ถูกเรียกชื่อ, แนะนำตัว, คนอื่นพูดถึง ถ้าเดาไม่ได้ให้ใส่ array ว่าง
- audio_quality เป็นคะแนน 0-100 ประเมินจากคุณภาพของบทถอดความ: เสียงชัด ถอดได้ครบ = 90-100, มีบางช่วงไม่ชัด = 70-89, ถอดยาก = ต่ำกว่า 70"""


def generate_analysis(transcript_text, custom_instructions=None, meeting_date=None):
    """Generate MoM + sentiment + meeting type in one call."""
    if not meeting_date:
        from datetime import datetime, timezone, timedelta
        meeting_date = datetime.now(timezone(timedelta(hours=7))).strftime("%d/%m/%Y")
    prompt = ANALYSIS_PROMPT.format(transcript=transcript_text, meeting_date=meeting_date)
    if custom_instructions:
        prompt += f"\n\nคำสั่งเพิ่มเติมสำหรับการสรุป:\n{custom_instructions}"
    payload = json.dumps({
        "model": "google/gemini-2.5-flash",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 8000,
        "temperature": 0,
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {settings.OPEN_ROUNTER}",
            "Content-Type": "application/json",
        },
    )

    with urllib.request.urlopen(req, timeout=120) as resp:
        result = json.loads(resp.read().decode("utf-8"))

    raw = result["choices"][0]["message"]["content"].strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1])
    raw = re.sub(r'[\x00-\x1f\x7f]', lambda m: '' if m.group() not in '\n\r\t' else m.group(), raw)

    try:
        return json.loads(raw, strict=False)
    except json.JSONDecodeError as e:
        logger.warning("Analysis JSON parse error: %s, attempting fix...", e)
        # Try to fix by escaping unescaped quotes in string values
        # Replace "text with "quotes" inside" → "text with \"quotes\" inside"
        fixed = raw
        for pattern in [r'"select all"', r'"ติ๊กเลือกทั้งหมด"']:
            fixed = fixed.replace(pattern, pattern.replace('"', "'"))
        # Generic: replace inner quotes between key-value pairs
        fixed = re.sub(r'(?<=[^\\])"(?=[^:,\[\]{}\n])', "'", fixed)
        try:
            return json.loads(fixed, strict=False)
        except json.JSONDecodeError:
            # Last resort: ask Gemini to re-generate with stricter JSON
            logger.warning("JSON fix failed, retrying generation...")
            try:
                payload2 = json.dumps({
                    "model": "google/gemini-2.5-flash",
                    "messages": [{"role": "user", "content": prompt + "\n\nสำคัญมาก: ตอบเป็น valid JSON เท่านั้น ห้ามใส่ double quote ในข้อความ ใช้ single quote แทน"}],
                    "max_tokens": 8000,
                    "temperature": 0,
                }).encode("utf-8")
                req2 = urllib.request.Request(
                    "https://openrouter.ai/api/v1/chat/completions",
                    data=payload2,
                    headers={"Authorization": f"Bearer {settings.OPEN_ROUNTER}", "Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req2, timeout=120) as resp2:
                    result2 = json.loads(resp2.read().decode("utf-8"))
                raw2 = result2["choices"][0]["message"]["content"].strip()
                if raw2.startswith("```"):
                    raw2 = "\n".join(raw2.split("\n")[1:-1])
                raw2 = re.sub(r'[\x00-\x1f\x7f]', lambda m: '' if m.group() not in '\n\r\t' else m.group(), raw2)
                return json.loads(raw2, strict=False)
            except Exception:
                logger.warning("Analysis generation retry also failed")
                return {}


def _fix_mom_style(mom_text):
    """Post-process MoM to fix common Gemini writing issues."""
    # Fix "มีการ/มีความ/มีปัญหา/มีข้อเสนอ" at start of bullet points
    prefixes = [
        ('มีการหารือเรื่อง', ''),
        ('มีการหารือถึง', ''),
        ('มีการหารือ', ''),
        ('มีการพูดถึง', ''),
        ('มีการพัฒนา', 'พัฒนา'),
        ('มีการนำเสนอ', 'นำเสนอ'),
        ('มีการเสนอ', 'เสนอ'),
        ('มีการใช้', 'ใช้'),
        ('มีการ์ดเรล', 'การ์ดเรล'),
        ('มีการ', ''),
        ('มีความกังวลเรื่อง', ''),
        ('มีความกังวลเกี่ยวกับ', ''),
        ('มีความท้าทายในเรื่อง', ''),
        ('มีความท้าทาย', ''),
        ('มีความต้องการ', 'ต้องการ'),
        ('มีความสามารถ', 'สามารถ'),
        ('มีความจำเป็น', 'จำเป็น'),
        ('มีความ', ''),
        ('มีปัญหาเรื่อง', ''),
        ('มีปัญหา', ''),
        ('มีข้อเสนอให้', 'เสนอให้'),
        ('มีข้อเสนอ', 'เสนอ'),
        ('มีประเด็นเรื่อง', ''),
        ('มีงาน', 'งาน'),
    ]

    lines = mom_text.split('\n')
    result = []
    in_todo = False
    for line in lines:
        if '### สิ่งที่ต้องทำ' in line:
            in_todo = True
        elif line.startswith('### '):
            in_todo = False

        if not in_todo and (line.strip().startswith('- ') or line.strip().startswith('  - ')):
            indent = len(line) - len(line.lstrip())
            bullet = line.lstrip()
            if bullet.startswith('  - '):
                prefix_part = '  - '
                content = bullet[4:]
            else:
                prefix_part = '- '
                content = bullet[2:]

            for old, new in prefixes:
                if content.startswith(old):
                    content = new + content[len(old):]
                    # Capitalize first char if Thai
                    break

            line = ' ' * indent + prefix_part + content

        # Fix "ทีมจะ/จะมีการ" in มติ
        if not in_todo and (line.strip().startswith('- ') or line.strip().startswith('  - ')):
            for pattern in ['ทีมจะดำเนินการ', 'ทีมจะพิจารณา', 'ทีมจะ', 'จะมีการ', 'จะดำเนินการ']:
                indent2 = len(line) - len(line.lstrip())
                stripped = line.lstrip()
                if stripped.startswith('- ') and stripped[2:].startswith(pattern):
                    line = ' ' * indent2 + '- ' + stripped[2 + len(pattern):]

        result.append(line)

    return '\n'.join(result)


def _strip_names_from_mom(mom_text, speaker_names=None):
    """Remove person names from ประเด็นที่พูดคุย and มติที่ประชุม sections.
    Only สิ่งที่ต้องทำ is allowed to have names."""
    import re
    if not speaker_names:
        return mom_text

    # Also strip common Thai name patterns (พี่xxx)
    extra_names = set()
    for match in re.finditer(r'พี่\w+', mom_text):
        extra_names.add(match.group())

    all_names = list(speaker_names) + list(extra_names)

    lines = mom_text.split('\n')
    result = []
    in_protected = False
    for line in lines:
        if '### สิ่งที่ต้องทำ' in line:
            in_protected = True
        elif line.startswith('### '):
            in_protected = False
        if not in_protected:
            leading = len(line) - len(line.lstrip())
            prefix = line[:leading]
            content = line[leading:]
            content = re.sub(r'\s*\([^)]*\)', '', content)
            for name in all_names:
                content = content.replace(name, '')
            # Clean up artifacts: "ให้เป็น " "กับ เรื่อง" etc
            content = re.sub(r'ให้เป็น\s*$', '', content)
            content = re.sub(r'กับ\s+เรื่อง', 'เรื่อง', content)
            content = re.sub(r'หารือกับ\s+เรื่อง', 'หารือเรื่อง', content)
            content = re.sub(r'\s{2,}', ' ', content).strip()
            line = prefix + content
        result.append(line)
    return '\n'.join(line for line in result if line.strip() or line == '')


def generate_mom(transcript_text, custom_instructions=None, speaker_names=None):
    """Generate MoM only (for regeneration)."""
    analysis = generate_analysis(transcript_text, custom_instructions)
    return _strip_names_from_mom(analysis.get("mom", ""), speaker_names)


# === Spectral Clustering Pipeline ===

_THAI_CANT_START = set('ิีึืุู็่้๊๋์ํฺั')


def _spectral_diarize(audio_path, utterances, n_clusters=4):
    """Extract speaker embeddings per utterance, cluster with Spectral."""
    import numpy as np
    import torchaudio
    import torch
    from speechbrain.inference.speaker import EncoderClassifier
    from sklearn.metrics.pairwise import cosine_similarity
    from sklearn.cluster import SpectralClustering

    wav_path = audio_path + ".spectral.wav"
    subprocess.run(["ffmpeg", "-y", "-i", audio_path, "-ar", "16000", "-ac", "1", wav_path],
                   capture_output=True, check=True)

    classifier = EncoderClassifier.from_hparams(
        source="speechbrain/spkrec-ecapa-voxceleb",
        run_opts={"device": "cuda"},
    )
    waveform, sr = torchaudio.load(wav_path)
    os.remove(wav_path)

    embeddings = []
    valid_utts = []
    for u in utterances:
        s = int(u["start"] * sr)
        e = int(u["end"] * sr)
        seg = waveform[:, s:e]
        if seg.shape[1] < sr * 0.5:
            continue
        with torch.no_grad():
            emb = classifier.encode_batch(seg.to("cuda"))
            embeddings.append(emb.squeeze().cpu().numpy())
            valid_utts.append(u)

    emb_array = np.array(embeddings)
    sim_matrix = np.clip(cosine_similarity(emb_array), 0, 1)

    sc = SpectralClustering(n_clusters=n_clusters, affinity="precomputed", random_state=42)
    labels = sc.fit_predict(sim_matrix)

    # Build segments with speaker labels
    segments = []
    seen = {}
    idx = 0
    for u, label in zip(valid_utts, labels):
        if int(label) not in seen:
            seen[int(label)] = idx
            idx += 1
        segments.append({
            "start": u["start"],
            "end": u["end"],
            "speaker": f"Speaker {seen[int(label)] + 1}",
            "text": u.get("transcript", ""),
        })

    # Merge consecutive same-speaker (gap < 5s)
    merged = [dict(segments[0])]
    for seg in segments[1:]:
        if seg["speaker"] == merged[-1]["speaker"] and seg["start"] - merged[-1]["end"] < 5.0:
            merged[-1]["end"] = seg["end"]
            merged[-1]["text"] += " " + seg["text"]
        else:
            merged.append(dict(seg))

    # Clean Thai spacing in Deepgram text
    for seg in merged:
        seg["text"] = re.sub(r'(?<=[\u0E00-\u0E7F])\s+(?=[\u0E00-\u0E7F])', '', seg["text"])

    return merged


def _gemini_audio_correct(audio_path, segments, chunk_sec=180):
    """Send audio + Deepgram text to Gemini for correction in chunks."""
    compressed = _compress_audio(audio_path)
    total_usage = {"prompt_tokens": 0, "completion_tokens": 0}

    # Build chunks
    chunks = []
    current = {"start": segments[0]["start"], "segments": []}
    for seg in segments:
        current["segments"].append(seg)
        if seg["end"] - current["start"] >= chunk_sec:
            current["end"] = seg["end"]
            chunks.append(current)
            current = {"start": seg["end"], "segments": []}
    if current["segments"]:
        current["end"] = current["segments"][-1]["end"]
        chunks.append(current)

    all_segments = []
    for chunk in chunks:
        chunk_file = compressed + f".corr_{int(chunk['start'])}.mp3"
        subprocess.run([
            "ffmpeg", "-y", "-i", compressed,
            "-ss", str(chunk["start"]), "-to", str(chunk["end"]),
            "-ar", "16000", "-ac", "1", "-b:a", "64k", chunk_file,
        ], capture_output=True, check=True)

        with open(chunk_file, "rb") as f:
            audio_b64 = base64.b64encode(f.read()).decode()
        os.remove(chunk_file)

        offset = chunk["start"]
        seg_lines = []
        for i, seg in enumerate(chunk["segments"]):
            seg_lines.append(f'{i}|{_fmt(seg["start"] - offset)}-{_fmt(seg["end"] - offset)}|{seg["text"]}')

        prompt = f"""ฟังไฟล์เสียงนี้แล้วแก้ไขข้อความถอดเสียงด้านล่างให้ถูกต้อง

ข้อความถอดเสียง (อาจมีคำผิด):
{chr(10).join(seg_lines)}

กฎ:
- ฟังเสียงจริงแล้วแก้คำผิดให้ตรงกับที่พูด
- รักษาโครงสร้าง segment เดิม ห้ามรวม ห้ามแยก ห้ามเพิ่ม segment
- คำอังกฤษเขียนเป็นอังกฤษ เช่น Agent, Search, API, AD
- ภาษาไทยเขียนติดกัน เว้นวรรคเฉพาะรอบคำอังกฤษ
- ถ้า segment ไหนถูกอยู่แล้วให้คงเดิม

ตอบเป็น JSON array เท่านั้น:
[{{"id": 0, "text": "ข้อความที่แก้แล้ว"}}, {{"id": 1, "text": "ข้อความ"}}]"""

        content = [
            {"type": "text", "text": prompt},
            {"type": "input_audio", "input_audio": {"data": audio_b64, "format": "mp3"}},
        ]

        payload = json.dumps({
            "model": "google/gemini-2.5-flash",
            "messages": [{"role": "user", "content": content}],
            "max_tokens": 16000,
            "temperature": 0,
        }).encode("utf-8")

        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/chat/completions",
            data=payload,
            headers={
                "Authorization": f"Bearer {settings.OPEN_ROUNTER}",
                "Content-Type": "application/json",
            },
        )

        texts = {}
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                result = json.loads(resp.read().decode("utf-8"))
            raw = result["choices"][0]["message"]["content"].strip()
            usage = result.get("usage", {})
            total_usage["prompt_tokens"] += usage.get("prompt_tokens", 0)
            total_usage["completion_tokens"] += usage.get("completion_tokens", 0)

            if raw.startswith("```"):
                raw = "\n".join(raw.split("\n")[1:-1])
            raw = re.sub(r'[\x00-\x1f\x7f]', lambda m: '' if m.group() not in '\n\r\t' else m.group(), raw)
            items = json.loads(raw, strict=False)
            for item in items:
                idx = item.get("id", -1)
                text = item.get("text", "")
                text = re.sub(r'(?<=[\u0E00-\u0E7F])\s+(?=[\u0E00-\u0E7F])', '', text)
                texts[idx] = text
        except Exception as e:
            logger.warning("Gemini audio-correct failed for chunk %.0f-%.0f: %s", chunk["start"], chunk["end"], e)

        for i, seg in enumerate(chunk["segments"]):
            all_segments.append({
                "start": seg["start"],
                "end": seg["end"],
                "speaker": seg["speaker"],
                "text": texts.get(i, seg["text"]),
            })

    os.remove(compressed)
    return all_segments, total_usage


def _fix_thai_splits(segments):
    """Merge segments where Thai word was split across boundary, then merge short same-speaker."""
    if not segments:
        return segments

    # Pass 1: Fix split Thai words
    merged = [dict(segments[0])]
    for seg in segments[1:]:
        text = seg["text"].lstrip()
        if text and text[0] in _THAI_CANT_START:
            merged[-1]["end"] = seg["end"]
            merged[-1]["text"] += seg["text"]
        else:
            merged.append(dict(seg))

    # Pass 2: Merge consecutive same-speaker (gap < 5s)
    pass2 = [dict(merged[0])]
    for seg in merged[1:]:
        if seg["speaker"] == pass2[-1]["speaker"] and seg["start"] - pass2[-1]["end"] < 5.0:
            pass2[-1]["end"] = seg["end"]
            pass2[-1]["text"] += " " + seg["text"]
        else:
            pass2.append(dict(seg))

    # Pass 3: Absorb short segments (< 3s) into previous same-speaker
    final = [dict(pass2[0])]
    for seg in pass2[1:]:
        dur = seg["end"] - seg["start"]
        if dur < 3.0 and seg["speaker"] == final[-1]["speaker"]:
            final[-1]["end"] = seg["end"]
            final[-1]["text"] += " " + seg["text"]
        else:
            final.append(dict(seg))

    return final


def _check_deepgram_diarization_quality(utterances):
    """Decide whether Deepgram's built-in diarization is good enough.

    Returns (is_good, num_speakers, max_pct, reason).
    Poor diarization = 1 speaker total, or one speaker dominates >85% of speech time.
    """
    if not utterances:
        return False, 0, 1.0, "no utterances"

    durs = {}
    for u in utterances:
        sp = u.get("speaker", 0)
        durs[sp] = durs.get(sp, 0) + (u["end"] - u["start"])

    num_speakers = len(durs)
    total = sum(durs.values()) or 1
    max_pct = max(durs.values()) / total

    if num_speakers < 2:
        return False, num_speakers, max_pct, f"only {num_speakers} speaker"
    if max_pct > 0.85:
        return False, num_speakers, max_pct, f"one speaker dominates {max_pct*100:.0f}%"
    return True, num_speakers, max_pct, f"{num_speakers} speakers, max {max_pct*100:.0f}%"


def _build_segments_from_deepgram(utterances):
    """Build diarized segments using Deepgram's built-in speaker labels."""
    segments = []
    for u in utterances:
        sp = u.get("speaker", 0)
        segments.append({
            "start": u["start"],
            "end": u["end"],
            "speaker": f"Speaker {sp + 1}",
            "text": u.get("transcript", ""),
        })

    # Merge consecutive same-speaker (gap < 5s) — same rule as spectral pipeline
    if not segments:
        return []
    merged = [dict(segments[0])]
    for seg in segments[1:]:
        if seg["speaker"] == merged[-1]["speaker"] and seg["start"] - merged[-1]["end"] < 5.0:
            merged[-1]["end"] = seg["end"]
            merged[-1]["text"] += " " + seg["text"]
        else:
            merged.append(dict(seg))

    # Clean Thai word splits
    for seg in merged:
        seg["text"] = re.sub(r"(?<=[\u0E00-\u0E7F])\s+(?=[\u0E00-\u0E7F])", "", seg["text"])
    return merged


def _process_spectral(db, t, file_path, transcription_id, start_time, mode="spectral"):
    """Diarization pipeline: Deepgram + (Deepgram-speakers | Spectral) + Gemini audio-correct.

    mode="spectral" — always re-cluster with spectral (useful when you know Deepgram can't
                      diarize mono-mixed single-mic recordings).
    mode="smart"    — use Deepgram's diarization if it looks good, fall back to spectral
                      only when Deepgram collapses everyone into one speaker.
    """
    import httpx

    # Get duration
    probe = subprocess.run([
        "ffprobe", "-v", "quiet", "-show_entries", "format=duration",
        "-of", "csv=p=0", file_path,
    ], capture_output=True, text=True)
    duration = float(probe.stdout.strip())

    # Step 1: Deepgram utterances (10-30%)
    with ProgressTicker(db, t, 10, 30, "Deepgram กำลังถอดเสียง...", interval=3):
        re_encoded = file_path + ".re.m4a"
        subprocess.run([
            "ffmpeg", "-y", "-i", file_path,
            "-ar", "16000", "-ac", "1", "-b:a", "64k", re_encoded,
        ], capture_output=True, check=True)

        with open(re_encoded, "rb") as f:
            audio = f.read()

        response = httpx.post(
            "https://api.deepgram.com/v1/listen",
            params={"model": "nova-3", "language": "th", "diarize": "true", "utterances": "true", "smart_format": "true"},
            headers={"Authorization": f"Token {settings.DEEPGRAM_API_KEY}", "Content-Type": "audio/mp4"},
            content=audio, timeout=300,
        )
        response.raise_for_status()
        dg_result = response.json()
        os.remove(re_encoded)

    utterances = dg_result.get("results", {}).get("utterances", [])
    if not utterances:
        raise RuntimeError("Deepgram returned no utterances")

    logger.info("#%d Deepgram: %d utterances", transcription_id, len(utterances))

    # Step 2: Choose diarization method (30-50%)
    use_spectral = True
    if mode == "smart":
        is_good, n_sp, max_pct, reason = _check_deepgram_diarization_quality(utterances)
        logger.info("#%d Smart quality check: %s (good=%s)", transcription_id, reason, is_good)
        use_spectral = not is_good

    if use_spectral:
        with ProgressTicker(db, t, 30, 50, "กำลังแยกผู้พูด (Spectral Clustering)...", interval=3):
            segments = _spectral_diarize(file_path, utterances, n_clusters=4)
        logger.info("#%d Spectral: %d segments, %d speakers",
                    transcription_id, len(segments), len(set(s["speaker"] for s in segments)))
    else:
        t.progress_percent = 50
        t.status_message = "ใช้ผู้พูดจาก Deepgram diarization..."
        db.commit()
        segments = _build_segments_from_deepgram(utterances)
        logger.info("#%d Deepgram-speakers: %d segments, %d speakers",
                    transcription_id, len(segments), len(set(s["speaker"] for s in segments)))

    num_speakers = len(set(seg["speaker"] for seg in segments))

    # Step 3: Gemini audio-correct (50-85%)
    with ProgressTicker(db, t, 50, 85, "Gemini กำลังแก้ไขข้อความ...", interval=5):
        corrected, gemini_usage = _gemini_audio_correct(file_path, segments)

    # Step 4: Fix Thai splits + apply corrections
    final_segs = _fix_thai_splits(corrected)

    from app.models.transcription import CorrectionDict
    corrections = db.query(CorrectionDict).all()
    if corrections:
        for seg in final_segs:
            for c in corrections:
                seg["text"] = seg["text"].replace(c.wrong, c.correct)

    # Save segments
    all_text = []
    for i, seg in enumerate(final_segs):
        db.add(TranscriptionSegment(
            transcription_id=transcription_id,
            segment_index=i,
            start_time=seg["start"],
            end_time=seg["end"],
            text=seg["text"],
            speaker=seg["speaker"],
        ))
        all_text.append(seg["text"])

    t.progress_percent = 85
    t.status_message = "กำลังบันทึก..."
    db.commit()

    # Step 4.5: Auto-match speakers against stored voiceprints
    try:
        from voiceprint_service import identify_speakers, get_speaker_suggestions
        # Build dg_segments format for voiceprint matching
        dg_segs_for_vp = [{"start": s["start"], "end": s["end"], "speaker": i, "is_gap": False}
                          for i, s in enumerate(final_segs)]
        vp_suggestions = get_speaker_suggestions(file_path, dg_segs_for_vp)
        t.voiceprint_suggestions = json.dumps(vp_suggestions, ensure_ascii=False)
        logger.info("#%d Voiceprint suggestions: %s", transcription_id, vp_suggestions)

        vp_mapping = identify_speakers(file_path, dg_segs_for_vp)
        if vp_mapping:
            # Rename speakers in segments
            for seg_obj in db.query(TranscriptionSegment).filter(
                TranscriptionSegment.transcription_id == transcription_id
            ).all():
                for old_spk, new_name in vp_mapping.items():
                    old_label = f"Speaker {old_spk + 1}" if isinstance(old_spk, int) else old_spk
                    if seg_obj.speaker == old_label:
                        seg_obj.speaker = new_name
            db.commit()
            logger.info("#%d Voiceprint matched: %s", transcription_id, vp_mapping)
    except Exception as e:
        logger.warning("#%d Voiceprint matching failed: %s", transcription_id, e)

    # Step 5: Generate analysis
    t.progress_percent = 90
    t.status_message = "กำลังวิเคราะห์การประชุม..."
    db.commit()

    transcript_for_analysis = "\n".join(f"{seg['speaker']}: {seg['text']}" for seg in final_segs)
    try:
        custom_instructions = None
        if t.group_id:
            from app.models.transcription import TranscriptionGroup
            group = db.query(TranscriptionGroup).filter(TranscriptionGroup.id == t.group_id).first()
            if group and group.custom_instructions:
                custom_instructions = group.custom_instructions

        analysis = generate_analysis(transcript_for_analysis, custom_instructions, meeting_date=t.created_at.strftime("%d/%m/%Y"))
        _speaker_names = list(set(seg["speaker"] for seg in final_segs))
        mom = analysis.get("mom", "")
        mom = _fix_mom_style(mom)
        mom = _strip_names_from_mom(mom, _speaker_names)
        t.summary = mom
        t.sentiment = analysis.get("sentiment", "")
        t.meeting_tone = analysis.get("meeting_tone", "")
        t.meeting_type = analysis.get("meeting_type", "")
        t.auto_title = analysis.get("title", "")
        t.summary_short = analysis.get("summary_short", "")
        t.topics = json.dumps(analysis.get("topics", []), ensure_ascii=False)
        t.action_items = json.dumps(analysis.get("action_items", []), ensure_ascii=False)
        t.key_decisions = json.dumps(analysis.get("key_decisions", []), ensure_ascii=False)
        t.open_questions = json.dumps(analysis.get("open_questions", []), ensure_ascii=False)
        t.speaker_suggestions = json.dumps(analysis.get("speaker_suggestions", []), ensure_ascii=False)
        t.deepgram_confidence = round(analysis.get("audio_quality", 0) / 100, 4)
    except Exception as e:
        logger.warning("#%d Analysis failed: %s", transcription_id, e)

    elapsed = time.time() - start_time

    # Build mom_full
    speakers_list = list(dict.fromkeys(seg["speaker"] for seg in final_segs))
    mom_meta = f"### ข้อมูลการประชุม\n"
    mom_meta += f"- **หัวข้อ:** {t.auto_title or t.audio_file.original_filename}\n"
    mom_meta += f"- **วันที่:** {t.created_at.strftime('%d/%m/%Y %H:%M')}\n"
    mom_meta += f"- **ความยาว:** {int(duration // 60)} นาที {int(duration % 60)} วินาที\n"
    mom_meta += f"- **ผู้เข้าร่วม:** {', '.join(speakers_list)}\n"
    t.mom_full = mom_meta + "\n" + (t.summary or "")

    t.full_text = " ".join(all_text).strip()
    t.detected_language = "th"
    t.status = TranscriptionStatus.completed
    t.progress_percent = 100
    t.status_message = f"เสร็จสิ้น ({elapsed:.0f}s)"
    t.processing_time_seconds = elapsed
    t.audio_file.status = AudioStatus.completed

    # Cost tracking
    t.gemini_input_tokens = gemini_usage.get("prompt_tokens", 0)
    t.gemini_output_tokens = gemini_usage.get("completion_tokens", 0)
    gemini_cost = (t.gemini_input_tokens * 0.15 + t.gemini_output_tokens * 0.6) / 1_000_000
    t.gemini_cost_usd = round(gemini_cost, 6)
    # Deepgram cost: $0.0043/min (nova-3)
    t.deepgram_cost_usd = round((duration / 60) * 0.0043, 6)
    t.total_cost_usd = round(t.deepgram_cost_usd + t.gemini_cost_usd, 6)

    db.commit()
    logger.info("#%d Spectral done! %d segments, %d speakers, %.0fs, cost=$%.4f", transcription_id, len(final_segs), len(speakers_list), elapsed, t.total_cost_usd)


# === Main Process ===

def _process_gemini_single(db, t, file_path, transcription_id, start_time):
    """Gemini single-call: diarize + transcribe in one API call per chunk."""
    import subprocess as _sp

    # Get duration
    probe = _sp.run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", file_path], capture_output=True, text=True)
    duration = float(probe.stdout.strip())

    # Compress audio
    compressed = _compress_audio(file_path)

    # Load voice samples for speaker identification
    voice_samples = _load_voice_samples()
    speaker_hint = ""
    if voice_samples:
        names = ", ".join(s["name"] for s in voice_samples)
        speaker_hint = f"\nผู้พูดที่รู้จัก: {names}"

    # Chunk into 5-min pieces
    chunk_dur = 300
    all_segments = []
    total_usage = {"prompt_tokens": 0, "completion_tokens": 0}
    chunk_idx = 0

    chunk_start = 0
    while chunk_start < duration:
        chunk_end = min(chunk_start + chunk_dur, duration)
        chunk_file = compressed + f".sc{chunk_idx}.mp3"
        _sp.run([
            "ffmpeg", "-y", "-i", compressed,
            "-ss", str(chunk_start), "-t", str(chunk_end - chunk_start),
            "-ar", "16000", "-ac", "1", "-b:a", "64k", chunk_file,
        ], capture_output=True, check=True)

        with open(chunk_file, "rb") as f:
            chunk_b64 = base64.b64encode(f.read()).decode()

        chunk_start_fmt = f"{int(chunk_start)//60}:{int(chunk_start)%60:02d}"
        chunk_end_fmt = f"{int(chunk_end)//60}:{int(chunk_end)%60:02d}"

        prompt = f"""ถอดเสียงภาษาไทยจากไฟล์เสียงนี้ ให้ละเอียดทุกคำ พร้อมระบุผู้พูด
มีคนพูดหลายคนในเสียงนี้ ให้แยกว่าใครพูดช่วงไหน{speaker_hint}
ถ้าจับคู่ชื่อไม่ได้ให้ใช้ Speaker 1, Speaker 2, ...

กฎสำคัญ:
1. รวมคำพูดต่อเนื่องของคนเดียวกันเป็น segment เดียว ตัด segment ใหม่เฉพาะเมื่อเปลี่ยนผู้พูด
2. แต่ละ segment ควรยาวอย่างน้อย 10 วินาที ยกเว้นคนพูดสั้นจริงๆ
3. ห้ามซอยทีละวินาทีหรือทีละประโยค

ตอบเป็น JSON array เท่านั้น ห้ามมีข้อความอื่น:
[{{"start": "M:SS", "end": "M:SS", "speaker": "ชื่อผู้พูด", "text": "ข้อความ"}}]"""

        # Build content with voice samples
        content = [{"type": "text", "text": prompt}]
        for s in voice_samples:
            content.append({"type": "text", "text": f"เสียงตัวอย่างของ {s['name']}:"})
            content.append({"type": "input_audio", "input_audio": {"data": s["b64"], "format": s["format"]}})
        content.append({"type": "text", "text": "ไฟล์เสียงประชุม:"})
        content.append({"type": "input_audio", "input_audio": {"data": chunk_b64, "format": "mp3"}})

        payload = json.dumps({
            "model": "google/gemini-2.5-flash",
            "messages": [{"role": "user", "content": content}],
            "max_tokens": 65000,
            "temperature": 0,
        }).encode("utf-8")

        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/chat/completions",
            data=payload,
            headers={
                "Authorization": f"Bearer {settings.OPEN_ROUNTER}",
                "Content-Type": "application/json",
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                result = json.loads(resp.read().decode("utf-8"))

            raw = result["choices"][0]["message"]["content"].strip()
            usage = result.get("usage", {})
            total_usage["prompt_tokens"] += usage.get("prompt_tokens", 0)
            total_usage["completion_tokens"] += usage.get("completion_tokens", 0)

            if raw.startswith("```"):
                lines = raw.split("\n")
                raw = "\n".join(lines[1:-1])
            raw = re.sub(r'[\x00-\x1f\x7f]', lambda m: '' if m.group() not in '\n\r\t' else m.group(), raw)

            chunk_segs = json.loads(raw, strict=False)
            # Offset timestamps + clean Thai spacing
            for seg in chunk_segs:
                seg["start"] = _parse_time(str(seg.get("start", "0:0"))) + chunk_start
                seg["end"] = _parse_time(str(seg.get("end", "0:0"))) + chunk_start
                if "text" in seg:
                    seg["text"] = re.sub(r'(?<=[\u0E00-\u0E7F])\s+(?=[\u0E00-\u0E7F])', '', seg["text"])
                    seg["text"] = _dedup_text(seg["text"])
            all_segments.extend(chunk_segs)
            logger.info("#%d Chunk %d-%d: %d segments", transcription_id, int(chunk_start), int(chunk_end), len(chunk_segs))
        except Exception as e:
            logger.error("#%d Chunk %d-%d failed: %s", transcription_id, int(chunk_start), int(chunk_end), e)
        finally:
            if os.path.exists(chunk_file):
                os.remove(chunk_file)

        pct = 10 + int((chunk_end / duration) * 70)
        t.progress_percent = pct
        t.status_message = f"กำลังถอดเสียง... ({int(chunk_end)}/{int(duration)}s)"
        db.commit()

        chunk_idx += 1
        chunk_start = chunk_end

    if os.path.exists(compressed):
        os.remove(compressed)

    # Merge consecutive same-speaker (keep speaker + text, ignore Gemini timestamps)
    merged_segs = []
    for seg in all_segments:
        speaker = seg.get("speaker", "Speaker 1")
        text = seg.get("text", "")

        if merged_segs and merged_segs[-1]["speaker"] == speaker:
            merged_segs[-1]["text"] += " " + text
        else:
            merged_segs.append({"text": text, "speaker": speaker})

    # Redistribute timestamps proportionally based on text length
    total_chars = sum(len(seg["text"]) for seg in merged_segs)
    if total_chars > 0:
        cursor = 0.0
        for seg in merged_segs:
            seg["start"] = round(cursor, 2)
            seg_duration = (len(seg["text"]) / total_chars) * duration
            cursor += seg_duration
            seg["end"] = round(cursor, 2)
    else:
        for seg in merged_segs:
            seg["start"] = 0.0
            seg["end"] = duration

    # Apply correction_dict
    from app.models.transcription import CorrectionDict
    corrections = db.query(CorrectionDict).all()
    if corrections:
        for seg in merged_segs:
            for c in corrections:
                seg["text"] = seg["text"].replace(c.wrong, c.correct)

    # Save segments
    from app.models.transcription import TranscriptionSegment
    all_text = []
    for i, seg in enumerate(merged_segs):
        db.add(TranscriptionSegment(
            transcription_id=transcription_id,
            segment_index=i,
            start_time=seg["start"],
            end_time=seg["end"],
            text=seg["text"],
            speaker=seg["speaker"],
        ))
        all_text.append(seg["text"])

    t.progress_percent = 85
    t.status_message = "กำลังบันทึก..."
    db.commit()

    # Generate analysis
    t.progress_percent = 90
    t.status_message = "กำลังวิเคราะห์การประชุม..."
    db.commit()

    transcript_for_analysis = "\n".join(f"{seg['speaker']}: {seg['text']}" for seg in merged_segs)
    try:
        custom_instructions = None
        if t.group_id:
            from app.models.transcription import TranscriptionGroup
            group = db.query(TranscriptionGroup).filter(TranscriptionGroup.id == t.group_id).first()
            if group and group.custom_instructions:
                custom_instructions = group.custom_instructions

        analysis = generate_analysis(transcript_for_analysis, custom_instructions, meeting_date=t.created_at.strftime("%d/%m/%Y"))
        mom_text = analysis.get("mom", "")
        if "สรุปภาพรวม" not in mom_text:
            logger.warning("#%d MoM missing สรุปภาพรวม, retrying...", transcription_id)
            analysis = generate_analysis(transcript_for_analysis, custom_instructions, meeting_date=t.created_at.strftime("%d/%m/%Y"))

        _speaker_names = list(set(seg["speaker"] for seg in merged_segs))
        t.summary = _strip_names_from_mom(analysis.get("mom", ""), _speaker_names)
        t.sentiment = analysis.get("sentiment", "")
        t.meeting_tone = analysis.get("meeting_tone", "")
        t.meeting_type = analysis.get("meeting_type", "")
        t.auto_title = analysis.get("title", "")
        t.summary_short = analysis.get("summary_short", "")
        t.topics = json.dumps(analysis.get("topics", []), ensure_ascii=False)
        t.action_items = json.dumps(analysis.get("action_items", []), ensure_ascii=False)
        t.key_decisions = json.dumps(analysis.get("key_decisions", []), ensure_ascii=False)
        t.open_questions = json.dumps(analysis.get("open_questions", []), ensure_ascii=False)
        t.speaker_suggestions = json.dumps(analysis.get("speaker_suggestions", []), ensure_ascii=False)
        t.deepgram_confidence = round(analysis.get("audio_quality", 0) / 100, 4)
    except Exception as e:
        logger.warning("#%d Analysis failed: %s", transcription_id, e)

    elapsed = time.time() - start_time

    # Build mom_full
    speakers_list = list(dict.fromkeys(seg["speaker"] for seg in merged_segs))
    mom_meta = f"### ข้อมูลการประชุม\n"
    mom_meta += f"- **หัวข้อ:** {t.auto_title or t.audio_file.original_filename}\n"
    mom_meta += f"- **วันที่:** {t.created_at.strftime('%d/%m/%Y %H:%M')}\n"
    mom_meta += f"- **ความยาว:** {int(duration // 60)} นาที {int(duration % 60)} วินาที\n"
    mom_meta += f"- **ผู้เข้าร่วม:** {', '.join(speakers_list)}\n"
    t.mom_full = mom_meta + "\n" + (t.summary or "")

    t.full_text = " ".join(all_text).strip()
    t.detected_language = "th"
    t.status = TranscriptionStatus.completed
    t.progress_percent = 100
    t.status_message = f"เสร็จสิ้น ({elapsed:.0f}s)"
    t.processing_time_seconds = elapsed
    t.audio_file.status = AudioStatus.completed

    # Cost tracking
    t.gemini_input_tokens = gemini_usage.get("prompt_tokens", 0)
    t.gemini_output_tokens = gemini_usage.get("completion_tokens", 0)
    gemini_cost = (t.gemini_input_tokens * 0.15 + t.gemini_output_tokens * 0.6) / 1_000_000
    t.gemini_cost_usd = round(gemini_cost, 6)
    # Deepgram cost: $0.0043/min (nova-3)
    t.deepgram_cost_usd = round((duration / 60) * 0.0043, 6)
    t.total_cost_usd = round(t.deepgram_cost_usd + t.gemini_cost_usd, 6)

    db.commit()
    logger.info("#%d Spectral done! %d segments, %d speakers, %.0fs, cost=$%.4f", transcription_id, len(final_segs), len(speakers_list), elapsed, t.total_cost_usd)


def process_transcription(transcription_id):
    db = SessionLocal()
    try:
        t = db.query(Transcription).filter(Transcription.id == transcription_id).first()
        if not t:
            return

        t.status = TranscriptionStatus.in_progress
        t.progress_percent = 5
        t.status_message = "กำลังเตรียมไฟล์..."
        db.commit()

        file_path = os.path.abspath(t.audio_file.file_path)
        start_time = time.time()

        parts = (t.model_size or "").split("+")
        diarization_model = parts[0] or "pyannote"
        transcription_model = parts[1] if len(parts) > 1 else "gemini"

        # Shortcut: gemini+gemini = single call (diarize + transcribe together)
        if diarization_model == "gemini" and transcription_model == "gemini":
            logger.info("#%d Using Gemini single-call mode (diarize + transcribe)", transcription_id)
            _process_gemini_single(db, t, file_path, transcription_id, start_time)
            return

        # Smart: Deepgram diarize if good, fallback to spectral if one-speaker-collapse
        if diarization_model == "smart":
            logger.info("#%d Using Smart hybrid mode", transcription_id)
            _process_spectral(db, t, file_path, transcription_id, start_time, mode="smart")
            return

        # Spectral: force spectral re-clustering (useful for mono single-mic recordings)
        if diarization_model == "spectral":
            logger.info("#%d Using Spectral clustering mode", transcription_id)
            _process_spectral(db, t, file_path, transcription_id, start_time, mode="spectral")
            return

        # Step 1: Diarization (5-25%)
        with ProgressTicker(db, t, 5, 25, f"{diarization_model} กำลังแยกผู้พูด...", interval=3):
            if diarization_model == "deepgram":
                guide, dg_segments, duration, num_speakers = build_timeline_guide_deepgram(file_path)
            elif diarization_model == "gpt":
                guide, dg_segments, duration, num_speakers = build_timeline_guide_llm(file_path, "openai/gpt-4o")
            else:
                guide, dg_segments, duration, num_speakers = build_timeline_guide(file_path)

        logger.info("#%d %s: %d segments, %d speakers, %.0fs", transcription_id, diarization_model, len(dg_segments), num_speakers, duration)

        # Auto-match speakers against stored voiceprints
        try:
            from voiceprint_service import identify_speakers, get_speaker_suggestions
            # Save suggestions for UI
            vp_suggestions = get_speaker_suggestions(file_path, dg_segments)
            t.voiceprint_suggestions = json.dumps(vp_suggestions, ensure_ascii=False)
            db.commit()
            logger.info("#%d Voiceprint suggestions: %s", transcription_id, vp_suggestions)
            # Auto-rename high-confidence matches
            vp_mapping = identify_speakers(file_path, dg_segments)
            if vp_mapping:
                # Update timeline guide with matched names
                for seg in dg_segments:
                    if seg.get("is_gap"):
                        continue
                    spk = seg["speaker"]
                    if spk in vp_mapping:
                        seg["matched_name"] = vp_mapping[spk]
                logger.info("#%d Voiceprint matched: %s", transcription_id, vp_mapping)
                # Rebuild guide with matched names
                guide_lines = []
                for seg in dg_segments:
                    if seg.get("is_gap"):
                        guide_lines.append(f"{_fmt(seg['start'])} - {_fmt(seg['end'])} : [Gap]")
                    else:
                        name = seg.get("matched_name", f"Speaker {seg['speaker'] + 1}")
                        guide_lines.append(f"{_fmt(seg['start'])} - {_fmt(seg['end'])} : {name}")
                guide = "[Speaker Timeline Guide]\n\n" + "\n\n".join(guide_lines)
        except Exception as e:
            logger.warning("#%d Voiceprint matching failed: %s", transcription_id, e)

        # Step 2: Gemini transcribes (chunked if > 10 min) (35-80%)
        with ProgressTicker(db, t, 35, 80, "Gemini กำลังถอดเสียง...", interval=5):
            if duration > 600:
                gemini_segments, gemini_usage = transcribe_chunked(file_path, dg_segments, duration)
            else:
                gemini_segments, gemini_usage = transcribe_with_gemini(file_path, guide)
        logger.info("#%d Gemini: %d segments, tokens: %s", transcription_id, len(gemini_segments), gemini_usage)

        # Step 3: Map Gemini text onto Deepgram timeline (Deepgram = structure, Gemini = content)
        t.progress_percent = 80
        t.status_message = "กำลังจัดเรียงข้อมูล..."
        db.commit()

        merged_segs = _map_text_to_deepgram_timeline(gemini_segments, dg_segments, duration)

        # Apply correction_dict before saving
        from app.models.transcription import CorrectionDict
        corrections = db.query(CorrectionDict).all()
        if corrections:
            for seg in merged_segs:
                for c in corrections:
                    seg["text"] = seg["text"].replace(c.wrong, c.correct)

        all_text = []
        for i, seg in enumerate(merged_segs):
            db.add(TranscriptionSegment(
                transcription_id=transcription_id,
                segment_index=i,
                start_time=seg["start"],
                end_time=seg["end"],
                text=seg["text"],
                speaker=seg["speaker"],
            ))
            all_text.append(seg["text"])

        t.progress_percent = 85
        t.status_message = "กำลังบันทึก..."
        db.commit()

        # Step 4: Generate analysis (MoM + sentiment + meeting type) (90-100%)
        db.commit()

        transcript_for_analysis = "\n".join(
            f"{seg['speaker']}: {seg['text']}" for seg in merged_segs
        )
        try:
            # Get group custom instructions
            custom_instructions = None
            if t.group_id:
                from app.models.transcription import TranscriptionGroup
                group = db.query(TranscriptionGroup).filter(TranscriptionGroup.id == t.group_id).first()
                if group and group.custom_instructions:
                    custom_instructions = group.custom_instructions

            with ProgressTicker(db, t, 90, 99, "กำลังวิเคราะห์การประชุม...", interval=4):
                analysis = generate_analysis(transcript_for_analysis, custom_instructions, meeting_date=t.created_at.strftime("%d/%m/%Y"))
                # QA: retry if สรุปภาพรวม section missing
                mom_text = analysis.get("mom", "")
                if "สรุปภาพรวม" not in mom_text:
                    logger.warning("#%d MoM missing สรุปภาพรวม, retrying...", transcription_id)
                    analysis = generate_analysis(transcript_for_analysis, custom_instructions, meeting_date=t.created_at.strftime("%d/%m/%Y"))
            _speaker_names = list(set(seg["speaker"] for seg in merged_segs))
            t.summary = _strip_names_from_mom(analysis.get("mom", ""), _speaker_names)
            t.sentiment = analysis.get("sentiment", "")
            t.meeting_tone = analysis.get("meeting_tone", "")
            t.meeting_type = analysis.get("meeting_type", "")
            t.auto_title = analysis.get("title", "")
            t.summary_short = analysis.get("summary_short", "")
            t.topics = json.dumps(analysis.get("topics", []), ensure_ascii=False)
            t.action_items = json.dumps(analysis.get("action_items", []), ensure_ascii=False)
            t.key_decisions = json.dumps(analysis.get("key_decisions", []), ensure_ascii=False)
            t.open_questions = json.dumps(analysis.get("open_questions", []), ensure_ascii=False)
            t.speaker_suggestions = json.dumps(analysis.get("speaker_suggestions", []), ensure_ascii=False)
            t.deepgram_confidence = round(analysis.get("audio_quality", 0) / 100, 4)
        except Exception as e:
            logger.warning("#%d Analysis failed: %s", transcription_id, e)

        elapsed = time.time() - start_time

        # Build mom_full (metadata + MoM content)
        speakers_list = []
        seen_spk = set()
        for seg in merged_segs:
            if seg["speaker"] not in seen_spk:
                speakers_list.append(seg["speaker"])
                seen_spk.add(seg["speaker"])
        mom_meta = f"### ข้อมูลการประชุม\n"
        mom_meta += f"- **หัวข้อ:** {t.auto_title or t.audio_file.original_filename}\n"
        mom_meta += f"- **วันที่:** {t.created_at.strftime('%d/%m/%Y %H:%M')}\n"
        mom_meta += f"- **ความยาว:** {int(duration // 60)} นาที {int(duration % 60)} วินาที\n"
        mom_meta += f"- **ผู้เข้าร่วม:** {', '.join(speakers_list)}\n"
        t.mom_full = mom_meta + "\n" + (t.summary or "")

        t.full_text = " ".join(all_text).strip()
        t.detected_language = "th"
        t.status = TranscriptionStatus.completed
        t.progress_percent = 100
        t.status_message = f"เสร็จสิ้น ({elapsed:.0f}s)"
        t.processing_time_seconds = elapsed
        t.audio_file.status = AudioStatus.completed

        # Auto-correct from correction dictionary (last step)
        from app.models.transcription import CorrectionDict
        corrections = db.query(CorrectionDict).all()
        if corrections:
            for seg_row in db.query(TranscriptionSegment).filter(
                TranscriptionSegment.transcription_id == transcription_id
            ).all():
                for c in corrections:
                    seg_row.text = seg_row.text.replace(c.wrong, c.correct)
            for field in ['full_text', 'summary', 'summary_short', 'key_decisions',
                          'action_items', 'topics', 'open_questions', 'auto_title']:
                val = getattr(t, field, None)
                if val:
                    for c in corrections:
                        val = val.replace(c.wrong, c.correct)
                    setattr(t, field, val)
            logger.info("#%d Applied %d corrections", transcription_id, len(corrections))

        # Cost tracking
        t.deepgram_duration_sec = duration
        if diarization_model == "deepgram":
            t.deepgram_cost_usd = round((duration / 60) * 0.0043, 6)
        else:
            t.deepgram_cost_usd = 0
        # deepgram_confidence is set from audio_quality in analysis step above
        # Gemini 2.5 Flash (OpenRouter): $0.30/M input, $2.50/M output
        input_tokens = gemini_usage.get("prompt_tokens", 0)
        output_tokens = gemini_usage.get("completion_tokens", 0)
        t.gemini_input_tokens = input_tokens
        t.gemini_output_tokens = output_tokens
        t.gemini_cost_usd = round(
            (input_tokens * 0.30 / 1_000_000) + (output_tokens * 2.50 / 1_000_000), 6
        )
        t.total_cost_usd = round(t.deepgram_cost_usd + t.gemini_cost_usd, 6)
        db.commit()

        logger.info("#%d Done in %.1fs (%d segments, merged from %d)",
                    transcription_id, elapsed, len(merged_segs), len(gemini_segments))

    except Exception as e:
        logger.exception("#%d Failed: %s", transcription_id, e)
        db.rollback()
        t = db.query(Transcription).filter(Transcription.id == transcription_id).first()
        if t:
            t.status = TranscriptionStatus.failed
            t.status_message = f"ล้มเหลว: {str(e)[:100]}"
            t.audio_file.status = AudioStatus.failed
            db.commit()
    finally:
        db.close()


def process_voiceprint_queue():
    """Process queued voiceprint enrollments."""
    queue_dir = os.path.join(os.path.dirname(__file__), "voiceprint_queue")
    if not os.path.isdir(queue_dir):
        return

    queue_files = sorted(f for f in os.listdir(queue_dir) if f.endswith(".json"))
    if not queue_files:
        return

    from voiceprint_service import enroll_from_transcription

    db = SessionLocal()
    try:
        for fname in queue_files:
            path = os.path.join(queue_dir, fname)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    task = json.load(f)
                logger.info("Enrolling voiceprint: %s", task["new_name"])
                enroll_from_transcription(
                    task["audio_path"],
                    task["transcription_id"],
                    task["old_name"],
                    task["new_name"],
                    db,
                )
            except Exception as e:
                logger.warning("Voiceprint enrollment failed: %s", e)
            finally:
                os.remove(path)
    finally:
        db.close()


def main():
    # Process voiceprint queue first
    process_voiceprint_queue()

    db = SessionLocal()
    pending = (
        db.query(Transcription)
        .filter(Transcription.status == TranscriptionStatus.pending)
        .order_by(Transcription.created_at)
        .first()
    )
    db.close()

    if pending:
        logger.info("Processing #%d", pending.id)
        process_transcription(pending.id)


def _get_code_mtime():
    """Get latest modification time of all .py files."""
    latest = 0
    for f in os.listdir(os.path.dirname(__file__) or "."):
        if f.endswith(".py"):
            mt = os.path.getmtime(f)
            if mt > latest:
                latest = mt
    app_dir = os.path.join(os.path.dirname(__file__) or ".", "app")
    if os.path.isdir(app_dir):
        for root, dirs, files in os.walk(app_dir):
            for f in files:
                if f.endswith(".py"):
                    mt = os.path.getmtime(os.path.join(root, f))
                    if mt > latest:
                        latest = mt
    return latest


if __name__ == "__main__":
    _start_mtime = _get_code_mtime()
    while True:
        main()
        # Check if code changed → restart
        if _get_code_mtime() > _start_mtime:
            logger.info("Code changed, restarting worker...")
            os.execv(sys.executable, [sys.executable] + sys.argv)
        time.sleep(5)
