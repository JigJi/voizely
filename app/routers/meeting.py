import json
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.meeting import MeetingRecording, MeetingRecordingStatus
from app.models.transcription import Transcription, TranscriptionStatus
from app.models.audio import AudioFile, AudioStatus
from app.models.user import User
from app.routers.auth import get_current_user

router = APIRouter(tags=["meetings"])


@router.get("/api/meetings")
def list_meetings(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """List meeting recordings for current user (organizer OR attendee)."""
    if current_user.role == "ADMIN":
        items = (
            db.query(MeetingRecording)
            .order_by(MeetingRecording.discovered_at.desc())
            .all()
        )
    else:
        # Show meetings where user is organizer OR listed as attendee
        email = current_user.email.lower() if current_user.email else ""
        items = (
            db.query(MeetingRecording)
            .filter(
                or_(
                    MeetingRecording.meeting_organizer == current_user.email,
                    MeetingRecording.attendees.like(f'%"{email}"%'),
                )
            )
            .order_by(MeetingRecording.discovered_at.desc())
            .all()
        )
    return [_meeting_to_dict(m, db) for m in items]


@router.get("/api/meetings/{meeting_id}")
def get_meeting(meeting_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    m = db.query(MeetingRecording).filter(MeetingRecording.id == meeting_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Not found")
    # Check if user is admin, organizer, or attendee
    if current_user.role != "ADMIN":
        email = (current_user.email or "").lower()
        organizer = (m.meeting_organizer or "").lower()
        attendees_str = (m.attendees or "").lower()
        if email not in organizer and email not in attendees_str:
            raise HTTPException(status_code=403, detail="Access denied")
    return _meeting_to_dict(m, db)


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
    """Retry a failed/stuck meeting recording."""
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

    # Reset transcription
    from app.config import settings
    t.status = TranscriptionStatus.pending
    t.progress_percent = 0
    t.status_message = None
    t.full_text = None
    t.summary = None
    t.mom_full = None
    t.auto_title = None
    t.model_size = recording_model

    # Reset audio status
    audio = db.query(AudioFile).filter(AudioFile.id == m.audio_file_id).first()
    if audio:
        audio.status = AudioStatus.processing
        audio.error_message = None

    m.status = MeetingRecordingStatus.queued
    db.commit()

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

    return {
        "id": m.id,
        "platform": m.platform,
        "meeting_subject": m.meeting_subject,
        "meeting_organizer": m.meeting_organizer,
        "attendees": attendees,
        "meeting_start_time": m.meeting_start_time.isoformat() if m.meeting_start_time else None,
        "status": m.status,
        "transcription_id": m.transcription_id,
        "transcription_status": transcription_status,
        "transcription_progress": transcription_progress,
        "file_size_mb": file_size_mb,
        "file_name": metadata.get("file_name"),
        "discovered_at": m.discovered_at.isoformat() if m.discovered_at else None,
        "processed_by": m.processed_by,
        "error_message": m.error_message,
    }
