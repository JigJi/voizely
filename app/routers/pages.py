import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import transcription_service

router = APIRouter(tags=["pages"])
templates = Jinja2Templates(directory="app/templates")
templates.env.filters["from_json"] = lambda s: json.loads(s) if s else []


def _sidebar_context(db):
    """Get groups + transcriptions for sidebar."""
    groups = transcription_service.get_grouped_transcriptions(db)
    transcriptions = transcription_service.get_all_transcriptions(db)
    return {"groups": groups, "transcriptions": transcriptions}


@router.get("/", response_class=HTMLResponse)
def home(request: Request, db: Session = Depends(get_db)):
    transcriptions = transcription_service.get_all_transcriptions(db)
    # If there are transcriptions, redirect to the latest one
    if transcriptions:
        return RedirectResponse(f"/transcriptions/{transcriptions[0].id}", status_code=302)
    ctx = _sidebar_context(db)
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "active_id": None, **ctx},
    )


@router.get("/audio/{audio_id}/config", response_class=HTMLResponse)
def audio_config(request: Request, audio_id: int, db: Session = Depends(get_db)):
    from app.models.audio import AudioFile
    audio = db.query(AudioFile).filter(AudioFile.id == audio_id).first()
    if not audio:
        return HTMLResponse("<h1>ไม่พบไฟล์เสียง</h1>", status_code=404)
    ctx = _sidebar_context(db)
    return templates.TemplateResponse(
        "audio_config.html",
        {"request": request, "audio": audio, "active_id": None, **ctx},
    )


@router.get("/voiceprints", response_class=HTMLResponse)
def voiceprints_page(request: Request, db: Session = Depends(get_db)):
    ctx = _sidebar_context(db)
    return templates.TemplateResponse(
        "voiceprints.html",
        {"request": request, "active_id": None, **ctx},
    )


@router.get("/groups/{group_id}", response_class=HTMLResponse)
def group_settings(request: Request, group_id: int, db: Session = Depends(get_db)):
    from app.models.transcription import TranscriptionGroup
    group = db.query(TranscriptionGroup).filter(TranscriptionGroup.id == group_id).first()
    if not group:
        return HTMLResponse("<h1>ไม่พบกลุ่ม</h1>", status_code=404)
    ctx = _sidebar_context(db)
    return templates.TemplateResponse(
        "group_settings.html",
        {"request": request, "group": group, "active_id": None, **ctx},
    )


@router.get("/corrections", response_class=HTMLResponse)
def corrections_page(request: Request, db: Session = Depends(get_db)):
    ctx = _sidebar_context(db)
    return templates.TemplateResponse(
        "corrections.html",
        {"request": request, "active_id": None, **ctx},
    )


@router.get("/transcriptions/{transcription_id}", response_class=HTMLResponse)
def transcription_detail(
    request: Request,
    transcription_id: int,
    db: Session = Depends(get_db),
):
    t = transcription_service.get_transcription(db, transcription_id)
    if not t:
        return HTMLResponse("<h1>ไม่พบข้อมูล</h1>", status_code=404)
    ctx = _sidebar_context(db)
    has_typhoon = any(s.clean_text for s in t.segments)
    has_gpt = any(s.clean_text_alt for s in t.segments)

    # Speaker stats
    speaker_durations = {}
    total_duration = 0
    for seg in t.segments:
        spk = seg.speaker or "Speaker 1"
        dur = max(0, seg.end_time - seg.start_time)
        speaker_durations[spk] = speaker_durations.get(spk, 0) + dur
        total_duration += dur

    speaker_stats = []
    for spk, dur in speaker_durations.items():
        pct = round(dur / total_duration * 100) if total_duration > 0 else 0
        speaker_stats.append({"name": spk, "duration": dur, "percent": pct})
    speaker_stats.sort(key=lambda x: x["duration"], reverse=True)

    return templates.TemplateResponse(
        "transcription.html",
        {
            "request": request,
            "transcription": t,
            "active_id": transcription_id,
            "has_typhoon": has_typhoon,
            "has_gpt": has_gpt,
            "speaker_stats": speaker_stats,
            "total_duration": total_duration,
            **ctx,
        },
    )
