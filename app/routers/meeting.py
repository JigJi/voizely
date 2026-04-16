import json
import logging
import os
from datetime import datetime, date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.meeting import MeetingRecording, MeetingRecordingStatus, UserCalendarCache
from app.models.transcription import Transcription, TranscriptionStatus
from app.models.audio import AudioFile, AudioStatus
from app.models.user import User
from app.routers.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(tags=["meetings"])


def _get_user_meeting_subjects(db: Session, user: User) -> set[str]:
    """Get meeting subjects this user attended (last 30 days) using cache.

    Past days are cached forever (meetings don't change retroactively).
    Only today's events are fetched fresh from Graph API each time.
    """
    today = date.today()
    start_date = today - timedelta(days=30)

    # 1. Get cached subjects for past days (start_date to yesterday)
    cached = (
        db.query(UserCalendarCache.subject)
        .filter(
            UserCalendarCache.user_id == user.id,
            UserCalendarCache.cached_date >= start_date,
            UserCalendarCache.cached_date < today,
        )
        .all()
    )
    subjects = {row.subject.strip().lower() for row in cached}

    # 2. Find which past days are NOT cached yet → fetch from Graph API
    cached_dates = set(
        row[0] for row in
        db.query(UserCalendarCache.cached_date)
        .filter(
            UserCalendarCache.user_id == user.id,
            UserCalendarCache.cached_date >= start_date,
            UserCalendarCache.cached_date < today,
        )
        .distinct()
        .all()
    )
    missing_dates = [start_date + timedelta(days=i)
                     for i in range((today - start_date).days)
                     if (start_date + timedelta(days=i)) not in cached_dates]

    # 3. Always fetch today fresh (today's meetings can still change)
    fetch_dates = missing_dates + [today]

    if fetch_dates and user.email and "@local" not in user.email:
        try:
            from app.services.meeting_platforms.teams_client import TeamsClient
            client = TeamsClient()

            # Batch into one API call: min(fetch_dates) to today
            fetch_start = min(fetch_dates)
            events = client.get_user_calendar_subjects(user.email, days=(today - fetch_start).days + 1)

            # Cache past-day events (not today — today refreshes each time)
            for evt in events:
                subj = evt["subject"].strip()
                subjects.add(subj.lower())

                evt_date = evt["start_time"].date() if evt.get("start_time") else None
                if evt_date and evt_date < today and evt_date in missing_dates:
                    existing = (
                        db.query(UserCalendarCache)
                        .filter(
                            UserCalendarCache.user_id == user.id,
                            UserCalendarCache.subject == subj,
                            UserCalendarCache.event_start == evt["start_time"],
                        )
                        .first()
                    )
                    if not existing:
                        db.add(UserCalendarCache(
                            user_id=user.id,
                            subject=subj,
                            event_start=evt["start_time"],
                            cached_date=evt_date,
                        ))

            # Mark missing dates as cached (even if no events — so we don't refetch)
            for d in missing_dates:
                if d not in cached_dates:
                    has_any = (
                        db.query(UserCalendarCache)
                        .filter(UserCalendarCache.user_id == user.id, UserCalendarCache.cached_date == d)
                        .first()
                    )
                    if not has_any:
                        # Insert a sentinel so we know this date was checked
                        db.add(UserCalendarCache(
                            user_id=user.id,
                            subject="__no_events__",
                            event_start=datetime(d.year, d.month, d.day),
                            cached_date=d,
                        ))
            db.commit()
        except Exception as e:
            logger.error("Calendar fetch failed for %s: %s", user.email, e)
            db.rollback()

    return subjects


