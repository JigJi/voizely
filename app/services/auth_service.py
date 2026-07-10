import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy.orm import Session

from app.config import settings
from app.core.passwords import verify_password
from app.models.user import User

logger = logging.getLogger(__name__)


def authenticate(username: str, password: str, db: Session, org_slug: str = "default") -> User | None:
    """Authenticate a user within a tenant (resolved by org slug).

    Order: per-tenant AD (or global AD for the default org) → local password_hash
    → legacy global fixed-password (default org / dev only).
    """
    org = _resolve_org(db, username, org_slug)
    if not org:
        logger.info("login rejected: cannot resolve org (slug='%s', user='%s')", org_slug, username)
        return None

    # 1. AD path — per-tenant config, or global env settings for the default org
    ad_cfg = _resolve_ad_config(org)
    if ad_cfg:
        profile = _authenticate_ad(username, password, ad_cfg)
        if profile:
            return upsert_user_from_profile(db, profile, org.id)
        logger.info("AD auth failed for %s in org '%s'", username, org_slug)

    # 2. Local password path — per-user bcrypt hash within this tenant
    user = db.query(User).filter(
        User.tenant_id == org.id,
        User.username == username,
    ).first()
    if user and user.is_active and verify_password(password, user.password_hash):
        user.last_login_at = datetime.now(timezone(timedelta(hours=7)))
        db.commit()
        return user

    # 3. Legacy global fixed-password fallback (default org / dev only)
    if org.id == 1 and settings.FIXED_PASSWORD and password == settings.FIXED_PASSWORD:
        profile = _authenticate_fixed(username, password)
        if profile:
            return upsert_user_from_profile(db, profile, org.id)

    return None


def _resolve_org(db: Session, username: str, org_slug: str = "default"):
    """Pick the tenant for a login attempt.

    Priority: explicit non-default slug (override / pre-domain fallback) → email
    domain of the username (officer@doh.go.th → the org owning 'doh.go.th') →
    the default (main company) tenant.
    """
    from app.models.organization import Organization

    if org_slug and org_slug != "default":
        return db.query(Organization).filter(
            Organization.slug == org_slug, Organization.is_active == True
        ).first()

    if "@" in username:
        domain = username.rsplit("@", 1)[1].strip().lower()
        if domain:
            for o in db.query(Organization).filter(Organization.is_active == True).all():
                if domain in [d.strip().lower() for d in (o.email_domains or [])]:
                    return o

    return db.query(Organization).filter(
        Organization.slug == "default", Organization.is_active == True
    ).first()


def _resolve_ad_config(org) -> dict | None:
    """AD connection settings for a tenant, or None if it doesn't use AD.

    Per-tenant ad_config wins; the default org (tenant 1) falls back to global
    AD_* env settings for backward compatibility.
    """
    if org.ad_config and org.ad_config.get("server"):
        return org.ad_config
    if org.id == 1 and settings.AD_ENABLED and settings.AD_SERVER:
        return {
            "server": settings.AD_SERVER,
            "domain": settings.AD_DOMAIN,
            "base_dn": settings.AD_BASE_DN,
        }
    return None


def upsert_user_from_profile(db: Session, profile: dict, tenant_id: int = 1) -> User:
    """Upsert user record from AD/external profile + sync SpeakerProfile if AD source."""
    user = db.query(User).filter(
        User.tenant_id == tenant_id,
        User.username == profile["username"],
    ).first()
    if not user:
        user = User(
            tenant_id=tenant_id,
            username=profile["username"],
            email=profile.get("email"),
            first_name=profile.get("first_name"),
            last_name=profile.get("last_name"),
            department=profile.get("department"),
        )
        db.add(user)
    else:
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

    # Auto-sync SpeakerProfile if profile has real email (not @local placeholder)
    email = profile.get("email", "")
    if email and "@local" not in email:
        _sync_speaker_profile(db, profile, tenant_id)

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


def _sync_speaker_profile(db: Session, profile: dict, tenant_id: int = 1):
    """Auto-create/update SpeakerProfile from AD user data."""
    try:
        from app.models.transcription import SpeakerProfile
        nickname = profile.get("first_name") or profile.get("username", "")
        if not nickname:
            return

        existing = db.query(SpeakerProfile).filter(
            SpeakerProfile.tenant_id == tenant_id,
            SpeakerProfile.email == profile.get("email"),
        ).first()

        if existing:
            # Update from AD but only if source is "ad"
            if existing.source == "ad":
                existing.full_name = f"{profile.get('first_name', '')} {profile.get('last_name', '')}".strip()
                existing.department = profile.get("department", "")
                existing.organization = profile.get("organization", "")
                existing.updated_at = datetime.now(timezone(timedelta(hours=7)))
        else:
            # Handle nickname collision within the tenant: first_name → +dept_short → username
            def _nick_taken(n):
                return db.query(SpeakerProfile).filter(
                    SpeakerProfile.tenant_id == tenant_id,
                    SpeakerProfile.nickname == n,
                ).first() is not None
            if _nick_taken(nickname):
                dept_short = _shorten_department(profile.get("department", ""))
                if dept_short and not _nick_taken(f"{nickname} {dept_short}"):
                    nickname = f"{nickname} {dept_short}"
                else:
                    nickname = profile.get("username", nickname)

            p = SpeakerProfile(
                tenant_id=tenant_id,
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


def _authenticate_ad(username: str, password: str, cfg: dict) -> dict | None:
    """Bind against a tenant's AD using its connection config (server/domain/base_dn)."""
    try:
        import ldap3

        domain = cfg.get("domain", "")
        base_dn = cfg.get("base_dn", "")
        server = ldap3.Server(cfg["server"], get_info=ldap3.ALL)
        user_dn = f"{username}@{domain}"
        conn = ldap3.Connection(server, user=user_dn, password=password, auto_bind=True)

        conn.search(
            base_dn,
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
            "email": str(entry.mail) if entry.mail else f"{username}@{domain}",
            "first_name": first_name,
            "last_name": last_name,
            "department": str(entry.department) if entry.department else "",
        }
        conn.unbind()
        return profile

    except Exception as e:
        logger.error("AD authentication failed: %s", e)
        return None
