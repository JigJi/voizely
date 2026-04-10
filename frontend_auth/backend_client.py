import logging

import httpx
from fastapi import HTTPException

from config import settings

logger = logging.getLogger(__name__)


def verify_ad_with_backend(profile: dict) -> dict:
    """POST verified AD profile to backend's /api/auth/ad-verify, return JWT response."""
    if not settings.INTERNAL_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="frontend_auth not configured: INTERNAL_API_KEY missing",
        )

    body = {
        "username": profile["username"],
        "email": profile["email"],
        "first_name": profile.get("first_name", ""),
        "last_name": profile.get("last_name", ""),
        "department": profile.get("department", ""),
        "organization": profile.get("organization", ""),
        "ad_source": profile.get("ad_source", ""),
    }

    url = f"{settings.BACKEND_PUBLIC_URL.rstrip('/')}/api/auth/ad-verify"

    try:
        r = httpx.post(
            url,
            headers={
                "Content-Type": "application/json",
                "X-Internal-API-Key": settings.INTERNAL_API_KEY,
            },
            json=body,
            timeout=settings.BACKEND_TIMEOUT,
        )
    except httpx.TimeoutException:
        logger.error("backend timeout: %s", url)
        raise HTTPException(status_code=504, detail="Backend timeout")
    except httpx.RequestError as e:
        logger.error("backend network error: %s", e)
        raise HTTPException(status_code=502, detail="Backend unreachable")

    if r.status_code == 200:
        return r.json()
    if r.status_code == 401:
        logger.error("backend rejected api key (frontend INTERNAL_API_KEY mismatch)")
        raise HTTPException(status_code=500, detail="API key mismatch with backend")
    if r.status_code == 422:
        logger.error("backend validation failed: %s", r.text)
        raise HTTPException(status_code=500, detail="Profile validation failed at backend")
    if r.status_code == 429:
        raise HTTPException(status_code=429, detail="Rate limit exceeded at backend")
    if r.status_code == 503:
        raise HTTPException(status_code=503, detail="Backend not configured for ad-verify")

    logger.error("backend unexpected status %s: %s", r.status_code, r.text[:200])
    raise HTTPException(status_code=502, detail=f"Backend error: {r.status_code}")
