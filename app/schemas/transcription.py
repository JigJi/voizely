from datetime import datetime

from pydantic import BaseModel

from app.models.transcription import TranscriptionStatus


class TranscriptionCreate(BaseModel):
    model_config = {"protected_namespaces": ()}

    language: str | None = None
    model_size: str = "large-v3"


class TranscriptionSegmentResponse(BaseModel):
    id: int
    segment_index: int
    start_time: float
    end_time: float
    text: str
    avg_logprob: float | None

    model_config = {"from_attributes": True}


class TranscriptionResponse(BaseModel):
    id: int
    audio_file_id: int
    model_size: str
    language: str | None
    full_text: str | None
    detected_language: str | None
    status: TranscriptionStatus
    progress_percent: float
    processing_time_seconds: float | None
    created_at: datetime
    segments: list[TranscriptionSegmentResponse] = []

    model_config = {"from_attributes": True, "protected_namespaces": ()}


class TranscriptionProgress(BaseModel):
    id: int
    status: TranscriptionStatus
    progress_percent: float
    processing_time_seconds: float | None
    status_message: str | None = None
