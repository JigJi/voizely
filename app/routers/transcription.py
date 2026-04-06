from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.transcription import TranscriptionStatus
from app.schemas.transcription import (
    TranscriptionCreate,
    TranscriptionProgress,
    TranscriptionResponse,
)
from app.services import audio_service, transcription_service

router = APIRouter(tags=["transcription"])
templates = Jinja2Templates(directory="app/templates")


# --- REST API ---

@router.get("/api/transcriptions")
def list_transcriptions(db: Session = Depends(get_db)):
    from app.models.transcription import TranscriptionSegment
    items = transcription_service.get_all_transcriptions(db)
    return [{
        "id": t.id,
        "audio_file_id": t.audio_file_id,
        "group_id": t.group_id,
        "auto_title": t.auto_title,
        "original_filename": t.audio_file.original_filename if t.audio_file else None,
        "status": t.status.value,
        "progress_percent": t.progress_percent,
        "status_message": t.status_message,
        "created_at": t.created_at.isoformat(),
    } for t in items]


@router.get("/api/transcriptions/{transcription_id}")
def get_transcription_detail(transcription_id: int, db: Session = Depends(get_db)):
    t = transcription_service.get_transcription(db, transcription_id)
    if not t:
        raise HTTPException(status_code=404, detail="Not found")
    return {
        "id": t.id,
        "audio_file_id": t.audio_file_id,
        "group_id": t.group_id,
        "auto_title": t.auto_title,
        "original_filename": t.audio_file.original_filename if t.audio_file else None,
        "status": t.status.value,
        "progress_percent": t.progress_percent,
        "status_message": t.status_message,
        "processing_time_seconds": t.processing_time_seconds,
        "detected_language": t.detected_language,
        "full_text": t.full_text,
        "summary": t.summary,
        "mom_full": t.mom_full,
        "summary_short": t.summary_short,
        "sentiment": t.sentiment,
        "meeting_tone": t.meeting_tone,
        "meeting_type": t.meeting_type,
        "topics": t.topics,
        "action_items": t.action_items,
        "key_decisions": t.key_decisions,
        "open_questions": t.open_questions,
        "speaker_suggestions": t.speaker_suggestions,
        "voiceprint_suggestions": t.voiceprint_suggestions,
        "deepgram_confidence": t.deepgram_confidence,
        "deepgram_cost_usd": t.deepgram_cost_usd,
        "gemini_cost_usd": t.gemini_cost_usd,
        "total_cost_usd": t.total_cost_usd,
        "model_size": t.model_size,
        "created_at": t.created_at.isoformat(),
        "segments": [{
            "id": s.id,
            "segment_index": s.segment_index,
            "start_time": s.start_time,
            "end_time": s.end_time,
            "text": s.text,
            "speaker": s.speaker,
        } for s in t.segments],
    }


@router.post("/api/transcriptions/", response_model=TranscriptionResponse)
def start_transcription(
    audio_id: int,
    body: TranscriptionCreate = TranscriptionCreate(),
    db: Session = Depends(get_db),
):
    audio = audio_service.get_audio(db, audio_id)
    if not audio:
        raise HTTPException(status_code=404, detail="Audio file not found")

    existing = transcription_service.get_transcription_by_audio(db, audio.id)
    if existing:
        return existing

    t = transcription_service.create_transcription(
        db, audio, language=body.language, model_size=body.model_size
    )
    return t


@router.get(
    "/api/transcriptions/{transcription_id}/progress",
    response_model=TranscriptionProgress,
)
def get_progress(transcription_id: int, db: Session = Depends(get_db)):
    t = transcription_service.get_transcription(db, transcription_id)
    if not t:
        raise HTTPException(status_code=404, detail="Transcription not found")
    return TranscriptionProgress(
        id=t.id,
        status=t.status,
        progress_percent=t.progress_percent,
        processing_time_seconds=t.processing_time_seconds,
    )


# --- HTMX Partials ---

