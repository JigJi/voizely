import logging
import os
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.audio import AudioFile, AudioStatus
from app.models.transcription import (
    Transcription,
    TranscriptionSegment,
    TranscriptionStatus,
)
from app.services.whisper_engine import get_whisper_model

logger = logging.getLogger(__name__)

executor = ThreadPoolExecutor(max_workers=1)


def _build_speaker_segments(
    words: list[dict], diar_segments: list[dict]
) -> list[dict]:
    """Map each word to a speaker via diarization, then group into segments."""
    if not words:
        return []

    # Build label mapping
    label_map = {}
    for ds in diar_segments:
        raw = ds.get("label") or ds.get("speaker", "Unknown")
        if raw not in label_map:
            label_map[raw] = f"Speaker {len(label_map) + 1}"

    def get_speaker(mid: float) -> str:
        for ds in diar_segments:
            s = ds.get("start", 0)
            e = ds.get("end", 0)
            if s <= mid <= e:
                raw = ds.get("label") or ds.get("speaker", "Unknown")
                return label_map.get(raw, "Unknown")
        # Nearest turn within 2s
        best, min_d = "Unknown", 999.0
        for ds in diar_segments:
            d = min(abs(ds["start"] - mid), abs(ds["end"] - mid))
            if d < min_d:
                min_d = d
                raw = ds.get("label") or ds.get("speaker", "Unknown")
                best = label_map.get(raw, "Unknown")
        return best if min_d < 2.0 else "Unknown"

    # Assign speaker to each word
    if diar_segments:
        for w in words:
            w["speaker"] = get_speaker((w["start"] + w["end"]) / 2)
    else:
        for w in words:
            w["speaker"] = "Speaker 1"

    # Group consecutive words by same speaker
    grouped: list[dict] = []
    cur: dict | None = None
    for w in words:
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

    # Thai continuation characters (vowels, tone marks that can't start a word)
    _THAI_CONT = set("ิีึืุูเแโใไ็่้๊๋์ำัํฺ")

    # Merge: short segments + segments starting with continuation chars
    merged: list[dict] = [grouped[0]]
    for g in grouped[1:]:
        text = g["text"].lstrip()
        starts_mid_word = text and text[0] in _THAI_CONT

        if g["speaker"] == merged[-1]["speaker"]:
            # Same speaker → always merge
            merged[-1]["end"] = g["end"]
            merged[-1]["text"] += g["text"]
        elif starts_mid_word:
            # Starts with continuation char → word was split, merge with previous
            merged[-1]["end"] = g["end"]
            merged[-1]["text"] += g["text"]
        elif (g["end"] - g["start"]) < 0.3:
            # Very short fragment → merge with previous
            merged[-1]["end"] = g["end"]
            merged[-1]["text"] += g["text"]
        else:
            merged.append(g)

    # Add index
    for i, m in enumerate(merged):
        m["index"] = i

    return merged


def create_transcription(
    db: Session,
    audio: AudioFile,
    language: str | None = None,
    model_size: str = "Vinxscribe/biodatlab-whisper-th-large-v3-faster",
    initial_prompt: str | None = None,
    llm_provider: str | None = None,
    user_id: int | None = None,
) -> Transcription:
    transcription = Transcription(
        audio_file_id=audio.id,
        user_id=user_id,
        model_size=model_size,
        language=language,
        initial_prompt=initial_prompt,
        llm_provider=llm_provider,
        status=TranscriptionStatus.pending,
    )
    db.add(transcription)
    audio.status = AudioStatus.processing
    db.commit()
    db.refresh(transcription)

    # Worker process จะมาหยิบ pending transcription ไปทำเอง
    return transcription


