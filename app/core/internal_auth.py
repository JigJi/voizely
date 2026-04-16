"""Machine-to-machine auth for trusted internal callers (e.g., frontend_auth service
on the AD-connected Windows box talking to this backend).

Uses the shared INTERNAL_API_KEY from .env. Both sides must hold the same value.
"""
import secrets

from fastapi import Header, HTTPException, status

from app.config import settings


def require_internal_api_key(x_internal_api_key: str = Header(..., alias="X-Internal-API-Key")):
    """Dependency: require a valid X-Internal-API-Key header.

    Use on endpoints called by trusted internal services (not by end users).
    """
    if not settings.INTERNAL_API_KEY:
        raise HTTPException(status_code=503, detail="Backend not configured for internal API")
    if not secrets.compare_digest(x_internal_api_key, settings.INTERNAL_API_KEY):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
