"""
Teams Recording Worker
Polls MS Graph API for new meeting recordings, downloads them,
and feeds them into the existing transcription pipeline.
Process ONE batch then exit. Runs in loop via start_teams_worker.bat
"""
import json
import logging
import os
import uuid
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s %(message)s")
logger = logging.getLogger("teams_worker")

from app.database import SessionLocal
from app.models.audio import AudioFile, AudioStatus
from app.models.transcription import Transcription, TranscriptionStatus
from app.models.meeting import MeetingRecording, MeetingPlatform, MeetingRecordingStatus
from app.models.user import User
from app.config import settings
from app.services.audio_service import get_audio_duration


def main():
    if not settings.MS_TEAMS_ENABLED:
        return

    from app.services.meeting_platforms.teams_client import TeamsClient
    client = TeamsClient()

    db = SessionLocal()
    try:
        # 1. Discover new recordings
        new_recordings = client.discover_new_recordings(db)
        if not new_recordings:
            return

        logger.info("Found %d new recording(s)", len(new_recordings))

        for rec_info in new_recordings:
            try:
                _process_recording(db, client, rec_info)
            except Exception as e:
                logger.exception("Failed to process recording: %s", e)
                db.rollback()
    finally:
        db.close()


def _find_user_by_email(db, email: str) -> User | None:
    """Find user by email to link transcription ownership."""
    if not email:
        return None
    return db.query(User).filter(User.email == email, User.is_active == True).first()


def _process_recording(db, client, rec_info: dict):
    """Save metadata only — NO download. File downloads when user clicks process."""
    # Serialize attendees list to JSON
    attendees_list = rec_info.get("attendees", [])
    attendees_json = json.dumps(attendees_list) if attendees_list else None

    metadata = rec_info.get("platform_metadata", {})
    # Store file size from metadata (from OneDrive listing, no download needed)
    file_size = metadata.get("file_size", 0)

    # Create MeetingRecording record (metadata only)
    meeting_rec = MeetingRecording(
        platform=MeetingPlatform.teams,
        platform_recording_id=rec_info["platform_recording_id"],
        meeting_subject=rec_info.get("meeting_subject"),
        meeting_organizer=rec_info.get("meeting_organizer"),
        meeting_start_time=rec_info.get("meeting_start_time"),
        recording_url=rec_info.get("recording_url"),
        status=MeetingRecordingStatus.discovered,
        platform_metadata=json.dumps(metadata),
        attendees=attendees_json,
    )
    db.add(meeting_rec)
    db.commit()

    subject = rec_info.get("meeting_subject", "Teams Recording")
    logger.info("Discovered: %s (%.1f MB) — metadata only, no download",
                subject, file_size / 1024 / 1024 if file_size else 0)


if __name__ == "__main__":
    main()
