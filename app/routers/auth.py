import logging
import os
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.core.security import create_access_token, decode_token
from app.models.user import User
from app.services.auth_service import authenticate, upsert_user_from_profile

# Audit logger (write to logs/auth_audit.log)
_audit_log_dir = os.path.join(os.path.dirname(__file__), "..", "..", "logs")
os.makedirs(_audit_log_dir, exist_ok=True)
_audit_logger = logging.getLogger("auth_audit")
_audit_logger.setLevel(logging.INFO)
if not _audit_logger.handlers:
    _h = logging.FileHandler(os.path.join(_audit_log_dir, "auth_audit.log"), encoding="utf-8")
    _h.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
    _audit_logger.addHandler(_h)
    _audit_logger.propagate = False

router = APIRouter(prefix="/api/auth", tags=["auth"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    username = decode_token(token)
    if not username:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = db.query(User).filter(User.username == username).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    return user


@router.post("/login")
def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = authenticate(form.username, form.password, db)
    if not user:
        raise HTTPException(status_code=401, detail="ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")

    token = create_access_token(user.username)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "department": user.department,
            "role": user.role,
        },
    }


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "department": user.department,
        "role": user.role,
    }


# --- AD Verify (for frontend_auth service) ---

class ADVerifyRequest(BaseModel):
    username: str
    email: str
    first_name: str = ""
    last_name: str = ""
    department: str = ""
    organization: str = ""
    ad_source: str = ""


def _audit(event: str, **kwargs):
    """Write structured audit log entry."""
    parts = [event] + [f"{k}={v}" for k, v in kwargs.items()]
    _audit_logger.info(" ".join(parts))


from app.core.limiter import limiter as _limiter


@router.post("/ad-verify")
@_limiter.limit("10/minute")
def ad_verify(
    request: Request,
    body: ADVerifyRequest,
    db: Session = Depends(get_db),
):
    """
    Receive AD-verified profile from frontend_auth service, upsert user, return JWT.

    Called by frontend_auth (LAN-only via Tailscale Funnel), not by end users directly.
    Protected by X-Internal-API-Key header + rate limit.
    """
    client_ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "unknown").split(",")[0].strip()

    # 1. Verify internal API key
    api_key = request.headers.get("x-internal-api-key", "")
    if not settings.INTERNAL_API_KEY:
        _audit("ad_verify.rejected", reason="backend_not_configured", ip=client_ip)
        raise HTTPException(status_code=503, detail="Backend not configured for ad-verify")
    if api_key != settings.INTERNAL_API_KEY:
        _audit("ad_verify.rejected", reason="invalid_api_key", ip=client_ip, username=body.username)
        raise HTTPException(status_code=401, detail="Invalid API key")

    # 2. Validate required fields
    if not body.username or not body.email:
        _audit("ad_verify.rejected", reason="missing_fields", ip=client_ip)
        raise HTTPException(status_code=422, detail="username and email are required")

    # 3. Upsert user (frontend already verified AD — trust the profile)
    profile = {
        "username": body.username,
        "email": body.email,
        "first_name": body.first_name,
        "last_name": body.last_name,
        "department": body.department,
        "organization": body.organization,
    }
    try:
        user = upsert_user_from_profile(db, profile)
    except Exception as e:
        _audit("ad_verify.error", ip=client_ip, username=body.username, error=str(e)[:100])
        raise HTTPException(status_code=500, detail="Failed to upsert user")

    # 4. Issue JWT
    token = create_access_token(user.username)
    _audit("ad_verify.success", ip=client_ip, username=user.username, ad_source=body.ad_source)

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "department": user.department,
            "role": user.role,
        },
    }
