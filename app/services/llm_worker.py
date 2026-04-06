"""Standalone LLM worker - runs as separate process to avoid blocking web."""
import sys
import json
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main(transcription_id: int, raw_segments_json: str, llm_provider: str, initial_prompt: str | None):
    from app.database import SessionLocal
    from app.models.transcription import Transcription, TranscriptionSegment
    from app.services.llm_service import correct_text, generate_summary, identify_speakers

    raw_segments = json.loads(raw_segments_json)

    try:
        # 1) Speaker names
        logger.info("LLM %d: identifying speakers...", transcription_id)
        speaker_map = identify_speakers(raw_segments, llm_provider)
        if speaker_map:
            db = SessionLocal()
            for seg in db.query(TranscriptionSegment).filter(TranscriptionSegment.transcription_id == transcription_id).all():
                if seg.speaker and seg.speaker in speaker_map:
                    seg.speaker = speaker_map[seg.speaker]
            db.commit()
            db.close()
            logger.info("Speaker mapping: %s", speaker_map)

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
        logger.info("LLM %d: correction done (%d chars)", transcription_id, len(correction.text))

        # 3) Summary
        logger.info("LLM %d: summarizing...", transcription_id)
        summary = generate_summary(correction.text or full_text, llm_provider)

        db = SessionLocal()
        t = db.query(Transcription).filter(Transcription.id == transcription_id).first()
        if t:
            t.summary = summary.text
            t.status_message = "เสร็จสิ้น"
        db.commit()
        db.close()
        logger.info("LLM %d: done!", transcription_id)

    except Exception as e:
        logger.error("LLM %d failed: %s", transcription_id, e)
        try:
            db = SessionLocal()
            t = db.query(Transcription).filter(Transcription.id == transcription_id).first()
            if t:
                t.status_message = "เสร็จสิ้น (AI ล้มเหลว)"
            db.commit()
            db.close()
        except Exception:
            pass


if __name__ == "__main__":
    tid = int(sys.argv[1])
    raw_json = sys.argv[2]
    provider = sys.argv[3]
    prompt = sys.argv[4] if len(sys.argv) > 4 else None
    main(tid, raw_json, provider, prompt)
