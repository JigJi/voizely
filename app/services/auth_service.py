import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy.orm import Session

from app.config import settings
from app.models.user import User

logger = logging.getLogger(__name__)


def authenticate(username: str, password: str, db: Session) -> User | None:
    """Authenticate user. Try AD first if enabled, fallback to fixed."""
    profile = None
    if settings.AD_ENABLED:
        profile = _authenticate_ad(username, password)
        if not profile:
            logger.info("AD auth failed for %s, falling back to fixed auth", username)
    if not profile:
        profile = _authenticate_fixed(username, password)

    if not profile:
        return None

    # Upsert user in DB
    user = db.query(User).filter(User.username == profile["username"]).first()
    if not user:
        user = User(
            username=profile["username"],
            email=profile.get("email"),
            first_name=profile.get("first_name"),
            last_name=profile.get("last_name"),
            department=profile.get("department"),
        )
        db.add(user)
    else:
        # Update profile fields only if new value is meaningful (not @local placeholder)
        new_email = profile.get("email", "")
        if new_email and "@local" not in new_email:
            user.email = new_email
        if profile.get("first_name"):
            user.first_name = profile["first_name"]
        if profile.get("last_name"):
            user.last_name = profile["last_name"]
        if profile.get("department"):
            user.department = profile["department"]

    user.last_login_at = datetime.now(timezone(timedelta(hours=7)))
    db.commit()
    db.refresh(user)

    # Auto-sync SpeakerProfile from AD user
    if settings.AD_ENABLED and profile.get("email") and "@local" not in profile.get("email", ""):
        _sync_speaker_profile(db, profile)

    return user


def _shorten_department(dept: str) -> str:
    """Shorten department name to max ~4 chars, prefer uppercase initials."""
    if not dept:
        return ""
    dept = dept.strip()
    # If already short (<=4 chars, no spaces), use as-is
    if len(dept) <= 4 and ' ' not in dept:
        return dept.upper()
    # Multiple words: take first letter of each word (uppercase)
    words = dept.split()
    if len(words) > 1:
        initials = ''.join(w[0].upper() for w in words if w and w[0].isalpha())
        if initials:
            return initials
    # Single long word: take first 3 chars uppercase
    return dept[:3].upper()


def _sync_speaker_profile(db: Session, profile: dict):
    """Auto-create/update SpeakerProfile from AD user data."""
    try:
        from app.models.transcription import SpeakerProfile
        nickname = profile.get("first_name") or profile.get("username", "")
        if not nickname:
            return

        existing = db.query(SpeakerProfile).filter(
            SpeakerProfile.email == profile.get("email")
        ).first()

        if existing:
            # Update from AD but only if source is "ad"
            if existing.source == "ad":
                existing.full_name = f"{profile.get('first_name', '')} {profile.get('last_name', '')}".strip()
                existing.department = profile.get("department", "")
                existing.organization = profile.get("organization", "")
                existing.updated_at = datetime.now(timezone(timedelta(hours=7)))
        else:
            # Handle nickname collision: first_name → first_name + dept_short → username
            nick_exists = db.query(SpeakerProfile).filter(SpeakerProfile.nickname == nickname).first()
            if nick_exists:
                dept_short = _shorten_department(profile.get("department", ""))
                if dept_short:
                    candidate = f"{nickname} {dept_short}"
                    if not db.query(SpeakerProfile).filter(SpeakerProfile.nickname == candidate).first():
                        nickname = candidate
                    else:
                        nickname = profile.get("username", nickname)
                else:
                    nickname = profile.get("username", nickname)

            p = SpeakerProfile(
                nickname=nickname,
                source="ad",
                email=profile.get("email", ""),
                full_name=f"{profile.get('first_name', '')} {profile.get('last_name', '')}".strip(),
                organization=profile.get("organization", ""),
                department=profile.get("department", ""),
            )
            db.add(p)

        db.commit()
    except Exception as e:
        logger.warning("SpeakerProfile sync failed: %s", e)
        db.rollback()


def _authenticate_fixed(username: str, password: str) -> dict | None:
    if password != settings.FIXED_PASSWORD:
        return None
    return {
        "username": username,
        "email": f"{username}@local",
        "first_name": username,
        "last_name": "",
        "department": "",
    }


def _authenticate_ad(username: str, password: str) -> dict | None:
    try:
        import ldap3

        server = ldap3.Server(settings.AD_SERVER, get_info=ldap3.ALL)
        user_dn = f"{username}@{settings.AD_DOMAIN}"
        conn = ldap3.Connection(server, user=user_dn, password=password, auto_bind=True)

        conn.search(
            settings.AD_BASE_DN,
            f"(sAMAccountName={username})",
            attributes=["sAMAccountName", "displayName", "department", "mail"],
        )

        if not conn.entries:
            conn.unbind()
            return None

        entry = conn.entries[0]
        display_name = str(entry.displayName) if entry.displayName else username
        parts = display_name.split(" ", 1)
        first_name = parts[0]
        last_name = parts[1] if len(parts) > 1 else ""

        profile = {
            "username": str(entry.sAMAccountName),
            "email": str(entry.mail) if entry.mail else f"{username}@{settings.AD_DOMAIN}",
            "first_name": first_name,
            "last_name": last_name,
            "department": str(entry.department) if entry.department else "",
        }
        conn.unbind()
        return profile

    except Exception as e:
        logger.error("AD authentication failed: %s", e)
        return None
