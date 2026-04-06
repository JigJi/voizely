"""
Speech-to-Text Worker
Process ONE pending transcription then exit.
Runs in loop via start_worker_wsl.bat

Works on both Windows and WSL/Linux.
"""
import os
import sys
import time
import json
import logging
import subprocess
import tempfile
import re
import platform

os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
)
logger = logging.getLogger("worker")

# Patch torch.load for pyannote (PyTorch 2.6+ compatibility)
import torch
_orig_load = torch.load
def _safe_load(*a, **kw):
    kw["weights_only"] = False
    return _orig_load(*a, **kw)
torch.load = _safe_load

# Register numpy types with psycopg2 so PostgreSQL can handle them
import numpy as np
import psycopg2.extensions
psycopg2.extensions.register_adapter(np.float32, lambda v: psycopg2.extensions.AsIs(float(v)))
psycopg2.extensions.register_adapter(np.float64, lambda v: psycopg2.extensions.AsIs(float(v)))
psycopg2.extensions.register_adapter(np.int32, lambda v: psycopg2.extensions.AsIs(int(v)))
psycopg2.extensions.register_adapter(np.int64, lambda v: psycopg2.extensions.AsIs(int(v)))

from app.database import SessionLocal
from app.models.audio import AudioFile, AudioStatus
from app.models.transcription import (
    Transcription, TranscriptionSegment, TranscriptionStatus,
)
from app.config import settings

IS_LINUX = platform.system() == "Linux"


PROJECT_DIR = "/mnt/d/0_product_dev/speech_text" if IS_LINUX else os.path.dirname(os.path.abspath(__file__))

def to_wsl_path(win_path):
    """Convert Windows path to WSL path if running on Linux/WSL."""
    if not IS_LINUX or not win_path:
        return win_path
    # Absolute Windows path: D:\path → /mnt/d/path
    if len(win_path) > 1 and win_path[1] in (":", ):
        drive = win_path[0].lower()
        rest = win_path[2:].replace("\\", "/")
        return f"/mnt/{drive}{rest}"
    # Relative path: uploads\file.wav → /mnt/d/.../uploads/file.wav
    rel = win_path.replace("\\", "/")
    return os.path.join(PROJECT_DIR, rel)


