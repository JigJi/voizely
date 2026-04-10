import logging
from pathlib import Path

from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm

from config import settings, AD_CONFIGS
from ad_service import authenticate_ad
from backend_client import verify_ad_with_backend


log_dir = Path(__file__).parent / settings.LOG_DIR
log_dir.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    handlers=[
        logging.FileHandler(log_dir / "frontend_auth.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)

logger = logging.getLogger("frontend_auth")


app = FastAPI(title="Voizely frontend_auth", version="0.1")


@app.get("/api/auth/health")
def health():
    return {
        "status": "ok",
        "service": "voizely-frontend-auth",
        "backend_configured": bool(settings.INTERNAL_API_KEY),
        "backend_url": settings.BACKEND_PUBLIC_URL,
        "ad_configs": [c["name"] for c in AD_CONFIGS],
    }


@app.post("/api/auth/login")
def login(form: OAuth2PasswordRequestForm = Depends()):
    username = form.username.strip()
    password = form.password

    if not username or not password:
        raise HTTPException(status_code=422, detail="username and password required")

    profile = authenticate_ad(username, password, AD_CONFIGS)
    if not profile:
        logger.info("login failed (AD bind): %s", username)
        raise HTTPException(status_code=401, detail="ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")

    try:
        result = verify_ad_with_backend(profile)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("backend relay failed: %s", e)
        raise HTTPException(status_code=500, detail="Authentication relay failed")

    logger.info("login ok: %s (%s)", username, profile["ad_source"])
    return result
