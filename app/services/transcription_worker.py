"""Standalone transcription worker - runs as separate process."""
import sys
import os
import json
import time
import logging
import subprocess
import tempfile

os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main():
    args = json.loads(sys.argv[1])
    transcription_id = args["transcription_id"]
    file_path = args["file_path"]
    language = args.get("language")
    model_size = args.get("model_size", "Vinxscribe/biodatlab-whisper-th-large-v3-faster")
    initial_prompt = args.get("initial_prompt")
    llm_provider = args.get("llm_provider")

    from app.database import SessionLocal
    from app.models.audio import AudioFile, AudioStatus
    from app.models.transcription import (
        Transcription, TranscriptionSegment, TranscriptionStatus,
    )

    db = SessionLocal()
    try:
        transcription = db.query(Transcription).filter(Transcription.id == transcription_id).first()
        if not transcription:
            return

        transcription.status = TranscriptionStatus.in_progress
        transcription.progress_percent = 0
        transcription.status_message = "กำลังโหลด AI model..."
        db.commit()

        # Load whisper
        from app.services.whisper_engine import get_whisper_model
        model = get_whisper_model(model_size)

        transcription.status_message = "กำลังแปลงไฟล์เสียง..."
        db.commit()

        # Convert to WAV
        wav_path = None
        try:
            wav_fd, wav_path = tempfile.mkstemp(suffix=".wav")
            os.close(wav_fd)
            subprocess.run(
                ["ffmpeg", "-y", "-i", file_path, "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", wav_path],
                check=True, capture_output=True,
            )
            transcribe_path = wav_path
        except Exception:
            transcribe_path = file_path
            if wav_path and os.path.exists(wav_path):
                os.unlink(wav_path)
            wav_path = None

        transcription.status_message = "กำลังถอดเสียง..."
        db.commit()

        start = time.time()

        # Transcribe
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

        import re
        def _is_garbage(text):
            t = text.strip()
            if not t: return True
            if len(t) > 5 and len(set(t.replace(" ", "").replace(",", ""))) <= 3: return True
            if re.match(r'^[\s?!.,;:…\-_=+*#@&^~`\'\"()\[\]{}|/\\]+$', t): return True
            return False

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
            db.commit()

        logger.info("Whisper: %d segments", len(raw_segments))

        # Filter garbage segments (replace with empty)
        for rs in raw_segments:
            if _is_garbage(rs["text"]):
                logger.info("Garbage segment [%.1f-%.1f]: %s", rs["start"], rs["end"], rs["text"][:30])
                rs["text"] = ""

        # Remove empty segments
        raw_segments = [rs for rs in raw_segments if rs["text"].strip()]
        for i, rs in enumerate(raw_segments):
            rs["index"] = i
        all_text_parts = [rs["text"] for rs in raw_segments]

        # Save segments
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
        transcription.status = TranscriptionStatus.completed
        transcription.progress_percent = 100
        transcription.status_message = "เสร็จสิ้น"
        transcription.processing_time_seconds = time.time() - start
        transcription.audio_file.status = AudioStatus.completed
        db.commit()
        db.close()

        logger.info("Transcription %d completed in %.1fs", transcription_id, time.time() - start)

        # LLM post-processing (disabled - run separately to avoid crash)
        # if llm_provider:
        #     _run_llm(transcription_id, raw_segments, llm_provider, initial_prompt)

    except Exception as e:
        logger.exception("Transcription %d failed", transcription_id)
        db.rollback()
        transcription = db.query(Transcription).filter(Transcription.id == transcription_id).first()
        if transcription:
            transcription.status = TranscriptionStatus.failed
            transcription.status_message = f"ล้มเหลว: {str(e)[:100]}"
            transcription.audio_file.status = AudioStatus.failed
            db.commit()
    finally:
        if wav_path and os.path.exists(wav_path):
            os.unlink(wav_path)
        db.close()


def _run_llm(transcription_id, raw_segments, llm_provider, initial_prompt):
    from app.database import SessionLocal
    from app.models.transcription import Transcription, TranscriptionSegment
    from app.services.llm_service import correct_text, generate_summary, identify_speakers

    try:
        # 1) Speaker names
        logger.info("LLM %d: speakers...", transcription_id)
        speaker_map = identify_speakers(raw_segments, llm_provider)
        if speaker_map:
            db = SessionLocal()
            for seg in db.query(TranscriptionSegment).filter(
                TranscriptionSegment.transcription_id == transcription_id
            ).all():
                if seg.speaker and seg.speaker in speaker_map:
                    seg.speaker = speaker_map[seg.speaker]
            db.commit()
            db.close()

        # 2) Correct text
        logger.info("LLM %d: correcting...", transcription_id)
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

        # 3) Summary
        logger.info("LLM %d: summary...", transcription_id)
        summary = generate_summary(correction.text or full_text, llm_provider)

        db = SessionLocal()
        t = db.query(Transcription).filter(Transcription.id == transcription_id).first()
        if t:
            t.summary = summary.text
            t.status_message = "เสร็จสิ้น"
        db.commit()
        db.close()

        logger.info("LLM %d done!", transcription_id)
    except Exception as e:
        logger.error("LLM %d failed: %s", transcription_id, e)


if __name__ == "__main__":
    main()
