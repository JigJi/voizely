import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy.orm import Session

from app.config import settings
from app.models.user import User

logger = logging.getLogger(__name__)


def authenticate(username: str, password: str, db: Session) -> User | None:
    """Authenticate user. Returns User on success, None on failure."""
    if settings.AD_ENABLED:
        profile = _authenticate_ad(username, password)
    else:
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

    user.last_login_at = datetime.now(timezone(timedelta(hours=7)))
    db.commit()
    db.refresh(user)
    return user


def _authenticate_fixed(username: str, password: str) -> dict | None:
    if username == settings.FIXED_USERNAME and password == settings.FIXED_PASSWORD:
        return {
            "username": username,
            "email": f"{username}@local",
            "first_name": "Admin",
            "last_name": "",
            "department": "Dev",
        }
    return None


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
