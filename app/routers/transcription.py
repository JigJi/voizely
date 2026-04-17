from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.transcription import TranscriptionStatus
from app.models.user import User
from app.schemas.transcription import (
    TranscriptionCreate,
    TranscriptionProgress,
    TranscriptionResponse,
)
from app.services import audio_service, transcription_service
from app.routers.auth import get_current_user

router = APIRouter(tags=["transcription"])
templates = Jinja2Templates(directory="app/templates")


def _check_owner(t, current_user: User, db: Session | None = None):
    """Raise 403 if user doesn't own this transcription and isn't a meeting attendee."""
    if current_user.role == "ADMIN":
        return
    if t.user_id is None or t.user_id == current_user.id:
        return
    if db:
        from app.models.meeting import MeetingRecording
        meeting = db.query(MeetingRecording).filter(MeetingRecording.transcription_id == t.id).first()
        if meeting:
            return
    raise HTTPException(status_code=403, detail="Access denied")


# --- REST API ---

@router.get("/api/transcriptions")
def list_transcriptions(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    from app.models.transcription import TranscriptionSegment
    items = transcription_service.get_all_transcriptions(db, user_id=current_user.id)
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
def get_transcription_detail(transcription_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    t = transcription_service.get_transcription(db, transcription_id)
    if not t:
        raise HTTPException(status_code=404, detail="Not found")
    _check_owner(t, current_user, db)
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
    current_user: User = Depends(get_current_user),
):
    audio = audio_service.get_audio(db, audio_id)
    if not audio:
        raise HTTPException(status_code=404, detail="Audio file not found")

    existing = transcription_service.get_transcription_by_audio(db, audio.id)
    if existing:
        return existing

    t = transcription_service.create_transcription(
        db, audio, language=body.language, model_size=body.model_size,
        user_id=current_user.id,
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
        status_message=t.status_message,
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
async def update_title(transcription_id: int, request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    body = await request.json()
    title = body.get("title", "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="Missing title")
    t = transcription_service.get_transcription(db, transcription_id)
    if not t:
        raise HTTPException(status_code=404, detail="Not found")
    _check_owner(t, current_user, db)
    old_title = t.auto_title or ""
    t.auto_title = title
    # Update title in mom_full header too
    if t.mom_full and old_title:
        t.mom_full = t.mom_full.replace(f"**หัวข้อ:** {old_title}", f"**หัวข้อ:** {title}")
    elif t.mom_full:
        import re
        t.mom_full = re.sub(r'\*\*หัวข้อ:\*\* .+', f'**หัวข้อ:** {title}', t.mom_full)
    db.commit()
    return {"ok": True}


@router.post("/api/audio/{audio_id}/start", response_class=HTMLResponse)
async def start_with_config(
    audio_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
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
        user_id=current_user.id,
    )
    if group_id:
        t.group_id = int(group_id)
    else:
        from app.models.transcription import TranscriptionGroup
        default_group = db.query(TranscriptionGroup).filter(TranscriptionGroup.is_default == True).first()
        if default_group:
            t.group_id = default_group.id
    db.commit()

    from fastapi.responses import RedirectResponse
    return RedirectResponse(f"/transcriptions/{t.id}", status_code=303)


@router.delete("/api/transcriptions/{transcription_id}")
def delete_transcription(transcription_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    t = transcription_service.get_transcription(db, transcription_id)
    if not t:
        raise HTTPException(status_code=404, detail="Not found")
    _check_owner(t, current_user, db)
    # Delete segments
    from app.models.transcription import TranscriptionSegment
    db.query(TranscriptionSegment).filter(
        TranscriptionSegment.transcription_id == transcription_id
    ).delete()
    # Clear meeting_recording FK if linked
    from app.models.meeting import MeetingRecording
    for mr in db.query(MeetingRecording).filter(MeetingRecording.transcription_id == transcription_id).all():
        mr.transcription_id = None
        mr.status = "discovered"
    # Delete audio file from disk
    from pathlib import Path
    audio = t.audio_file
    if audio:
        file_path = Path(audio.file_path)
        if file_path.exists():
            file_path.unlink()
        # Clear meeting_recording audio FK too
        for mr in db.query(MeetingRecording).filter(MeetingRecording.audio_file_id == audio.id).all():
            mr.audio_file_id = None
        db.delete(audio)
    db.delete(t)
    db.commit()
    return {"ok": True}


@router.post("/htmx/delete/{transcription_id}", response_class=HTMLResponse)
def htmx_delete(transcription_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    t = transcription_service.get_transcription(db, transcription_id)
    if t:
        _check_owner(t, current_user, db)
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
    current_user: User = Depends(get_current_user),
):
    t = transcription_service.get_transcription(db, transcription_id)
    if not t:
        return HTMLResponse("<p>ไม่พบข้อมูล</p>", status_code=404)
    _check_owner(t, current_user, db)

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
    current_user: User = Depends(get_current_user),
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
    _check_owner(t, current_user, db)

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
    current_user: User = Depends(get_current_user),
):
    from app.models.transcription import TranscriptionSegment
    body = await request.json()
    new_speaker = body.get("speaker", "").strip()
    if not new_speaker:
        raise HTTPException(status_code=400, detail="Missing speaker")

    seg = db.query(TranscriptionSegment).filter(TranscriptionSegment.id == segment_id).first()
    if not seg:
        raise HTTPException(status_code=404, detail="Segment not found")

    # Check owner via parent transcription
    t = transcription_service.get_transcription(db, seg.transcription_id)
    if t:
        _check_owner(t, current_user, db)

    seg.speaker = new_speaker
    db.commit()
    return {"ok": True}


@router.post("/api/transcriptions/{transcription_id}/save-mom")
async def save_mom(
    transcription_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    body = await request.json()
    t = transcription_service.get_transcription(db, transcription_id)
    if not t:
        raise HTTPException(status_code=404, detail="Not found")
    _check_owner(t, current_user, db)
    t.summary = body.get("summary", "")
    db.commit()
    return {"ok": True}


@router.post("/api/transcriptions/{transcription_id}/save-mom-full")
async def save_mom_full(
    transcription_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    body = await request.json()
    content = body.get("content", "")
    t = transcription_service.get_transcription(db, transcription_id)
    if not t:
        raise HTTPException(status_code=404, detail="Not found")
    _check_owner(t, current_user, db)

    # Save full MoM as-is
    t.mom_full = content

    # Sync fields from MoM content
    import re
    title_match = re.search(r'\*\*หัวข้อ:\*\*\s*(.+)', content)
    if title_match:
        t.auto_title = title_match.group(1).strip()

    # Extract summary (everything after ### สรุปภาพรวม until next ###)
    summary_match = re.search(r'### สรุปภาพรวม\n(.*?)(?=\n### |\Z)', content, re.DOTALL)
    if summary_match:
        t.summary_short = summary_match.group(1).strip()[:200]

    # Also save the non-info sections as summary
    sections = content.split('### ')
    mom_sections = []
    for s in sections:
        if s.strip() and not s.startswith('ข้อมูลการประชุม'):
            mom_sections.append('### ' + s)
    t.summary = '\n'.join(mom_sections).strip()

    db.commit()
    return {"ok": True}


@router.post("/api/transcriptions/{transcription_id}/replace-text")
async def replace_text(
    transcription_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.models.transcription import TranscriptionSegment, CorrectionDict
    body = await request.json()
    find = body.get("find", "")
    replace = body.get("replace", "")

    if not find:
        raise HTTPException(status_code=400, detail="Missing find text")
    if not replace:
        raise HTTPException(status_code=400, detail="กรุณาระบุข้อความที่ต้องการแก้ไข ไม่สามารถแทนที่ด้วยค่าว่างได้")

    t = transcription_service.get_transcription(db, transcription_id)
    if not t:
        raise HTTPException(status_code=404, detail="Not found")
    _check_owner(t, current_user, db)

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

    # Don't save to correction dictionary — this is a one-time fix for this file only
    # Users can add permanent corrections via the Correction Dictionary page

    db.commit()
    return {"ok": True, "count": count}


@router.post("/api/transcriptions/{transcription_id}/regenerate-mom")
def regenerate_mom(transcription_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    from app.models.transcription import TranscriptionSegment
    t = transcription_service.get_transcription(db, transcription_id)
    if not t:
        raise HTTPException(status_code=404, detail="Not found")
    _check_owner(t, current_user, db)

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

    from gemini_worker import _fix_mom_style
    analysis = generate_analysis(transcript_text, custom_instructions, meeting_date=t.created_at.strftime("%d/%m/%Y"))
    if not analysis or not analysis.get("mom"):
        raise HTTPException(status_code=502, detail="MoM generation failed — Gemini returned empty result")
    speaker_names = list(dict.fromkeys(seg.speaker for seg in segments))
    mom = _fix_mom_style(analysis.get("mom", ""))
    mom = _strip_names_from_mom(mom, speaker_names)
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
def export_docx(transcription_id: int, token: str = None, db: Session = Depends(get_db)):
    from app.models.transcription import TranscriptionSegment
    from fastapi.responses import FileResponse
    from app.services.docx_export import export_mom_docx
    from app.core.security import decode_token

    # Auth via query param (browser download can't send Bearer header)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    username = decode_token(token)
    if not username:
        raise HTTPException(status_code=401, detail="Invalid token")
    current_user = db.query(User).filter(User.username == username).first()
    if not current_user:
        raise HTTPException(status_code=401, detail="User not found")

    t = transcription_service.get_transcription(db, transcription_id)
    if not t:
        raise HTTPException(status_code=404, detail="Not found")
    _check_owner(t, current_user, db)

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
def apply_corrections(transcription_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    from app.models.transcription import TranscriptionSegment, CorrectionDict
    t = transcription_service.get_transcription(db, transcription_id)
    if not t:
        raise HTTPException(status_code=404, detail="Not found")
    _check_owner(t, current_user, db)

    corrections = db.query(CorrectionDict).filter(CorrectionDict.user_id == current_user.id).all()
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
def list_speakers(source: str | None = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    from app.models.transcription import SpeakerProfile
    from sqlalchemy import or_
    q = db.query(SpeakerProfile)
    if source:
        q = q.filter(SpeakerProfile.source == source)
    # Manual speakers: show only current user's
    # AD speakers: show all
    if source == "manual":
        q = q.filter(SpeakerProfile.user_id == current_user.id)
    elif not source:
        # No filter: AD all + manual only current user's
        q = q.filter(or_(
            SpeakerProfile.source == "ad",
            SpeakerProfile.user_id == current_user.id,
        ))
    profiles = q.order_by(SpeakerProfile.nickname).all()
    return [{
        "id": p.id,
        "nickname": p.nickname,
        "source": getattr(p, 'source', 'manual'),
        "email": p.email or "",
        "full_name": p.full_name or "",
        "organization": p.organization or "",
        "department": p.department or "",
        "position": p.position or "",
        "total_seconds": p.total_seconds,
        "num_sessions": p.num_sessions,
    } for p in profiles]


@router.post("/api/speakers")
async def create_speaker(request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    from app.models.transcription import SpeakerProfile
    body = await request.json()
    nickname = body.get("nickname", "").strip()
    if not nickname:
        raise HTTPException(status_code=400, detail="Missing nickname")
    existing = db.query(SpeakerProfile).filter(
        SpeakerProfile.nickname == nickname,
        SpeakerProfile.user_id == current_user.id,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"ชื่อ '{nickname}' มีอยู่แล้ว กรุณาใช้ชื่ออื่น")
    p = SpeakerProfile(
        nickname=nickname,
        user_id=current_user.id,
        email=body.get("email", ""),
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
async def update_speaker(speaker_id: int, request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    from app.models.transcription import SpeakerProfile
    from datetime import datetime, timezone, timedelta
    body = await request.json()
    p = db.query(SpeakerProfile).filter(SpeakerProfile.id == speaker_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Not found")
    if getattr(p, 'source', 'manual') == 'ad':
        raise HTTPException(status_code=403, detail="ข้อมูลพนักงานจาก AD ไม่สามารถแก้ไขได้")
    if p.user_id and p.user_id != current_user.id and current_user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Access denied")
    for key in ["nickname", "email", "full_name", "organization", "department", "position"]:
        if key in body:
            if key == "nickname":
                new_nick = body[key].strip()
                if new_nick and new_nick != p.nickname:
                    dup = db.query(SpeakerProfile).filter(SpeakerProfile.nickname == new_nick, SpeakerProfile.id != speaker_id, SpeakerProfile.user_id == current_user.id).first()
                    if dup:
                        raise HTTPException(status_code=400, detail=f"ชื่อ '{new_nick}' มีอยู่แล้ว กรุณาใช้ชื่ออื่น")
            setattr(p, key, body[key])
    p.updated_at = datetime.now(timezone(timedelta(hours=7)))
    db.commit()
    return {"ok": True}


@router.delete("/api/speakers/{speaker_id}")
def delete_speaker(speaker_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    from app.models.transcription import SpeakerProfile
    p = db.query(SpeakerProfile).filter(SpeakerProfile.id == speaker_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Not found")
    if getattr(p, 'source', 'manual') == 'ad':
        raise HTTPException(status_code=403, detail="ข้อมูลพนักงานจาก AD ไม่สามารถลบได้")
    if p.user_id and p.user_id != current_user.id and current_user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Access denied")
    db.delete(p)
    db.commit()
    return {"ok": True}


# Keep old endpoint for backward compatibility
@router.get("/api/voiceprints")
def list_voiceprints_api(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
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
async def update_voiceprint_api(speaker_name: str, request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
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
def delete_voiceprint_api(speaker_name: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    from app.models.transcription import SpeakerProfile
    p = db.query(SpeakerProfile).filter(SpeakerProfile.nickname == speaker_name).first()
    if not p:
        raise HTTPException(status_code=404, detail="Not found")
    db.delete(p)
    db.commit()
    return {"ok": True}


# --- Correction Dictionary API ---

@router.get("/api/corrections")
def list_corrections(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    from app.models.transcription import CorrectionDict
    items = db.query(CorrectionDict).filter(CorrectionDict.user_id == current_user.id).order_by(CorrectionDict.created_at.desc()).all()
    return [{"id": c.id, "wrong": c.wrong, "correct": c.correct} for c in items]


@router.post("/api/corrections")
async def add_correction(request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    from app.models.transcription import CorrectionDict
    body = await request.json()
    wrong = body.get("wrong", "").strip()
    correct = body.get("correct", "").strip()
    if not wrong or not correct:
        raise HTTPException(status_code=400, detail="Missing wrong or correct")
    existing = db.query(CorrectionDict).filter(CorrectionDict.wrong == wrong, CorrectionDict.user_id == current_user.id).first()
    if existing:
        existing.correct = correct
    else:
        db.add(CorrectionDict(wrong=wrong, correct=correct, user_id=current_user.id))
    db.commit()
    return {"ok": True}


@router.put("/api/corrections/{correction_id}")
async def update_correction(correction_id: int, request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
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
def delete_correction(correction_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
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
