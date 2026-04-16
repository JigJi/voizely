"""Admin / machine-to-machine endpoints.

Endpoints here are not called by end users. They are called by trusted internal
services (e.g. the AD sync job on the frontend machine) and are authenticated
via X-Internal-API-Key (see app.core.internal_auth).
"""
import logging
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.core.internal_auth import require_internal_api_key
from app.database import get_db
from app.models.transcription import SpeakerProfile

logger = logging.getLogger(__name__)
router = APIRouter(tags=["admin"], dependencies=[Depends(require_internal_api_key)])


# ---------- AD Speaker Sync ----------

class ADUserPayload(BaseModel):
    email: str
    display_name: str = ""
    first_name: str = ""
    last_name: str = ""
    department: str = ""
    organization: str = ""  # e.g. "appworks" or "iwired"
    title: str = ""
    is_disabled: bool = False


class SyncADSpeakersRequest(BaseModel):
    users: list[ADUserPayload] = Field(..., min_length=1)


class SyncADSpeakersResponse(BaseModel):
    total_received: int
    created: int
    updated: int
    reactivated: int
    marked_inactive: int


def _shorten_department(dept: str) -> str:
    """Shorten department to ≤4 char uppercase suffix for nickname collision resolution."""
    if not dept:
        return ""
    dept = dept.strip()
    if len(dept) <= 4 and " " not in dept:
        return dept.upper()
    words = dept.split()
    if len(words) > 1:
        initials = "".join(w[0].upper() for w in words if w and w[0].isalpha())
        if initials:
            return initials
    return dept[:3].upper()


def _resolve_nickname(db: Session, desired: str, dept: str, email: str, exclude_id: int | None = None) -> str:
    """Pick a unique nickname for an AD speaker. Falls back to 'Name DEPT' or email local-part."""
    desired = (desired or "").strip() or email.split("@")[0]
    q = db.query(SpeakerProfile).filter(SpeakerProfile.nickname == desired)
    if exclude_id:
        q = q.filter(SpeakerProfile.id != exclude_id)
    if not q.first():
        return desired

    dept_short = _shorten_department(dept)
    if dept_short:
        candidate = f"{desired} {dept_short}"
        q2 = db.query(SpeakerProfile).filter(SpeakerProfile.nickname == candidate)
        if exclude_id:
            q2 = q2.filter(SpeakerProfile.id != exclude_id)
        if not q2.first():
            return candidate

    # Fallback: email local-part (unique per user)
    local = email.split("@")[0]
    return local


@router.post("/api/admin/sync-ad-speakers", response_model=SyncADSpeakersResponse)
def sync_ad_speakers(body: SyncADSpeakersRequest, db: Session = Depends(get_db)):
    """Bulk upsert AD users into SpeakerProfile (source='ad').

    Called by the scheduled AD sync job running on the AD-connected frontend machine.
    Does not touch profiles with source='manual' — those are owned by individual users.
    Leavers (AD users no longer present, or marked disabled) are flagged is_active=False
    so they stay referenced by past transcriptions but drop out of the speaker picker.
    """
    now = datetime.now(timezone(timedelta(hours=7)))
    incoming_emails: set[str] = set()
    created = updated = reactivated = 0

    for u in body.users:
        email = (u.email or "").strip().lower()
        if not email:
            continue
        incoming_emails.add(email)

        full_name = f"{u.first_name} {u.last_name}".strip() or u.display_name.strip()
        nickname = u.display_name.strip() or u.first_name.strip() or email.split("@")[0]

        existing = db.query(SpeakerProfile).filter(SpeakerProfile.email == email).first()

        if existing:
            if existing.source != "ad":
                # Don't touch manual profiles — user owns these
                continue

            # Update fields from AD (AD is authoritative for 'ad' profiles)
            wanted_nickname = _resolve_nickname(db, nickname, u.department, email, exclude_id=existing.id)
            if existing.nickname != wanted_nickname:
                existing.nickname = wanted_nickname
            existing.full_name = full_name
            existing.organization = u.organization
            existing.department = u.department
            existing.position = u.title
            was_inactive = not existing.is_active
            existing.is_active = not u.is_disabled
            if was_inactive and existing.is_active:
                reactivated += 1
            existing.updated_at = now
            updated += 1
        else:
            wanted_nickname = _resolve_nickname(db, nickname, u.department, email)
            db.add(SpeakerProfile(
                nickname=wanted_nickname,
                source="ad",
                email=email,
                full_name=full_name,
                organization=u.organization,
                department=u.department,
                position=u.title,
                is_active=not u.is_disabled,
                created_at=now,
                updated_at=now,
            ))
            created += 1

    # Mark missing AD users inactive (leavers not present in this sync batch)
    marked_inactive = 0
    if incoming_emails:
        missing = (
            db.query(SpeakerProfile)
            .filter(
                SpeakerProfile.source == "ad",
                SpeakerProfile.is_active == True,
                ~SpeakerProfile.email.in_(incoming_emails),
            )
            .all()
        )
        for m in missing:
            m.is_active = False
            m.updated_at = now
            marked_inactive += 1

    db.commit()

    logger.info(
        "AD sync: received=%d created=%d updated=%d reactivated=%d inactive=%d",
        len(body.users), created, updated, reactivated, marked_inactive,
    )

    return SyncADSpeakersResponse(
        total_received=len(body.users),
        created=created,
        updated=updated,
        reactivated=reactivated,
        marked_inactive=marked_inactive,
    )