@router.get("/api/meetings")
def list_meetings(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """List meeting recordings that match user's calendar events."""
    if current_user.role == "ADMIN":
        items = (
            db.query(MeetingRecording)
            .order_by(MeetingRecording.discovered_at.desc())
            .all()
        )
    else:
        # Get subjects from user's calendar (cached)
        user_subjects = _get_user_meeting_subjects(db, current_user)

        # Get all recordings and match by subject
        all_recordings = (
            db.query(MeetingRecording)
            .order_by(MeetingRecording.discovered_at.desc())
            .all()
        )
        items = [
            m for m in all_recordings
            if (m.meeting_subject or "").strip().lower() in user_subjects
        ]
    return [_meeting_to_dict(m, db) for m in items]


@router.get("/api/meetings/{meeting_id}")
def get_meeting(meeting_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    m = db.query(MeetingRecording).filter(MeetingRecording.id == meeting_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Not found")
    if current_user.role != "ADMIN":
        user_subjects = _get_user_meeting_subjects(db, current_user)
        if (m.meeting_subject or "").strip().lower() not in user_subjects:
            raise HTTPException(status_code=403, detail="Access denied")
    return _meeting_to_dict(m, db)


@router.get("/api/meetings/{meeting_id}/download")
def download_meeting_audio(meeting_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Download the audio file of a meeting recording. Access-controlled by calendar match."""
    m = db.query(MeetingRecording).filter(MeetingRecording.id == meeting_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Not found")
    if current_user.role != "ADMIN":
        user_subjects = _get_user_meeting_subjects(db, current_user)
        if (m.meeting_subject or "").strip().lower() not in user_subjects:
            raise HTTPException(status_code=403, detail="Access denied")
    if not m.audio_file_id:
        raise HTTPException(status_code=400, detail="ยังไม่มีไฟล์เสียง")
    audio = db.query(AudioFile).filter(AudioFile.id == m.audio_file_id).first()
    if not audio or not audio.file_path or not os.path.exists(audio.file_path):
        raise HTTPException(status_code=404, detail="ไฟล์เสียงถูกลบไปแล้ว")
    subject = (m.meeting_subject or "recording").strip() or "recording"
    ext = os.path.splitext(audio.original_filename or audio.file_path)[1] or ".mp4"
    safe_name = "".join(c for c in subject if c not in '<>:"/\\|?*').strip()[:100] or "recording"
    return FileResponse(
        audio.file_path,
        media_type=audio.mime_type or "application/octet-stream",
        filename=f"{safe_name}{ext}",
    )


@router.post("/api/meetings/{meeting_id}/retranscribe")
async def retranscribe_meeting(meeting_id: int, request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Re-transcribe an already-completed meeting with a (possibly different) model."""
    from app.models.transcription import TranscriptionSegment, TranscriptionGroup
    from app.config import settings

    m = db.query(MeetingRecording).filter(MeetingRecording.id == meeting_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Not found")
    if m.status == MeetingRecordingStatus.queued or m.status == MeetingRecordingStatus.downloading:
        raise HTTPException(status_code=400, detail="กำลังประมวลผลอยู่ รอให้เสร็จก่อน")
    if not m.transcription_id:
        raise HTTPException(status_code=400, detail="ยังไม่เคยถอดเสียง — ใช้ process แทน")

    body = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}
    model_size = body.get("model_size") or settings.MS_TEAMS_RECORDING_MODEL
    group_id = body.get("group_id")

    t = db.query(Transcription).filter(Transcription.id == m.transcription_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Transcription not found")

    # Wipe old segments + analysis
    db.query(TranscriptionSegment).filter(TranscriptionSegment.transcription_id == t.id).delete()
    t.status = TranscriptionStatus.pending
    t.progress_percent = 0
    t.status_message = "รอประมวลผล (re-transcribe)"
    t.full_text = None
    t.summary = None
    t.mom_full = None
    t.auto_title = None
    t.summary_short = None
    t.sentiment = None
    t.meeting_tone = None
    t.meeting_type = None
    t.topics = None
    t.action_items = None
    t.key_decisions = None
    t.open_questions = None
    t.speaker_suggestions = None
    t.voiceprint_suggestions = None
    t.model_size = model_size
    if group_id:
        t.group_id = int(group_id)

    # Reset audio status
    audio = db.query(AudioFile).filter(AudioFile.id == m.audio_file_id).first()
    if audio:
        audio.status = AudioStatus.processing
        audio.error_message = None

    m.status = MeetingRecordingStatus.queued
    m.processed_by = current_user.id
    m.error_message = None
    db.commit()

    return {"ok": True, "transcription_id": t.id, "model_size": model_size}


@router.post("/api/meetings/{meeting_id}/process")
async def process_meeting(meeting_id: int, request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Manually trigger processing for a skipped/failed recording."""
    from app.models.transcription import TranscriptionGroup

    m = db.query(MeetingRecording).filter(MeetingRecording.id == meeting_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Not found")
    # Lock: reject if already queued or completed
    if m.status == MeetingRecordingStatus.queued:
        raise HTTPException(status_code=400, detail="กำลังประมวลผลอยู่แล้ว ไม่สามารถเริ่มซ้ำได้")
    if m.status == MeetingRecordingStatus.completed:
        raise HTTPException(status_code=400, detail="ประมวลผลเสร็จแล้ว ไม่สามารถเริ่มซ้ำได้")
    if m.status not in (MeetingRecordingStatus.skipped, MeetingRecordingStatus.failed, MeetingRecordingStatus.discovered):
        raise HTTPException(status_code=400, detail=f"Cannot process recording with status: {m.status}")

    # Track who initiated processing
    m.processed_by = current_user.id

    # Parse group_id from body
    body = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}
    group_id = body.get("group_id")
    model_size = body.get("model_size")

    # If no group selected, use default group
    if not group_id:
        default_group = db.query(TranscriptionGroup).filter(TranscriptionGroup.is_default == True).first()
        if default_group:
            group_id = default_group.id

    from app.config import settings
    import os, uuid
    recording_model = model_size or settings.MS_TEAMS_RECORDING_MODEL

    # If already has transcription, reset it
    if m.transcription_id:
        t = db.query(Transcription).filter(Transcription.id == m.transcription_id).first()
        if t:
            t.status = TranscriptionStatus.pending
            t.progress_percent = 0
            t.status_message = None
            t.group_id = int(group_id) if group_id else None
            t.model_size = recording_model
            db.commit()
            m.status = MeetingRecordingStatus.queued
            db.commit()
            return {"ok": True, "transcription_id": t.id}

    # If no audio file yet, create placeholder + start background download
    if not m.audio_file_id:
        if not m.recording_url:
            raise HTTPException(status_code=400, detail="ไม่มี URL สำหรับดาวน์โหลด")

        # Create placeholder audio + transcription immediately so it shows in sidebar
        subject = m.meeting_subject or "Teams Recording"
        placeholder_filename = f"{uuid.uuid4().hex}.mp4"
        audio = AudioFile(
            original_filename=f"{subject}.mp4",
            stored_filename=placeholder_filename,
            file_path=str(settings.upload_path / placeholder_filename),
            file_size_bytes=0,
            duration_seconds=0,
            mime_type="video/mp4",
            status=AudioStatus.processing,
        )
        db.add(audio)
        db.commit()
        db.refresh(audio)

        t = Transcription(
            audio_file_id=audio.id,
            user_id=current_user.id,
            group_id=int(group_id) if group_id else None,
            model_size=recording_model,
            language=settings.MS_TEAMS_DEFAULT_LANGUAGE,
            status=TranscriptionStatus.in_progress,
            progress_percent=0,
            status_message="กำลังดาวน์โหลดไฟล์จาก Teams...",
        )
        db.add(t)
        db.commit()
        db.refresh(t)

        m.audio_file_id = audio.id
        m.transcription_id = t.id
        m.status = MeetingRecordingStatus.downloading
        db.commit()

        # Launch background download
        import threading
        _bg_args = {
            "meeting_id": m.id,
            "audio_id": audio.id,
            "transcription_id": t.id,
            "recording_url": m.recording_url,
            "meeting_subject": subject,
            "dest_path": str(settings.upload_path / placeholder_filename),
        }
        threading.Thread(target=_download_recording_bg, args=(_bg_args,), daemon=True).start()

        return {"ok": True, "transcription_id": t.id}

    # Audio already exists — create/reset transcription
    t = _create_or_reset_transcription(db, m, current_user.id, group_id, recording_model)

    # Update audio status
    audio = db.query(AudioFile).filter(AudioFile.id == m.audio_file_id).first()
    if audio:
        audio.status = AudioStatus.processing
        db.commit()

    m.transcription_id = t.id
    m.status = MeetingRecordingStatus.queued
    db.commit()

    return {"ok": True, "transcription_id": t.id}


@router.post("/api/meetings/{meeting_id}/retry")
def retry_meeting(meeting_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Retry a failed/stuck meeting recording. Re-downloads the file if missing."""
    import os
    from app.config import settings
    from app.models.transcription import TranscriptionSegment

    m = db.query(MeetingRecording).filter(MeetingRecording.id == meeting_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Not found")
    if not m.transcription_id:
        raise HTTPException(status_code=400, detail="No transcription to retry")

    t = db.query(Transcription).filter(Transcription.id == m.transcription_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Transcription not found")

    # Clear old segments
    db.query(TranscriptionSegment).filter(TranscriptionSegment.transcription_id == t.id).delete()

    # Reset transcription state
    t.status = TranscriptionStatus.pending
    t.progress_percent = 0
    t.status_message = None
    t.full_text = None
    t.summary = None
    t.mom_full = None
    t.auto_title = None

    audio = db.query(AudioFile).filter(AudioFile.id == m.audio_file_id).first()
    if audio:
        audio.status = AudioStatus.processing
        audio.error_message = None

    # If file is missing on disk, re-download in background before worker picks up
    needs_download = not audio or not audio.file_path or not os.path.exists(audio.file_path) or audio.file_size_bytes == 0
    if needs_download and m.recording_url and audio:
        t.status = TranscriptionStatus.in_progress
        t.status_message = "กำลังดาวน์โหลดไฟล์จาก Teams..."
        m.status = MeetingRecordingStatus.downloading
        db.commit()

        import threading
        _bg_args = {
            "meeting_id": m.id,
            "audio_id": audio.id,
            "transcription_id": t.id,
            "recording_url": m.recording_url,
            "meeting_subject": m.meeting_subject or "Teams Recording",
            "dest_path": audio.file_path,
        }
        threading.Thread(target=_download_recording_bg, args=(_bg_args,), daemon=True).start()
        return {"ok": True, "transcription_id": t.id, "redownloading": True}

    m.status = MeetingRecordingStatus.queued
    db.commit()
    return {"ok": True, "transcription_id": t.id}

    return {"ok": True, "transcription_id": t.id}


def _download_recording_bg(args: dict):
    """Background: download recording file, update audio record, set transcription to pending."""
    import os, logging
    logger = logging.getLogger("meeting")

    from app.database import SessionLocal
    from app.models.meeting import MeetingRecording, MeetingRecordingStatus
    # AudioFile, AudioStatus already imported at top level
    from app.models.transcription import Transcription, TranscriptionStatus
    from app.services.meeting_platforms.teams_client import TeamsClient
    from app.services.audio_service import get_audio_duration

    db = SessionLocal()
    try:
        logger.info("Downloading: %s", args["meeting_subject"])
        client = TeamsClient()
        success = client._graph_download(args["recording_url"], args["dest_path"])

        m = db.query(MeetingRecording).filter(MeetingRecording.id == args["meeting_id"]).first()
        audio = db.query(AudioFile).filter(AudioFile.id == args["audio_id"]).first()
        t = db.query(Transcription).filter(Transcription.id == args["transcription_id"]).first()

        if not success:
            if m:
                m.status = MeetingRecordingStatus.failed
                m.error_message = "ดาวน์โหลดไฟล์ไม่สำเร็จ"
            if t:
                t.status = TranscriptionStatus.failed
                t.status_message = "ดาวน์โหลดไฟล์ไม่สำเร็จ"
            if audio:
                audio.status = AudioStatus.failed
            db.commit()
            return

        # Update audio file info
        file_size = os.path.getsize(args["dest_path"])
        duration = get_audio_duration(args["dest_path"])
        logger.info("Downloaded: %s (%.1f MB, %.0fs)", args["meeting_subject"], file_size / 1024 / 1024, duration or 0)

        if audio:
            audio.file_size_bytes = file_size
            audio.duration_seconds = duration

        # Set transcription to pending — worker will pick it up
        if t:
            t.status = TranscriptionStatus.pending
            t.status_message = "รอประมวลผล..."

        if m:
            m.status = MeetingRecordingStatus.queued

        db.commit()
        logger.info("Ready for worker: %s (transcription ID %d)", args["meeting_subject"], args["transcription_id"])

    except Exception as e:
        logger.exception("Download failed: %s", e)
        try:
            m = db.query(MeetingRecording).filter(MeetingRecording.id == args["meeting_id"]).first()
            t = db.query(Transcription).filter(Transcription.id == args["transcription_id"]).first()
            if m:
                m.status = MeetingRecordingStatus.failed
                m.error_message = str(e)[:200]
            if t:
                t.status = TranscriptionStatus.failed
                t.status_message = f"ดาวน์โหลดล้มเหลว: {str(e)[:100]}"
            db.commit()
        except Exception:
            pass
    finally:
        db.close()


def _create_or_reset_transcription(db, m, user_id, group_id, recording_model):
    """Create or reset transcription for a meeting that already has audio."""
    from app.config import settings
    existing_t = db.query(Transcription).filter(Transcription.audio_file_id == m.audio_file_id).first()
    if existing_t:
        existing_t.status = TranscriptionStatus.pending
        existing_t.progress_percent = 0
        existing_t.status_message = None
        existing_t.user_id = user_id
        existing_t.group_id = int(group_id) if group_id else None
        existing_t.model_size = recording_model
        db.commit()
        t = existing_t
    else:
        t = Transcription(
            audio_file_id=m.audio_file_id,
            user_id=user_id,
            group_id=int(group_id) if group_id else None,
            model_size=recording_model,
            language=settings.MS_TEAMS_DEFAULT_LANGUAGE,
            status=TranscriptionStatus.pending,
        )
        db.add(t)
        db.commit()
        db.refresh(t)

    audio = db.query(AudioFile).filter(AudioFile.id == m.audio_file_id).first()
    if audio:
        audio.status = AudioStatus.processing

    m.transcription_id = t.id
    m.status = MeetingRecordingStatus.queued
    db.commit()
    return t


@router.post("/api/meetings/{meeting_id}/skip")
def skip_meeting(meeting_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Skip a recording - don't process it."""
    m = db.query(MeetingRecording).filter(MeetingRecording.id == meeting_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Not found")
    m.status = MeetingRecordingStatus.skipped
    db.commit()
    return {"ok": True}


@router.delete("/api/meetings/{meeting_id}")
def delete_meeting(meeting_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Delete a meeting recording entry."""
    m = db.query(MeetingRecording).filter(MeetingRecording.id == meeting_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Not found")
    db.delete(m)
    db.commit()
    return {"ok": True}


def _meeting_to_dict(m: MeetingRecording, db: Session) -> dict:
    metadata = {}
    if m.platform_metadata:
        try:
            metadata = json.loads(m.platform_metadata)
        except (json.JSONDecodeError, TypeError):
            pass

    transcription_status = None
    transcription_progress = None
    if m.transcription_id:
        t = db.query(Transcription).filter(Transcription.id == m.transcription_id).first()
        if t:
            transcription_status = t.status.value
            transcription_progress = t.progress_percent
            # Sync meeting status from transcription
            if t.status.value == "completed" and m.status != MeetingRecordingStatus.completed:
                m.status = MeetingRecordingStatus.completed
                db.commit()
            elif t.status.value == "failed" and m.status != MeetingRecordingStatus.failed:
                m.status = MeetingRecordingStatus.failed
                m.error_message = t.status_message
                db.commit()

    file_size_mb = None
    if m.audio_file_id:
        audio = db.query(AudioFile).filter(AudioFile.id == m.audio_file_id).first()
        if audio:
            file_size_mb = round(audio.file_size_bytes / 1024 / 1024, 1) if audio.file_size_bytes else None

    # Parse attendees from JSON text
    attendees = []
    if m.attendees:
        try:
            attendees = json.loads(m.attendees)
        except (json.JSONDecodeError, TypeError):
            pass

    processed_by_name = None
    if m.processed_by:
        u = db.query(User).filter(User.id == m.processed_by).first()
        if u:
            full = f"{u.first_name or ''} {u.last_name or ''}".strip()
            processed_by_name = full or u.username

    return {
        "id": m.id,
        "platform": m.platform,
        "meeting_subject": m.meeting_subject,
        "meeting_organizer": m.meeting_organizer,
        "attendees": attendees,
        "meeting_start_time": m.meeting_start_time.isoformat() if m.meeting_start_time else None,
        "status": m.status,
        "audio_file_id": m.audio_file_id,
        "transcription_id": m.transcription_id,
        "transcription_status": transcription_status,
        "transcription_progress": transcription_progress,
        "file_size_mb": file_size_mb,
        "file_name": metadata.get("file_name"),
        "discovered_at": m.discovered_at.isoformat() if m.discovered_at else None,
        "processed_by": m.processed_by,
        "processed_by_name": processed_by_name,
        "error_message": m.error_message,
    }
