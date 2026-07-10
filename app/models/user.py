from datetime import datetime, timezone, timedelta

from sqlalchemy import Integer, String, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class User(Base):
    __tablename__ = "users"
    # username/email are unique *within a tenant*, not globally — two orgs can both
    # have "admin" or reuse an email.
    __table_args__ = (
        UniqueConstraint("tenant_id", "username", name="uq_users_tenant_username"),
        UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id"), nullable=False, index=True, server_default="1"
    )
    username: Mapped[str] = mapped_column(String(100), index=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # bcrypt hash for local (non-AD) accounts; NULL for AD-authenticated users
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    department: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(String(20), default="USER")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone(timedelta(hours=7)))
    )
