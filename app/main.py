import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.database import SessionLocal
from app.models.audio import AudioFile, AudioStatus
from app.models.transcription import Transcription, TranscriptionStatus
from app.routers import audio, auth, group, pages, transcription

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
)

logger = logging.getLogger(__name__)


def _cleanup_stuck_transcriptions():
    """Mark any in-progress/pending transcriptions as failed on startup."""
    db = SessionLocal()
    try:
        stuck = (
            db.query(Transcription)
            .filter(
                Transcription.status == TranscriptionStatus.in_progress,
            )
            .all()
        )
        for t in stuck:
            logger.warning(
                "Marking stuck transcription %d as failed (was %s)",
                t.id, t.status.value,
            )
            t.status = TranscriptionStatus.failed
            t.status_message = "ถูกยกเลิก (server restart)"
            if t.audio_file:
                t.audio_file.status = AudioStatus.failed
                t.audio_file.error_message = "ถูกยกเลิก (server restart)"
        if stuck:
            db.commit()
            logger.info("Cleaned up %d stuck transcription(s)", len(stuck))
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    _cleanup_stuck_transcriptions()
    logger.info("Speech-to-Text app starting up")
    yield
    logger.info("Speech-to-Text app shutting down")


app = FastAPI(title="Speech-to-Text", version="1.0.0", lifespan=lifespan)

from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000"], allow_methods=["*"], allow_headers=["*"])

app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(auth.router)
app.include_router(pages.router)
app.include_router(audio.router)
app.include_router(transcription.router)
app.include_router(group.router)

# --- SPA: serve React frontend from dist ---
DIST_DIR = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if DIST_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=str(DIST_DIR / "assets")), name="spa_assets")

    @app.get("/{full_path:path}")
    async def spa_catch_all(request: Request, full_path: str):
        # Serve actual files (favicon, etc.) if they exist
        file_path = DIST_DIR / full_path
        if full_path and file_path.is_file():
            return FileResponse(file_path)
        # Otherwise serve index.html for client-side routing
        return FileResponse(DIST_DIR / "index.html")
