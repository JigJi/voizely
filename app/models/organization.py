from datetime import datetime, timezone, timedelta

from sqlalchemy import Integer, String, Boolean, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Organization(Base):
    """A tenant. Every user / transcription / recording belongs to exactly one org.

    tenant_id=1 is the original (legacy) organization — created by the multi-tenant
    migration and back-filled onto all pre-existing rows. Its ad_config is left NULL
    so the app falls back to the global AD_* env settings (backward compatible).
    """
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # 'cloud' = Deepgram + Gemini APIs (default), 'local' = on-box GPU pipeline only
    # (no audio leaves the server — the "Sovereign" tier for gov customers).
    pipeline_mode: Mapped[str] = mapped_column(String(20), default="cloud", nullable=False)

    # Email domains that resolve to this tenant at login, e.g. ["doh.go.th"].
    # A user typing officer@doh.go.th is routed here automatically — no org code.
    email_domains: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Per-tenant AD settings: {"server": ..., "domain": ..., "base_dn": ...}.
    # NULL → use global AD_* env settings (legacy tenant 1).
    ad_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Per-tenant branding: {"display_name": ..., "logo_url": ..., "primary_color": ...}
    branding: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone(timedelta(hours=7)))
    )