def _run_transcription(
    transcription_id: int,
    file_path: str,
    language: str | None,
    model_size: str = "Vinxscribe/biodatlab-whisper-th-large-v3-faster",
    initial_prompt: str | None = None,
    llm_provider: str | None = None,
) -> None:
    db = SessionLocal()
    try:
        transcription = (
            db.query(Transcription)
            .filter(Transcription.id == transcription_id)
            .first()
        )
        if not transcription:
            return

        transcription.status = TranscriptionStatus.in_progress
        transcription.progress_percent = 0
        transcription.status_message = "กำลังโหลด AI model..."
        db.commit()

        model = get_whisper_model(model_size)

        transcription.status_message = "กำลังแปลงไฟล์เสียง..."
        db.commit()

        # Pre-process: convert to WAV 16kHz mono to reduce RAM usage
        wav_path = None
        try:
            wav_fd, wav_path = tempfile.mkstemp(suffix=".wav")
            os.close(wav_fd)
            subprocess.run(
                [
                    "ffmpeg", "-y", "-i", file_path,
                    "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le",
                    wav_path,
                ],
                check=True,
                capture_output=True,
            )
            transcribe_path = wav_path
            logger.info("Converted to WAV 16kHz: %s", wav_path)
        except Exception:
            logger.warning("FFmpeg conversion failed, using original file")
            transcribe_path = file_path
            if wav_path and os.path.exists(wav_path):
                os.unlink(wav_path)
            wav_path = None

        transcription.status_message = "กำลังเริ่มถอดเสียง..."
        db.commit()

        start = time.time()

        transcribe_kwargs = dict(
            language=language,
            beam_size=5,
            vad_filter=True,
            word_timestamps=False,
            condition_on_previous_text=False,
            temperature=[0.0, 0.2, 0.4, 0.6, 0.8, 1.0],
        )
        if initial_prompt:
            transcribe_kwargs["initial_prompt"] = initial_prompt

        segments_iter, info = model.transcribe(transcribe_path, **transcribe_kwargs)

        transcription.detected_language = info.language
        duration = info.duration if info.duration else 1.0
        transcription.status_message = "กำลังถอดเสียง..."
        db.commit()

        # Collect segments with timestamps
        raw_segments = []
        all_text_parts = []
        for idx, segment in enumerate(segments_iter):
            all_text_parts.append(segment.text)
            raw_segments.append({
                "index": idx,
                "start": round(segment.start, 2),
                "end": round(segment.end, 2),
                "text": segment.text,
            })

            progress = min((segment.end / duration) * 100, 90)
            transcription.progress_percent = progress
            elapsed = time.time() - start
            if progress > 0:
                eta = (elapsed / progress) * (100 - progress)
                mins, secs = divmod(int(eta), 60)
                transcription.status_message = f"กำลังถอดเสียง... (เหลือประมาณ {mins} นาที {secs} วินาที)"
            db.commit()

        logger.info("Whisper: %d segments", len(raw_segments))

        # Save segments to DB
        transcription.progress_percent = 96
        transcription.status_message = "กำลังบันทึกผลลัพธ์..."
        db.commit()

        for rs in raw_segments:
            seg = TranscriptionSegment(
                transcription_id=transcription_id,
                segment_index=rs["index"],
                start_time=rs["start"],
                end_time=rs["end"],
                text=rs["text"],
                speaker=rs.get("speaker"),
            )
            db.add(seg)

        transcription.full_text = "".join(all_text_parts).strip()

        # Mark completed FIRST so web is usable immediately
        transcription.status = TranscriptionStatus.completed
        transcription.progress_percent = 100
        transcription.status_message = "เสร็จสิ้น"
        transcription.processing_time_seconds = time.time() - start
        transcription.audio_file.status = AudioStatus.completed
        db.commit()

        logger.info("Transcription %d completed in %.1fs", transcription_id, time.time() - start)

    except Exception as e:
        logger.exception("Transcription %d failed", transcription_id)
        db.rollback()
        transcription = (
            db.query(Transcription)
            .filter(Transcription.id == transcription_id)
            .first()
        )
        if transcription:
            transcription.status = TranscriptionStatus.failed
            transcription.status_message = f"ล้มเหลว: {str(e)[:100]}"
            transcription.audio_file.status = AudioStatus.failed
            transcription.audio_file.error_message = str(e)
            db.commit()
    finally:
        if wav_path and os.path.exists(wav_path):
            os.unlink(wav_path)
        db.close()


