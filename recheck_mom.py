"""Recheck completed transcriptions with empty MoM and re-run analysis."""
import json
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from app.database import SessionLocal
from app.models.transcription import Transcription, TranscriptionSegment, TranscriptionStatus, TranscriptionGroup
from gemini_worker import generate_analysis, _fix_mom_style, _strip_names_from_mom, _clean_speaker_suggestions


def find_broken():
    db = SessionLocal()
    broken = db.query(Transcription).filter(
        Transcription.status == TranscriptionStatus.completed,
        (Transcription.summary == None) | (Transcription.summary == ""),
    ).all()
    results = []
    for t in broken:
        seg_count = db.query(TranscriptionSegment).filter(
            TranscriptionSegment.transcription_id == t.id
        ).count()
        results.append((t.id, seg_count, t.auto_title or t.audio_file.original_filename if t.audio_file else "?"))
    db.close()
    return results


def recheck(transcription_id: int):
    db = SessionLocal()
    t = db.query(Transcription).filter(Transcription.id == transcription_id).first()
    if not t:
        print(f"[ERROR] #{transcription_id} not found")
        db.close()
        return False

    segs = db.query(TranscriptionSegment).filter(
        TranscriptionSegment.transcription_id == transcription_id
    ).order_by(TranscriptionSegment.start_time).all()

    if not segs:
        print(f"[SKIP] #{transcription_id} no segments")
        db.close()
        return False

    print(f"[START] #{transcription_id} ({len(segs)} segments)")

    transcript_text = "\n".join(f"{s.speaker}: {s.text}" for s in segs)
    speaker_names = list(set(s.speaker for s in segs))

    custom_instructions = None
    if t.group_id:
        group = db.query(TranscriptionGroup).filter(TranscriptionGroup.id == t.group_id).first()
        if group and group.custom_instructions:
            custom_instructions = group.custom_instructions

    meeting_date = t.created_at.strftime("%d/%m/%Y") if t.created_at else None

    try:
        analysis = generate_analysis(transcript_text, custom_instructions, meeting_date=meeting_date)
    except Exception as e:
        print(f"[ERROR] #{transcription_id} generate_analysis failed: {e}")
        db.close()
        return False

    mom = analysis.get("mom", "")
    mom = _fix_mom_style(mom)
    mom = _strip_names_from_mom(mom, speaker_names)

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
    t.speaker_suggestions = json.dumps(_clean_speaker_suggestions(analysis.get("speaker_suggestions", [])), ensure_ascii=False)
    t.deepgram_confidence = round(analysis.get("audio_quality", 0) / 100, 4)

    # Rebuild mom_full
    speakers_list = list(dict.fromkeys(s.speaker for s in segs))
    duration = segs[-1].end_time if segs[-1].end_time else segs[-1].start_time
    mom_meta = f"### ข้อมูลการประชุม\n"
    mom_meta += f"- **หัวข้อ:** {t.auto_title or (t.audio_file.original_filename if t.audio_file else '')}\n"
    mom_meta += f"- **วันที่:** {t.created_at.strftime('%d/%m/%Y %H:%M') if t.created_at else ''}\n"
    mom_meta += f"- **ความยาว:** {int(duration // 60)} นาที {int(duration % 60)} วินาที\n"
    mom_meta += f"- **ผู้เข้าร่วม:** {', '.join(speakers_list)}\n"
    t.mom_full = mom_meta + "\n" + (t.summary or "")

    db.commit()
    print(f"[OK] #{transcription_id} title=\"{t.auto_title}\" summary={len(t.summary)} chars")
    db.close()
    return True


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Recheck specific ID(s)
        for tid in sys.argv[1:]:
            recheck(int(tid))
    else:
        # Find and recheck all broken
        broken = find_broken()
        if not broken:
            print("No broken transcriptions found.")
        else:
            print(f"Found {len(broken)} broken transcription(s):")
            for tid, seg_count, name in broken:
                print(f"  #{tid} ({seg_count} segs) {name}")
            print()
            for tid, seg_count, name in broken:
                if seg_count > 0:
                    recheck(tid)
                else:
                    print(f"[SKIP] #{tid} no segments")
