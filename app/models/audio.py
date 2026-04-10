import enum
from datetime import datetime, timezone, timedelta

from sqlalchemy import Integer, String, Float, Text, Enum, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AudioStatus(str, enum.Enum):
    uploaded = "uploaded"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class AudioFile(Base):
    __tablename__ = "audio_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    stored_filename: Mapped[str] = mapped_column(String(255), unique=True)
    file_path: Mapped[str] = mapped_column(String(500))
    file_size_bytes: Mapped[int] = mapped_column(Integer)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[AudioStatus] = mapped_column(
        Enum(AudioStatus), default=AudioStatus.uploaded
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone(timedelta(hours=7)))
    )

    transcription: Mapped["Transcription"] = relationship(
        back_populates="audio_file", uselist=False
    )
