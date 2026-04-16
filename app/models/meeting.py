import enum
from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, Date, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base


class MeetingPlatform(str, enum.Enum):
    teams = "teams"
    zoom = "zoom"
    google_meet = "google_meet"


class MeetingRecordingStatus(str, enum.Enum):
    discovered = "discovered"
    downloading = "downloading"
    queued = "queued"
    completed = "completed"
    failed = "failed"
    skipped = "skipped"


class MeetingRecording(Base):
    __tablename__ = "meeting_recordings"
    __table_args__ = (
        UniqueConstraint("platform", "platform_recording_id", name="uq_platform_recording"),
    )

    id = Column(Integer, primary_key=True, index=True)
    platform = Column(String(20), nullable=False, index=True)
    platform_recording_id = Column(String(500), nullable=False)
    platform_meeting_id = Column(String(500), nullable=True)
    meeting_subject = Column(String(500), nullable=True)
    meeting_organizer = Column(String(200), nullable=True)
    meeting_start_time = Column(DateTime, nullable=True)
    meeting_end_time = Column(DateTime, nullable=True)
    recording_url = Column(Text, nullable=True)

    audio_file_id = Column(Integer, ForeignKey("audio_files.id"), nullable=True)
    transcription_id = Column(Integer, ForeignKey("transcriptions.id"), nullable=True)

    status = Column(String(20), nullable=False, default=MeetingRecordingStatus.discovered)
    error_message = Column(Text, nullable=True)
    discovered_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)
    platform_metadata = Column(Text, nullable=True)  # JSON blob
    attendees = Column(Text, nullable=True)  # JSON list of attendee emails
    processed_by = Column(Integer, ForeignKey("users.id"), nullable=True)  # user who clicked ถอดเสียง

    audio_file = relationship("AudioFile", foreign_keys=[audio_file_id])
    transcription = relationship("Transcription", foreign_keys=[transcription_id])


class UserCalendarCache(Base):
    """Cache calendar events per user per date — past days never change."""
    __tablename__ = "user_calendar_cache"
    __table_args__ = (
        UniqueConstraint("user_id", "subject", "event_start", name="uq_user_calendar_event"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    subject = Column(String(500), nullable=False)
    event_start = Column(DateTime, nullable=True)
    cached_date = Column(Date, nullable=False, index=True)  # which date this entry covers
    created_at = Column(DateTime, default=datetime.utcnow)