def clean_repetition(text):
    """Remove repeated phrases from text. Returns cleaned text."""
    # Find any phrase (2-20 chars) repeated more than 3 times
    for length in range(3, 21):
        words = text.split()
        # Check word-level repetition
        for i in range(len(words)):
            phrase = " ".join(words[i:i+length//3+1])
            if len(phrase) < 2:
                continue
            count = text.count(phrase)
            if count > 3 and len(phrase) * count > len(text) * 0.3:
                # This phrase takes >30% of text and repeats >3 times
                # Keep only the first occurrence
                first_end = text.find(phrase) + len(phrase)
                return text[:first_end].strip()
    return text


def is_garbage(text):
    t = text.strip()
    if not t:
        return True
    if len(t) > 5 and len(set(t.replace(" ", "").replace(",", ""))) <= 3:
        return True
    if re.match(r'^[\s?!.,;:…\-_=+*#@&^~`\'\"()\[\]{}|/\\]+$', t):
        return True
    return False


DIARIZATION_TIMEOUT = 180  # seconds (3 minutes)


def _run_diarization(audio_path, result_file):
    """Run pyannote diarization in a separate process. Writes results to a JSON file."""
    try:
        from pyannote.audio import Pipeline
        logger.info("Loading pyannote (GPU)...")
        pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            use_auth_token=settings.HF_TOKEN,
        )
        pipeline.to(torch.device("cuda"))
        logger.info("Diarizing...")
        diarization = pipeline(audio_path)

        diar_turns = []
        for turn, _, speaker in diarization.itertracks(yield_label=True):
            diar_turns.append({"start": turn.start, "end": turn.end, "label": speaker})

        unique = set(d["label"] for d in diar_turns)
        logger.info("Pyannote: %d turns, %d speakers", len(diar_turns), len(unique))

        with open(result_file, "w", encoding="utf-8") as f:
            json.dump(diar_turns, f)
    except Exception as e:
        logger.error("Diarization subprocess error: %s", e)
        with open(result_file, "w", encoding="utf-8") as f:
            json.dump([], f)


def run_diarization_with_timeout(audio_path, timeout=DIARIZATION_TIMEOUT):
    """Run diarization in a subprocess with timeout. Returns list of turns or empty list."""
    import multiprocessing
    ctx = multiprocessing.get_context("spawn")
    result_fd, result_file = tempfile.mkstemp(suffix=".json")
    os.close(result_fd)
    try:
        p = ctx.Process(target=_run_diarization, args=(audio_path, result_file))
        p.start()
        p.join(timeout=timeout)
        if p.is_alive():
            logger.warning("Diarization timed out after %ds, killing...", timeout)
            p.kill()
            p.join(5)
            return []
        if p.exitcode != 0:
            logger.warning("Diarization process exited with code %d", p.exitcode)
            return []
        with open(result_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning("Diarization failed: %s", e)
        return []
    finally:
        if os.path.exists(result_file):
            os.unlink(result_file)


def _safe_update(db, t, **kwargs):
    """Update transcription fields with stale data protection."""
    try:
        db.refresh(t)
    except Exception:
        pass
    for k, v in kwargs.items():
        setattr(t, k, v)
    try:
        db.commit()
    except Exception as e:
        logger.warning("DB update failed (row may have been deleted): %s", e)
        db.rollback()


def process_transcription(transcription_id):
    db = SessionLocal()
    wav_path = None
    try:
        t = db.query(Transcription).filter(Transcription.id == transcription_id).first()
        if not t:
            return

        t.status = TranscriptionStatus.in_progress
        t.progress_percent = 0
        t.status_message = "กำลังโหลด AI model..."
        db.commit()

        # Load Whisper
        from faster_whisper import WhisperModel
        model_dir = to_wsl_path(settings.WHISPER_MODEL_DIR)
        logger.info("Loading Whisper: %s", t.model_size)
        model = WhisperModel(
            t.model_size, device="cuda", compute_type="float16",
            download_root=model_dir,
        )

        # Convert audio
        t.status_message = "กำลังแปลงไฟล์เสียง..."
        db.commit()

        file_path = to_wsl_path(t.audio_file.file_path)
        try:
            wav_fd, wav_path = tempfile.mkstemp(suffix=".wav")
            os.close(wav_fd)
            subprocess.run(
                ["ffmpeg", "-y", "-i", file_path,
                 "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", wav_path],
                check=True, capture_output=True,
            )
            audio_path = wav_path
            logger.info("Converted to WAV: %s", wav_path)
        except Exception as e:
            logger.warning("FFmpeg failed: %s, using original", e)
            audio_path = file_path
            if wav_path and os.path.exists(wav_path):
                os.unlink(wav_path)
            wav_path = None

        # Transcribe
        t.status_message = "กำลังถอดเสียง..."
        db.commit()

        start = time.time()
        kwargs = dict(
            language=t.language,
            beam_size=5,
            vad_filter=True,
            word_timestamps=True,
            condition_on_previous_text=False,
            temperature=[0.0, 0.2, 0.4, 0.6, 0.8, 1.0],
        )
        if t.initial_prompt:
            kwargs["initial_prompt"] = t.initial_prompt

        segments_iter, info = model.transcribe(audio_path, **kwargs)
        lang = str(info.language) if info.language else None
        dur = float(info.duration) if info.duration else 1.0
        logger.info("Detected: language=%s (%s), duration=%.1f (%s)", lang, type(info.language).__name__, dur, type(info.duration).__name__)
        t.detected_language = lang
        db.commit()
        duration = dur

        # Collect all words with timestamps
        all_words = []
        raw_segments = []
        all_text = []
        for seg in segments_iter:
            cleaned = clean_repetition(seg.text)
            if is_garbage(cleaned):
                logger.info("Filtered: %s", seg.text[:30])
                continue
            if cleaned != seg.text:
                logger.info("Cleaned repetition: %s → %s", seg.text[:50], cleaned[:50])
            raw_segments.append({
                "index": len(raw_segments),
                "start": round(seg.start, 2),
                "end": round(seg.end, 2),
                "text": cleaned,
            })
            all_text.append(cleaned)
            # Collect word-level timestamps
            if seg.words:
                for w in seg.words:
                    word_text = w.word
                    if word_text.strip():
                        all_words.append({
                            "word": word_text,
                            "start": round(w.start, 2),
                            "end": round(w.end, 2),
                        })
            t.progress_percent = min((seg.end / duration) * 100, 80)
            db.commit()

        logger.info("Whisper: %d segments, %d words in %.0fs", len(raw_segments), len(all_words), time.time() - start)

        # Free GPU from Whisper
        logger.info("Releasing Whisper model from GPU...")
        del model
        import gc
        gc.collect()
        torch.cuda.empty_cache()
        logger.info("GPU freed: %.1f GB available", torch.cuda.mem_get_info()[0]/1024**3)

        # Diarization (pyannote on GPU, with timeout)
        t.progress_percent = 82
        t.status_message = "กำลังระบุผู้พูด..."
        db.commit()

        try:
            diar_turns = run_diarization_with_timeout(audio_path)

            if diar_turns and all_words:
                label_map = {}
                for d in diar_turns:
                    if d["label"] not in label_map:
                        label_map[d["label"]] = f"Speaker {len(label_map) + 1}"

                # Assign speaker to each word based on pyannote turns
                def get_speaker_for_time(mid):
                    best, best_overlap = None, 0
                    for d in diar_turns:
                        if d["start"] <= mid <= d["end"]:
                            return label_map[d["label"]]
                        # Track nearest
                        dist = min(abs(d["start"] - mid), abs(d["end"] - mid))
                        if best is None or dist < best_overlap:
                            best_overlap = dist
                            best = label_map[d["label"]]
                    return best if best and best_overlap < 2.0 else "Unknown"

                for w in all_words:
                    mid = (w["start"] + w["end"]) / 2
                    w["speaker"] = get_speaker_for_time(mid)

                # === Pass 1: Group words by speaker ===
                grouped = []
                cur = None
                for w in all_words:
                    if cur is None or w["speaker"] != cur["speaker"]:
                        if cur:
                            grouped.append(cur)
                        cur = {
                            "speaker": w["speaker"],
                            "start": w["start"],
                            "end": w["end"],
                            "text": w["word"],
                        }
                    else:
                        cur["end"] = w["end"]
                        cur["text"] += w["word"]
                if cur:
                    grouped.append(cur)

                logger.info("Pass 1: %d raw speaker segments", len(grouped))

                # === Pass 2: Repair with PyThaiNLP ===
                from pythainlp.tokenize import word_tokenize
                MIN_CHARS = 6

                def fix_boundary(prev_text, next_text):
                    """Use PyThaiNLP to find proper word boundary between two speaker texts.
                    Returns (fixed_prev, fixed_next)."""
                    # Take last ~30 chars of prev + first ~30 chars of next
                    tail = prev_text[-30:] if len(prev_text) > 30 else prev_text
                    head = next_text[:30] if len(next_text) > 30 else next_text
                    combined = tail + head

                    words = word_tokenize(combined, engine="newmm")

                    # Find where the original boundary was
                    boundary_pos = len(tail)
                    # Walk through tokenized words to find the best cut point
                    pos = 0
                    best_cut = 0
                    for w in words:
                        pos += len(w)
                        if pos <= boundary_pos:
                            best_cut = pos

                    # Calculate how much to move
                    actual_cut_in_prev = len(prev_text) - (len(tail) - best_cut)
                    if actual_cut_in_prev < 1 or actual_cut_in_prev >= len(prev_text):
                        return prev_text, next_text

                    fixed_prev = prev_text[:actual_cut_in_prev]
                    moved = prev_text[actual_cut_in_prev:]
                    fixed_next = moved + next_text

                    return fixed_prev, fixed_next

                repaired = [grouped[0]]
                for g in grouped[1:]:
                    text = g["text"].strip()

                    if len(text) < MIN_CHARS:
                        # Tiny fragment — merge into previous
                        repaired[-1]["end"] = g["end"]
                        repaired[-1]["text"] += text
                        logger.info("Repair: merged tiny '%s' (%s) into %s", text[:20], g["speaker"], repaired[-1]["speaker"])
                    else:
                        # Fix word boundary using PyThaiNLP
                        prev_text = repaired[-1]["text"]
                        fixed_prev, fixed_next = fix_boundary(prev_text, text)
                        if fixed_prev != prev_text:
                            moved = prev_text[len(fixed_prev):]
                            logger.info("Repair: moved '%s' from %s to %s", moved.strip()[:20], repaired[-1]["speaker"], g["speaker"])
                            repaired[-1]["text"] = fixed_prev
                            g["text"] = fixed_next
                        repaired.append(g)

                # Merge consecutive segments that ended up with same speaker after repair
                final = [repaired[0]]
                for r in repaired[1:]:
                    if r["speaker"] == final[-1]["speaker"]:
                        final[-1]["end"] = r["end"]
                        final[-1]["text"] += r["text"]
                    else:
                        final.append(r)

                logger.info("Pass 2: %d segments after repair (from %d)", len(final), len(grouped))

                # Re-index
                raw_segments = []
                all_text = []
                for i, m in enumerate(final):
                    raw_segments.append({
                        "index": i,
                        "start": round(m["start"], 2),
                        "end": round(m["end"], 2),
                        "text": m["text"].strip(),
                        "speaker": m["speaker"],
                    })
                    all_text.append(m["text"])

                logger.info("Word-level diarization: %d final segments from %d words", len(raw_segments), len(all_words))

            elif diar_turns and not all_words:
                # Fallback: no word timestamps, assign majority speaker per segment
                label_map = {}
                for d in diar_turns:
                    if d["label"] not in label_map:
                        label_map[d["label"]] = f"Speaker {len(label_map) + 1}"
                for rs in raw_segments:
                    mid = (rs["start"] + rs["end"]) / 2
                    for d in diar_turns:
                        if d["start"] <= mid <= d["end"]:
                            rs["speaker"] = label_map[d["label"]]
                            break
                logger.info("Fallback diarization: %d segments", len(raw_segments))

        except Exception as e:
            logger.warning("Diarization failed: %s", e)

        # Save segments
        t.progress_percent = 92
        t.status_message = "กำลังบันทึก..."
        db.commit()

        for rs in raw_segments:
            db.add(TranscriptionSegment(
                transcription_id=transcription_id,
                segment_index=rs["index"],
                start_time=rs["start"],
                end_time=rs["end"],
                text=rs["text"],
                speaker=rs.get("speaker"),
            ))

        t.full_text = "".join(all_text).strip()
        t.status = TranscriptionStatus.completed
        t.progress_percent = 93
        t.status_message = "ถอดเสียงเสร็จ"
        t.processing_time_seconds = time.time() - start
        t.audio_file.status = AudioStatus.completed
        db.commit()

        logger.info("Transcription %d done in %.0fs", transcription_id, time.time() - start)

        # LLM post-processing runs on Windows side (llm_worker.py)
        # progress stays at 95 so llm_worker picks it up
        t.progress_percent = 95
        t.status_message = "รอ AI แก้ข้อความ..."
        db.commit()

    except Exception as e:
        logger.exception("Failed: %s", e)
        db.rollback()
        t = db.query(Transcription).filter(Transcription.id == transcription_id).first()
        if t:
            t.status = TranscriptionStatus.failed
            t.status_message = f"ล้มเหลว: {str(e)[:100]}"
            t.audio_file.status = AudioStatus.failed
            db.commit()
    finally:
        if wav_path and os.path.exists(wav_path):
            os.unlink(wav_path)
        db.close()


def main():
    from datetime import datetime, timedelta
    db = SessionLocal()

    # Pick pending
    pending = (
        db.query(Transcription)
        .filter(
            Transcription.status == TranscriptionStatus.pending,
            Transcription.model_size.notin_(["gemini", "deepgram"]),
        )
        .order_by(Transcription.created_at)
        .first()
    )

    # Recover stuck (>5 min)
    if not pending:
        cutoff = datetime.utcnow() - timedelta(minutes=5)
        stuck = (
            db.query(Transcription)
            .filter(
                Transcription.status == TranscriptionStatus.in_progress,
                Transcription.created_at < cutoff,
            )
            .first()
        )
        if stuck:
            logger.info("Recovering stuck #%d", stuck.id)
            stuck.status = TranscriptionStatus.pending
            stuck.progress_percent = 0
            db.query(TranscriptionSegment).filter(
                TranscriptionSegment.transcription_id == stuck.id
            ).delete()
            db.commit()
            pending = stuck
    db.close()

    if pending:
        logger.info("Processing #%d", pending.id)
        process_transcription(pending.id)


if __name__ == "__main__":
    main()
