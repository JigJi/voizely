"""
LLM Worker - runs on Windows to access Ollama (localhost) and OpenRouter.
Polls for completed transcriptions that haven't been LLM-corrected yet.
"""
import logging
import time

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s %(message)s")
logger = logging.getLogger("llm_worker")

from app.database import SessionLocal
from app.models.transcription import Transcription, TranscriptionSegment, TranscriptionStatus
from app.services.llm_service import correct_segments


def process_llm(transcription_id):
    db = SessionLocal()
    try:
        t = db.query(Transcription).filter(Transcription.id == transcription_id).first()
        if not t:
            return

        segments = db.query(TranscriptionSegment).filter(
            TranscriptionSegment.transcription_id == transcription_id
        ).order_by(TranscriptionSegment.segment_index).all()

        seg_data = [{"index": s.segment_index, "text": s.text} for s in segments]
        if not seg_data:
            return

        # GPT-4o-mini first (fast, API)
        t.status_message = "GPT-4o-mini กำลังแก้ข้อความ..."
        db.commit()
        try:
            gpt_map = correct_segments(seg_data, "openrouter", t.initial_prompt)
            for seg in segments:
                if seg.segment_index in gpt_map:
                    seg.clean_text_alt = gpt_map[seg.segment_index]
            db.commit()
            logger.info("#%d GPT-4o-mini: corrected %d/%d segments", transcription_id, len(gpt_map), len(seg_data))
        except Exception as e:
            logger.warning("#%d GPT-4o-mini failed: %s", transcription_id, e)

        # Typhoon (ollama - local, slower)
        t.status_message = "Typhoon กำลังแก้ข้อความ..."
        db.commit()
        try:
            typhoon_map = correct_segments(seg_data, "ollama", t.initial_prompt)
            for seg in segments:
                if seg.segment_index in typhoon_map:
                    seg.clean_text = typhoon_map[seg.segment_index]
            db.commit()
            logger.info("#%d Typhoon: corrected %d/%d segments", transcription_id, len(typhoon_map), len(seg_data))
        except Exception as e:
            logger.warning("#%d Typhoon failed: %s", transcription_id, e)

        t.progress_percent = 100
        t.status_message = "เสร็จสิ้น"
        db.commit()
        logger.info("#%d LLM done", transcription_id)

    except Exception as e:
        logger.exception("#%d LLM failed: %s", transcription_id, e)
    finally:
        db.close()


def main():
    db = SessionLocal()
    # Find completed transcriptions where LLM hasn't run yet (clean_text is NULL)
    t = (
        db.query(Transcription)
        .filter(
            Transcription.status == TranscriptionStatus.completed,
            Transcription.progress_percent < 100,
        )
        .order_by(Transcription.created_at)
        .first()
    )
    db.close()

    if t:
        logger.info("Processing LLM for #%d", t.id)
        process_llm(t.id)


if __name__ == "__main__":
    main()
