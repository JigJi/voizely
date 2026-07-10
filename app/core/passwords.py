"""Password hashing for non-AD tenants (email/password accounts we create).

AD-authenticated users (tenant 1 / company) have no password_hash — they are
verified against Active Directory. Tenants without AD (e.g. the gov pilot) get
local accounts whose bcrypt hash lives in users.password_hash.

Uses the `bcrypt` library directly (not passlib) to avoid passlib 1.7.x's broken
version probe against bcrypt 4.x. Output is standard $2b$ bcrypt, so existing
passlib-bcrypt hashes remain verifiable.
"""
import bcrypt

# bcrypt only hashes the first 72 bytes; encode once and reuse.
_MAX = 72


def hash_password(plain: str) -> str:
    pw = plain.encode("utf-8")[:_MAX]
    return bcrypt.hashpw(pw, bcrypt.gensalt()).decode("ascii")


def verify_password(plain: str, hashed: str | None) -> bool:
    if not hashed:
        return False
    try:
        return bcrypt.checkpw(plain.encode("utf-8")[:_MAX], hashed.encode("ascii"))
    except Exception:
        return False
