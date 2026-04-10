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
from app.routers import audio, auth, group, meeting, pages, transcription

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
from app.config import settings as _settings
_cors_origins = [o.strip() for o in _settings.CORS_ORIGINS.split(",") if o.strip()] if hasattr(_settings, "CORS_ORIGINS") and _settings.CORS_ORIGINS else ["http://localhost:3000"]
app.add_middleware(CORSMiddleware, allow_origins=_cors_origins, allow_methods=["*"], allow_headers=["*"], allow_credentials=True)

# Rate limiter (for /api/auth/ad-verify)
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.core.limiter import limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# Health check endpoint (no auth, for Tailscale Funnel test)
@app.get("/api/health")
def health():
    return {"status": "ok", "service": "voizely-backend"}


app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(auth.router)
app.include_router(pages.router)
app.include_router(audio.router)
app.include_router(transcription.router)
app.include_router(group.router)
app.include_router(meeting.router)

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
