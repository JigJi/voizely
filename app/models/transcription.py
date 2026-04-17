import enum
from datetime import datetime, timezone, timedelta

import sqlalchemy as sa
from sqlalchemy import Integer, String, Float, Text, Enum, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TranscriptionStatus(str, enum.Enum):
    pending = "pending"
    in_progress = "in_progress"
    completed = "completed"
    failed = "failed"


class TranscriptionGroup(Base):
    __tablename__ = "transcription_groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    custom_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone(timedelta(hours=7)))
    )

    transcriptions: Mapped[list["Transcription"]] = relationship(
        back_populates="group", order_by="Transcription.created_at.desc()"
    )


class Transcription(Base):
    __tablename__ = "transcriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    audio_file_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("audio_files.id"), unique=True
    )
    user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True, index=True
    )
    group_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("transcription_groups.id"), nullable=True
    )
    model_size: Mapped[str] = mapped_column(String(50), default="large-v3")
    language: Mapped[str | None] = mapped_column(String(10), nullable=True)
    full_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    detected_language: Mapped[str | None] = mapped_column(String(10), nullable=True)
    status: Mapped[TranscriptionStatus] = mapped_column(
        Enum(TranscriptionStatus), default=TranscriptionStatus.pending
    )
    progress_percent: Mapped[float] = mapped_column(Float, default=0.0)
    status_message: Mapped[str | None] = mapped_column(String(200), nullable=True)
    processing_time_seconds: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    initial_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    clean_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    mom_full: Mapped[str | None] = mapped_column(Text, nullable=True)
    llm_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    llm_processing_time: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Analysis
    auto_title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    summary_short: Mapped[str | None] = mapped_column(Text, nullable=True)
    sentiment: Mapped[str | None] = mapped_column(String(20), nullable=True)
    meeting_tone: Mapped[str | None] = mapped_column(String(100), nullable=True)
    meeting_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    topics: Mapped[str | None] = mapped_column(Text, nullable=True)
    action_items: Mapped[str | None] = mapped_column(Text, nullable=True)
    key_decisions: Mapped[str | None] = mapped_column(Text, nullable=True)
    open_questions: Mapped[str | None] = mapped_column(Text, nullable=True)
    speaker_suggestions: Mapped[str | None] = mapped_column(Text, nullable=True)
    voiceprint_suggestions: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Quality
    deepgram_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Cost tracking
    deepgram_duration_sec: Mapped[float | None] = mapped_column(Float, nullable=True)
    deepgram_cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    gemini_input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gemini_output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gemini_cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone(timedelta(hours=7)))
    )

    audio_file: Mapped["AudioFile"] = relationship(back_populates="transcription")
    segments: Mapped[list["TranscriptionSegment"]] = relationship(
        back_populates="transcription", order_by="TranscriptionSegment.segment_index"
    )
    group: Mapped["TranscriptionGroup | None"] = relationship(back_populates="transcriptions")


class TranscriptionSegment(Base):
    __tablename__ = "transcription_segments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    transcription_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("transcriptions.id")
    )
    segment_index: Mapped[int] = mapped_column(Integer)
    start_time: Mapped[float] = mapped_column(Float)
    end_time: Mapped[float] = mapped_column(Float)
    text: Mapped[str] = mapped_column(Text)
    clean_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    clean_text_alt: Mapped[str | None] = mapped_column(Text, nullable=True)
    speaker: Mapped[str | None] = mapped_column(String(50), nullable=True)
    avg_logprob: Mapped[float | None] = mapped_column(Float, nullable=True)

    transcription: Mapped["Transcription"] = relationship(back_populates="segments")


class SpeakerProfile(Base):
    __tablename__ = "speaker_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    nickname: Mapped[str] = mapped_column(String(100))
    source: Mapped[str] = mapped_column(String(20), default="manual")  # "ad" or "manual"
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    full_name: Mapped[str | None] = mapped_column(String(200), default="")
    organization: Mapped[str | None] = mapped_column(String(200), default="")
    department: Mapped[str | None] = mapped_column(String(200), default="")
    position: Mapped[str | None] = mapped_column(String(200), default="")
    embedding: Mapped[bytes | None] = mapped_column(sa.LargeBinary, nullable=True)
    total_seconds: Mapped[float] = mapped_column(Float, default=0)
    num_sessions: Mapped[int] = mapped_column(Integer, default=0)
    user_id: Mapped[int | None] = mapped_column(Integer, sa.ForeignKey("users.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(sa.Boolean, default=True, nullable=False, server_default=sa.true())
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone(timedelta(hours=7)))
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone(timedelta(hours=7)))
    )


class CorrectionDict(Base):
    __tablename__ = "correction_dict"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True, index=True
    )
    wrong: Mapped[str] = mapped_column(String(200), unique=True)
    correct: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone(timedelta(hours=7)))
    )
