"""Tenant-scoping helpers for multi-tenancy.

Every tenant-owned model has a `tenant_id` column. These helpers are the default
way to (a) resolve the authenticated user from a JWT and (b) read tenant data, so
no query can accidentally cross a tenant boundary.
"""
from sqlalchemy.orm import Session

from app.models.user import User


def resolve_user(db: Session, payload: dict | None) -> User | None:
    """Load the User named by a decoded JWT payload, scoped to its tenant.

    Username is unique only within a tenant, so filter by (tenant_id, username)
    when the token carries a tenant id. Legacy tokens have no tid → fall back to
    username-only (safe while only tenant 1 exists; such tokens expire within a day).
    """
    if not payload or not payload.get("username"):
        return None
    q = db.query(User).filter(User.username == payload["username"])
    tid = payload.get("tenant_id")
    if tid is not None:
        q = q.filter(User.tenant_id == tid)
    return q.first()


def tenant_query(db: Session, model, current_user: User):
    """db.query(model) pre-filtered to the current user's tenant."""
    return db.query(model).filter(model.tenant_id == current_user.tenant_id)


def same_tenant(obj, current_user: User) -> bool:
    """True if obj belongs to the current user's tenant."""
    return getattr(obj, "tenant_id", None) == current_user.tenant_id