@router.post("/htmx/upload", response_class=HTMLResponse)
async def htmx_upload(
    request: Request,
    db: Session = Depends(get_db),
):
    form = await request.form()
    file = form.get("file")
    language = form.get("language") or None
    model_size = form.get("model_size", "Vinxscribe/biodatlab-whisper-th-large-v3-faster")
    initial_prompt = form.get("initial_prompt") or None
    llm_provider = form.get("llm_provider") or None

    if not file or not file.filename:
        return HTMLResponse(
            '<p class="error">กรุณาเลือกไฟล์เสียง</p>', status_code=400
        )

    try:
        audio = await audio_service.save_upload(file, db)
    except ValueError as e:
        return HTMLResponse(f'<p class="error">{e}</p>', status_code=400)

    return HTMLResponse(
        status_code=200,
        headers={"HX-Redirect": f"/audio/{audio.id}/config"},
        content="",
    )


@router.post("/api/transcriptions/{transcription_id}/update-title")
async def update_title(transcription_id: int, request: Request, db: Session = Depends(get_db)):
    body = await request.json()
    title = body.get("title", "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="Missing title")
    t = transcription_service.get_transcription(db, transcription_id)
    if not t:
        raise HTTPException(status_code=404, detail="Not found")
    t.auto_title = title
    db.commit()
    return {"ok": True}


@router.post("/api/audio/{audio_id}/start", response_class=HTMLResponse)
async def start_with_config(
    audio_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    form = await request.form()
    diarization_model = form.get("diarization_model", "pyannote")
    transcription_model = form.get("transcription_model", "gemini")
    group_id = form.get("group_id")

    audio = audio_service.get_audio(db, audio_id)
    if not audio:
        raise HTTPException(status_code=404, detail="Audio not found")

    existing = transcription_service.get_transcription_by_audio(db, audio.id)
    if existing:
        return HTMLResponse(
            status_code=200,
            headers={"HX-Redirect": f"/transcriptions/{existing.id}"},
            content="",
        )

    t = transcription_service.create_transcription(
        db, audio,
        model_size=f"{diarization_model}+{transcription_model}",
    )
    if group_id:
        t.group_id = int(group_id)
        db.commit()

    from fastapi.responses import RedirectResponse
    return RedirectResponse(f"/transcriptions/{t.id}", status_code=303)


@router.delete("/api/transcriptions/{transcription_id}")
def delete_transcription(transcription_id: int, db: Session = Depends(get_db)):
    t = transcription_service.get_transcription(db, transcription_id)
    if not t:
        raise HTTPException(status_code=404, detail="Not found")
    # Delete segments
    from app.models.transcription import TranscriptionSegment
    db.query(TranscriptionSegment).filter(
        TranscriptionSegment.transcription_id == transcription_id
    ).delete()
    # Delete audio file from disk
    from pathlib import Path
    audio = t.audio_file
    file_path = Path(audio.file_path)
    if file_path.exists():
        file_path.unlink()
    # Delete from DB
    db.delete(t)
    db.delete(audio)
    db.commit()
    return {"ok": True}


@router.post("/htmx/delete/{transcription_id}", response_class=HTMLResponse)
def htmx_delete(transcription_id: int, db: Session = Depends(get_db)):
    t = transcription_service.get_transcription(db, transcription_id)
    if t:
        from app.models.transcription import TranscriptionSegment
        from pathlib import Path
        db.query(TranscriptionSegment).filter(
            TranscriptionSegment.transcription_id == transcription_id
        ).delete()
        audio = t.audio_file
        file_path = Path(audio.file_path)
        if file_path.exists():
            file_path.unlink()
        db.delete(t)
        db.delete(audio)
        db.commit()
    return HTMLResponse(
        status_code=200,
        headers={"HX-Redirect": "/"},
        content="",
    )


@router.post("/htmx/retry/{transcription_id}", response_class=HTMLResponse)
def htmx_retry(
    request: Request,
    transcription_id: int,
    db: Session = Depends(get_db),
):
    t = transcription_service.get_transcription(db, transcription_id)
    if not t:
        return HTMLResponse("<p>ไม่พบข้อมูล</p>", status_code=404)

    transcription_service.retry_transcription(db, t)

    return HTMLResponse(
        status_code=200,
        headers={"HX-Redirect": f"/transcriptions/{t.id}"},
        content="",
    )


@router.post("/api/transcriptions/{transcription_id}/rename-speaker")
async def rename_speaker(
    transcription_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    from app.models.transcription import TranscriptionSegment
    body = await request.json()
    old_name = body.get("old_name", "").strip()
    new_name = body.get("new_name", "").strip()

    if not old_name or not new_name:
        raise HTTPException(status_code=400, detail="Missing old_name or new_name")

    t = transcription_service.get_transcription(db, transcription_id)
    if not t:
        raise HTTPException(status_code=404, detail="Not found")

    # Update segments
    segments = db.query(TranscriptionSegment).filter(
        TranscriptionSegment.transcription_id == transcription_id,
        TranscriptionSegment.speaker == old_name,
    ).all()
    for seg in segments:
        seg.speaker = new_name

    # Update all text fields with new name
    for field in ['full_text', 'summary', 'summary_short', 'key_decisions', 'action_items', 'topics', 'open_questions', 'mom_full']:
        val = getattr(t, field, None)
        if val:
            setattr(t, field, val.replace(old_name, new_name))

    # Queue voiceprint enrollment (processed by background worker, not here)
    try:
        import os
        enroll_path = os.path.join(os.path.dirname(__file__), "..", "..", "voiceprint_queue")
        os.makedirs(enroll_path, exist_ok=True)
        import json, time
        queue_file = os.path.join(enroll_path, f"{int(time.time()*1000)}.json")
        with open(queue_file, "w", encoding="utf-8") as f:
            json.dump({
                "transcription_id": transcription_id,
                "audio_path": os.path.abspath(t.audio_file.file_path),
                "old_name": old_name,
                "new_name": new_name,
            }, f)
    except Exception as e:
        import logging
        logging.getLogger("voiceprint").warning("Enrollment queue failed: %s", e)

    # Deduplicate participants in mom_full
    if t.mom_full and "ผู้เข้าร่วม:" in t.mom_full:
        import re
        def dedup_participants(m):
            names = [n.strip() for n in m.group(1).split(",")]
            seen = []
            for n in names:
                if n and n not in seen:
                    seen.append(n)
            return f"**ผู้เข้าร่วม:** {', '.join(seen)}"
        t.mom_full = re.sub(r'\*\*ผู้เข้าร่วม:\*\* (.+)', dedup_participants, t.mom_full)

    db.commit()
    return {"ok": True, "updated": len(segments)}


@router.post("/api/transcriptions/segments/{segment_id}/speaker")
async def update_segment_speaker(
    segment_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    from app.models.transcription import TranscriptionSegment
    body = await request.json()
    new_speaker = body.get("speaker", "").strip()
    if not new_speaker:
        raise HTTPException(status_code=400, detail="Missing speaker")

    seg = db.query(TranscriptionSegment).filter(TranscriptionSegment.id == segment_id).first()
    if not seg:
        raise HTTPException(status_code=404, detail="Segment not found")

    seg.speaker = new_speaker
    db.commit()
    return {"ok": True}


@router.post("/api/transcriptions/{transcription_id}/save-mom")
async def save_mom(
    transcription_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    body = await request.json()
    t = transcription_service.get_transcription(db, transcription_id)
    if not t:
        raise HTTPException(status_code=404, detail="Not found")
    t.summary = body.get("summary", "")
    db.commit()
    return {"ok": True}


@router.post("/api/transcriptions/{transcription_id}/save-mom-full")
async def save_mom_full(
    transcription_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    body = await request.json()
    content = body.get("content", "")
    t = transcription_service.get_transcription(db, transcription_id)
    if not t:
        raise HTTPException(status_code=404, detail="Not found")

    # Save full MoM as-is
    t.mom_full = content

    # Also extract title if present
    import re
    title_match = re.search(r'\*\*หัวข้อ:\*\*\s*(.+)', content)
    if title_match:
        t.auto_title = title_match.group(1).strip()

    db.commit()
    return {"ok": True}


@router.post("/api/transcriptions/{transcription_id}/replace-text")
async def replace_text(
    transcription_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    from app.models.transcription import TranscriptionSegment, CorrectionDict
    body = await request.json()
    find = body.get("find", "")
    replace = body.get("replace", "")

    if not find:
        raise HTTPException(status_code=400, detail="Missing find text")

    t = transcription_service.get_transcription(db, transcription_id)
    if not t:
        raise HTTPException(status_code=404, detail="Not found")

    count = 0
    # Replace in segments
    segments = db.query(TranscriptionSegment).filter(
        TranscriptionSegment.transcription_id == transcription_id
    ).all()
    for seg in segments:
        if find in seg.text:
            count += seg.text.count(find)
            seg.text = seg.text.replace(find, replace)

    # Replace in all text fields
    for field in ['full_text', 'summary', 'summary_short', 'key_decisions',
                  'action_items', 'topics', 'open_questions', 'auto_title', 'mom_full']:
        val = getattr(t, field, None)
        if val and find in val:
            setattr(t, field, val.replace(find, replace))

    # Save to correction dictionary for future auto-correct
    if replace:
        existing = db.query(CorrectionDict).filter(CorrectionDict.wrong == find).first()
        if existing:
            existing.correct = replace
        else:
            db.add(CorrectionDict(wrong=find, correct=replace))

    db.commit()
    return {"ok": True, "count": count}


@router.post("/api/transcriptions/{transcription_id}/regenerate-mom")
def regenerate_mom(transcription_id: int, db: Session = Depends(get_db)):
    from app.models.transcription import TranscriptionSegment
    t = transcription_service.get_transcription(db, transcription_id)
    if not t:
        raise HTTPException(status_code=404, detail="Not found")

    segments = db.query(TranscriptionSegment).filter(
        TranscriptionSegment.transcription_id == transcription_id
    ).order_by(TranscriptionSegment.segment_index).all()

    transcript_text = "\n".join(
        f"{seg.speaker}: {seg.text}" for seg in segments
    )

    # Apply corrections before sending to Gemini
    from app.models.transcription import CorrectionDict
    for c in db.query(CorrectionDict).all():
        transcript_text = transcript_text.replace(c.wrong, c.correct)

    from gemini_worker import generate_analysis, _strip_names_from_mom
    import json

    # Get custom instructions from group
    custom_instructions = None
    if t.group_id:
        from app.models.transcription import TranscriptionGroup
        group = db.query(TranscriptionGroup).filter(TranscriptionGroup.id == t.group_id).first()
        if group and group.custom_instructions:
            custom_instructions = group.custom_instructions

    analysis = generate_analysis(transcript_text, custom_instructions, meeting_date=t.created_at.strftime("%d/%m/%Y"))
    speaker_names = list(dict.fromkeys(seg.speaker for seg in segments))
    mom = _strip_names_from_mom(analysis.get("mom", ""), speaker_names)
    t.summary = mom
    t.auto_title = analysis.get("title", t.auto_title or "")
    t.summary_short = analysis.get("summary_short", "")
    t.sentiment = analysis.get("sentiment", "")
    t.meeting_tone = analysis.get("meeting_tone", "")
    t.meeting_type = analysis.get("meeting_type", "")
    t.topics = json.dumps(analysis.get("topics", []), ensure_ascii=False)
    t.action_items = json.dumps(analysis.get("action_items", []), ensure_ascii=False)
    t.key_decisions = json.dumps(analysis.get("key_decisions", []), ensure_ascii=False)
    t.open_questions = json.dumps(analysis.get("open_questions", []), ensure_ascii=False)
    t.speaker_suggestions = json.dumps(analysis.get("speaker_suggestions", []), ensure_ascii=False)
    t.deepgram_confidence = round(analysis.get("audio_quality", 0) / 100, 4)

    # Rebuild mom_full with metadata
    duration = segments[-1].end_time if segments else 0
    mom_meta = f"### ข้อมูลการประชุม\n"
    mom_meta += f"- **หัวข้อ:** {t.auto_title or t.audio_file.original_filename}\n"
    mom_meta += f"- **วันที่:** {t.created_at.strftime('%d/%m/%Y %H:%M')}\n"
    mom_meta += f"- **ความยาว:** {int(duration // 60)} นาที {int(duration % 60)} วินาที\n"
    mom_meta += f"- **ผู้เข้าร่วม:** {', '.join(speaker_names)}\n"
    t.mom_full = mom_meta + "\n" + mom

    db.commit()
    return {"ok": True}


# --- Export DOCX ---

@router.get("/api/transcriptions/{transcription_id}/export-docx")
def export_docx(transcription_id: int, db: Session = Depends(get_db)):
    from app.models.transcription import TranscriptionSegment
    from fastapi.responses import FileResponse
    from app.services.docx_export import export_mom_docx

    t = transcription_service.get_transcription(db, transcription_id)
    if not t:
        raise HTTPException(status_code=404, detail="Not found")

    segs = db.query(TranscriptionSegment).filter(
        TranscriptionSegment.transcription_id == transcription_id
    ).order_by(TranscriptionSegment.segment_index).all()

    tmp_path = export_mom_docx(t, segs, db)
    filename = f"MOM_{t.auto_title or 'meeting'}_{t.created_at.strftime('%Y%m%d')}.docx"
    return FileResponse(tmp_path,
                        media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                        filename=filename)


# --- Apply Corrections API ---

@router.post("/api/transcriptions/{transcription_id}/apply-corrections")
def apply_corrections(transcription_id: int, db: Session = Depends(get_db)):
    from app.models.transcription import TranscriptionSegment, CorrectionDict
    t = transcription_service.get_transcription(db, transcription_id)
    if not t:
        raise HTTPException(status_code=404, detail="Not found")

    corrections = db.query(CorrectionDict).all()
    if not corrections:
        return {"ok": True, "count": 0}

    count = 0
    # Apply to segments
    segments = db.query(TranscriptionSegment).filter(
        TranscriptionSegment.transcription_id == transcription_id
    ).all()
    for seg in segments:
        for c in corrections:
            if c.wrong in seg.text:
                count += seg.text.count(c.wrong)
                seg.text = seg.text.replace(c.wrong, c.correct)

    # Apply to all text fields
    for field in ['full_text', 'summary', 'summary_short', 'key_decisions',
                  'action_items', 'topics', 'open_questions', 'auto_title', 'mom_full']:
        val = getattr(t, field, None)
        if val:
            for c in corrections:
                if c.wrong in val:
                    count += val.count(c.wrong)
                    val = val.replace(c.wrong, c.correct)
            setattr(t, field, val)

    db.commit()
    return {"ok": True, "count": count}


# --- Speaker Profile API ---

@router.get("/api/speakers")
def list_speakers(db: Session = Depends(get_db)):
    from app.models.transcription import SpeakerProfile
    profiles = db.query(SpeakerProfile).order_by(SpeakerProfile.nickname).all()
    return [{
        "id": p.id,
        "nickname": p.nickname,
        "full_name": p.full_name or "",
        "organization": p.organization or "",
        "department": p.department or "",
        "position": p.position or "",
        "total_seconds": p.total_seconds,
        "num_sessions": p.num_sessions,
    } for p in profiles]


@router.post("/api/speakers")
async def create_speaker(request: Request, db: Session = Depends(get_db)):
    from app.models.transcription import SpeakerProfile
    body = await request.json()
    nickname = body.get("nickname", "").strip()
    if not nickname:
        raise HTTPException(status_code=400, detail="Missing nickname")
    existing = db.query(SpeakerProfile).filter(SpeakerProfile.nickname == nickname).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"ชื่อ '{nickname}' มีอยู่แล้ว กรุณาใช้ชื่ออื่น")
    p = SpeakerProfile(
        nickname=nickname,
        full_name=body.get("full_name", ""),
        organization=body.get("organization", ""),
        department=body.get("department", ""),
        position=body.get("position", ""),
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return {"ok": True, "id": p.id, "nickname": p.nickname}


@router.put("/api/speakers/{speaker_id}")
async def update_speaker(speaker_id: int, request: Request, db: Session = Depends(get_db)):
    from app.models.transcription import SpeakerProfile
    from datetime import datetime, timezone, timedelta
    body = await request.json()
    p = db.query(SpeakerProfile).filter(SpeakerProfile.id == speaker_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Not found")
    for key in ["nickname", "full_name", "organization", "department", "position"]:
        if key in body:
            if key == "nickname":
                new_nick = body[key].strip()
                if new_nick and new_nick != p.nickname:
                    dup = db.query(SpeakerProfile).filter(SpeakerProfile.nickname == new_nick, SpeakerProfile.id != speaker_id).first()
                    if dup:
                        raise HTTPException(status_code=400, detail=f"ชื่อ '{new_nick}' มีอยู่แล้ว กรุณาใช้ชื่ออื่น")
            setattr(p, key, body[key])
    p.updated_at = datetime.now(timezone(timedelta(hours=7)))
    db.commit()
    return {"ok": True}


@router.delete("/api/speakers/{speaker_id}")
def delete_speaker(speaker_id: int, db: Session = Depends(get_db)):
    from app.models.transcription import SpeakerProfile
    p = db.query(SpeakerProfile).filter(SpeakerProfile.id == speaker_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Not found")
    db.delete(p)
    db.commit()
    return {"ok": True}


# Keep old endpoint for backward compatibility
@router.get("/api/voiceprints")
def list_voiceprints_api(db: Session = Depends(get_db)):
    from app.models.transcription import SpeakerProfile
    profiles = db.query(SpeakerProfile).order_by(SpeakerProfile.nickname).all()
    return [{
        "name": p.nickname,
        "full_name": p.full_name or "",
        "organization": p.organization or "",
        "department": p.department or "",
        "position": p.position or "",
        "total_seconds": p.total_seconds,
        "num_sessions": p.num_sessions,
    } for p in profiles]


@router.put("/api/voiceprints/{speaker_name}")
async def update_voiceprint_api(speaker_name: str, request: Request, db: Session = Depends(get_db)):
    from app.models.transcription import SpeakerProfile
    from datetime import datetime, timezone, timedelta
    body = await request.json()
    p = db.query(SpeakerProfile).filter(SpeakerProfile.nickname == speaker_name).first()
    if not p:
        # Create new if not exists
        p = SpeakerProfile(nickname=speaker_name)
        db.add(p)
    for key in ["full_name", "organization", "department", "position"]:
        if key in body:
            setattr(p, key, body[key])
    p.updated_at = datetime.now(timezone(timedelta(hours=7)))
    db.commit()
    return {"ok": True}


@router.delete("/api/voiceprints/{speaker_name}")
def delete_voiceprint_api(speaker_name: str, db: Session = Depends(get_db)):
    from app.models.transcription import SpeakerProfile
    p = db.query(SpeakerProfile).filter(SpeakerProfile.nickname == speaker_name).first()
    if not p:
        raise HTTPException(status_code=404, detail="Not found")
    db.delete(p)
    db.commit()
    return {"ok": True}


# --- Correction Dictionary API ---

@router.get("/api/corrections")
def list_corrections(db: Session = Depends(get_db)):
    from app.models.transcription import CorrectionDict
    items = db.query(CorrectionDict).order_by(CorrectionDict.created_at.desc()).all()
    return [{"id": c.id, "wrong": c.wrong, "correct": c.correct} for c in items]


@router.post("/api/corrections")
async def add_correction(request: Request, db: Session = Depends(get_db)):
    from app.models.transcription import CorrectionDict
    body = await request.json()
    wrong = body.get("wrong", "").strip()
    correct = body.get("correct", "").strip()
    if not wrong or not correct:
        raise HTTPException(status_code=400, detail="Missing wrong or correct")
    existing = db.query(CorrectionDict).filter(CorrectionDict.wrong == wrong).first()
    if existing:
        existing.correct = correct
    else:
        db.add(CorrectionDict(wrong=wrong, correct=correct))
    db.commit()
    return {"ok": True}


@router.put("/api/corrections/{correction_id}")
async def update_correction(correction_id: int, request: Request, db: Session = Depends(get_db)):
    from app.models.transcription import CorrectionDict
    body = await request.json()
    c = db.query(CorrectionDict).filter(CorrectionDict.id == correction_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Not found")
    if "wrong" in body:
        c.wrong = body["wrong"].strip()
    if "correct" in body:
        c.correct = body["correct"].strip()
    db.commit()
    return {"ok": True}


@router.delete("/api/corrections/{correction_id}")
def delete_correction(correction_id: int, db: Session = Depends(get_db)):
    from app.models.transcription import CorrectionDict
    c = db.query(CorrectionDict).filter(CorrectionDict.id == correction_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Not found")
    db.delete(c)
    db.commit()
    return {"ok": True}


@router.get("/htmx/transcription-progress/{transcription_id}", response_class=HTMLResponse)
def htmx_progress(
    request: Request,
    transcription_id: int,
    db: Session = Depends(get_db),
):
    t = transcription_service.get_transcription(db, transcription_id)
    if not t:
        return HTMLResponse("<p>ไม่พบข้อมูล</p>", status_code=404)

    return templates.TemplateResponse(
        "partials/progress_bar.html",
        {"request": request, "transcription": t},
    )


@router.get("/htmx/transcription-result/{transcription_id}", response_class=HTMLResponse)
def htmx_result(
    request: Request,
    transcription_id: int,
    db: Session = Depends(get_db),
):
    t = transcription_service.get_transcription(db, transcription_id)
    if not t:
        return HTMLResponse("<p>ไม่พบข้อมูล</p>", status_code=404)

    return templates.TemplateResponse(
        "partials/transcription_result.html",
        {"request": request, "transcription": t},
    )
