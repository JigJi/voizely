from datetime import datetime, timedelta, timezone

from jose import jwt, JWTError

from app.config import settings


def create_access_token(username: str, tenant_id: int | None = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    claims = {"sub": username, "exp": expire}
    if tenant_id is not None:
        claims["tid"] = tenant_id
    return jwt.encode(claims, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict | None:
    """Return {"username": str, "tenant_id": int|None} from token, or None if invalid.

    Legacy tokens (issued before multi-tenancy) carry no "tid" → tenant_id is None;
    callers fall back to username-only lookup (safe while only tenant 1 exists)."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        username = payload.get("sub")
        if not username:
            return None
        return {"username": username, "tenant_id": payload.get("tid")}
    except JWTError:
        return None
