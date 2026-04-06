import json
import logging
import subprocess
import uuid
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.config import settings
from app.models.audio import AudioFile, AudioStatus

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".webm", ".mp4", ".wma"}
MIME_MAP = {
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".m4a": "audio/mp4",
    ".ogg": "audio/ogg",
    ".flac": "audio/flac",
    ".webm": "audio/webm",
    ".mp4": "video/mp4",
    ".wma": "audio/x-ms-wma",
}


def get_audio_duration(file_path: str) -> float | None:
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                file_path,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return float(data["format"]["duration"])
    except Exception as e:
        logger.warning("Could not get audio duration: %s", e)
    return None


async def save_upload(file: UploadFile, db: Session) -> AudioFile:
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {ext}")

    stored_filename = f"{uuid.uuid4().hex}{ext}"
    file_path = settings.upload_path / stored_filename

    content = await file.read()
    file_path.write_bytes(content)

    duration = get_audio_duration(str(file_path))

    audio = AudioFile(
        original_filename=file.filename,
        stored_filename=stored_filename,
        file_path=str(file_path),
        file_size_bytes=len(content),
        duration_seconds=duration,
        mime_type=MIME_MAP.get(ext, file.content_type),
        status=AudioStatus.uploaded,
    )
    db.add(audio)
    db.commit()
    db.refresh(audio)
    return audio


def get_audio(db: Session, audio_id: int) -> AudioFile | None:
    return db.query(AudioFile).filter(AudioFile.id == audio_id).first()