def _run_llm_postprocess(
    transcription_id: int,
    raw_segments: list[dict],
    llm_provider: str,
    initial_prompt: str | None,
) -> None:
    """Run LLM post-processing. DB is only opened briefly for reads/writes."""
    try:
        from app.services.llm_service import (
            correct_text, generate_summary, identify_speakers,
        )

        # 1) Identify speaker names (no DB needed - uses raw_segments)
        logger.info("LLM %d: identifying speakers...", transcription_id)
        speaker_map = identify_speakers(raw_segments, llm_provider)

        # Save speaker names (quick DB open/close)
        if speaker_map:
            db = SessionLocal()
            for seg_obj in (
                db.query(TranscriptionSegment)
                .filter(TranscriptionSegment.transcription_id == transcription_id)
                .all()
            ):
                if seg_obj.speaker and seg_obj.speaker in speaker_map:
                    seg_obj.speaker = speaker_map[seg_obj.speaker]
            db.commit()
            db.close()

        # 2) Correct full text (single LLM call - fast)
        logger.info("LLM %d: correcting text...", transcription_id)
        db = SessionLocal()
        t = db.query(Transcription).filter(Transcription.id == transcription_id).first()
        full_text = t.full_text if t else ""
        db.close()

        correction = correct_text(full_text, llm_provider, initial_prompt)

        db = SessionLocal()
        t = db.query(Transcription).filter(Transcription.id == transcription_id).first()
        if t:
            t.clean_text = correction.text
        db.commit()
        db.close()

        # 3) Summary (no DB needed during LLM call)
        logger.info("LLM %d: generating summary...", transcription_id)
        db = SessionLocal()
        t = db.query(Transcription).filter(Transcription.id == transcription_id).first()
        text_for_summary = (t.clean_text or t.full_text) if t else ""
        db.close()

        summary = generate_summary(text_for_summary, llm_provider)

        # Save summary (quick)
        db = SessionLocal()
        t = db.query(Transcription).filter(Transcription.id == transcription_id).first()
        if t:
            t.summary = summary.text
            t.status_message = "เสร็จสิ้น"
        db.commit()
        db.close()

        logger.info("LLM %d done", transcription_id)

    except Exception as e:
        logger.warning("LLM post-processing %d failed: %s", transcription_id, e)
        try:
            transcription = db.query(Transcription).filter(Transcription.id == transcription_id).first()
            if transcription:
                transcription.status_message = "เสร็จสิ้น (AI ล้มเหลว)"
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


def retry_transcription(db: Session, transcription: Transcription) -> None:
    """Reset a failed transcription to pending. Worker will pick it up."""
    transcription.status = TranscriptionStatus.pending
    transcription.progress_percent = 0
    transcription.status_message = "รอประมวลผล..."
    transcription.full_text = None
    transcription.clean_text = None
    transcription.summary = None
    transcription.detected_language = None
    transcription.processing_time_seconds = None
    transcription.llm_processing_time = None
    transcription.audio_file.status = AudioStatus.processing
    transcription.audio_file.error_message = None

    db.query(TranscriptionSegment).filter(
        TranscriptionSegment.transcription_id == transcription.id
    ).delete()
    db.commit()


def get_transcription(db: Session, transcription_id: int) -> Transcription | None:
    return (
        db.query(Transcription).filter(Transcription.id == transcription_id).first()
    )


def get_transcription_by_audio(db: Session, audio_id: int) -> Transcription | None:
    return (
        db.query(Transcription)
        .filter(Transcription.audio_file_id == audio_id)
        .first()
    )


def get_all_transcriptions(db: Session, user_id: int | None = None) -> list[Transcription]:
    q = db.query(Transcription)
    if user_id is not None:
        q = q.filter(Transcription.user_id == user_id)
    return q.order_by(Transcription.created_at.desc()).all()


def get_grouped_transcriptions(db: Session, user_id: int | None = None):
    """Return groups with their transcriptions for sidebar."""
    from app.models.transcription import TranscriptionGroup
    # Non-default groups: filter by user, newest first
    q_groups = db.query(TranscriptionGroup).filter(TranscriptionGroup.is_default == False)
    if user_id is not None:
        q_groups = q_groups.filter(
            (TranscriptionGroup.user_id == user_id) |
            (TranscriptionGroup.user_id.is_(None))
        )
    custom_groups = q_groups.order_by(TranscriptionGroup.created_at.desc()).all()
    # Default group always last
    default_group = (
        db.query(TranscriptionGroup)
        .filter(TranscriptionGroup.is_default == True)
        .first()
    )
    # Ungrouped transcriptions
    q_ungrouped = db.query(Transcription).filter(Transcription.group_id.is_(None))
    if user_id is not None:
        q_ungrouped = q_ungrouped.filter(Transcription.user_id == user_id)
    ungrouped = q_ungrouped.order_by(Transcription.created_at.desc()).all()

    result = []
    for g in custom_groups:
        if user_id is not None:
            items = [t for t in g.transcriptions if t.user_id == user_id]
        else:
            items = list(g.transcriptions)
        result.append({"group": g, "transcriptions": items})
    if default_group:
        if user_id is not None:
            grouped_items = [t for t in default_group.transcriptions if t.user_id == user_id]
        else:
            grouped_items = list(default_group.transcriptions)
        items = grouped_items + ungrouped
        result.append({"group": default_group, "transcriptions": items})
    return result
