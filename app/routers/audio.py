from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.audio import AudioFileResponse
from app.services import audio_service

router = APIRouter(prefix="/api/audio", tags=["audio"])


@router.post("/upload", response_model=AudioFileResponse)
async def upload_audio(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    try:
        audio = await audio_service.save_upload(file, db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return audio


@router.get("/{audio_id}", response_model=AudioFileResponse)
def get_audio(audio_id: int, db: Session = Depends(get_db)):
    audio = audio_service.get_audio(db, audio_id)
    if not audio:
        raise HTTPException(status_code=404, detail="Audio file not found")
    return audio


@router.post("/{audio_id}/rename")
async def rename_audio(audio_id: int, request: Request, db: Session = Depends(get_db)):
    from app.models.audio import AudioFile
    body = await request.json()
    name = body.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Missing name")
    audio = db.query(AudioFile).filter(AudioFile.id == audio_id).first()
    if not audio:
        raise HTTPException(status_code=404, detail="Not found")
    audio.original_filename = name
    db.commit()
    return {"ok": True}


@router.get("/{audio_id}/stream")
def stream_audio(audio_id: int, db: Session = Depends(get_db)):
    audio = audio_service.get_audio(db, audio_id)
    if not audio:
        raise HTTPException(status_code=404, detail="Audio file not found")
    file_path = Path(audio.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")
    return FileResponse(
        file_path,
        media_type=audio.mime_type or "audio/mpeg",
        filename=audio.original_filename,
    )
