from datetime import datetime

from pydantic import BaseModel

from app.models.audio import AudioStatus


class AudioFileResponse(BaseModel):
    id: int
    original_filename: str
    stored_filename: str
    file_size_bytes: int
    duration_seconds: float | None
    mime_type: str | None
    status: AudioStatus
    error_message: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
