"""Server-side staff sessions (httpOnly cookie + CSRF double-submit token)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import User, UserSession, utcnow
from app.security.tokens import new_token, sha256_hex

# Avoid a DB write on every request: refresh last_seen_at at most once per minute.
_TOUCH_INTERVAL = timedelta(seconds=60)


@dataclass
class NewSession:
    token: str
    csrf_token: str
    session: UserSession


def create_session(db: Session, user: User, ip: str | None, user_agent: str | None) -> NewSession:
    settings = get_settings()
    token = new_token(32)
    csrf = new_token(24)
    now = utcnow()
    row = UserSession(
        token_hash=sha256_hex(token),
        csrf_token=csrf,
        user_id=user.id,
        created_at=now,
        last_seen_at=now,
        expires_at=now + timedelta(hours=settings.session_absolute_hours),
        ip_address=ip,
        user_agent=(user_agent or "")[:300],
    )
    db.add(row)
    db.flush()
    return NewSession(token=token, csrf_token=csrf, session=row)


def load_session(db: Session, token: str | None) -> UserSession | None:
    """Return a valid session or None. Enforces absolute expiry, idle timeout and active user."""
    if not token or len(token) > 200:
        return None
    settings = get_settings()
    row = db.scalar(select(UserSession).where(UserSession.token_hash == sha256_hex(token)))
    if row is None or row.revoked_at is not None:
        return None
    now = utcnow()
    if row.expires_at <= now:
        return None
    if row.last_seen_at + timedelta(minutes=settings.session_idle_minutes) <= now:
        return None
    if not row.user.is_active:
        return None
    if now - row.last_seen_at >= _TOUCH_INTERVAL:
        row.last_seen_at = now
        db.commit()
    return row


def revoke_session(db: Session, row: UserSession) -> None:
    row.revoked_at = utcnow()


def revoke_all_sessions(db: Session, user_id: int, except_session_id: int | None = None) -> None:
    stmt = update(UserSession).where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
    if except_session_id is not None:
        stmt = stmt.where(UserSession.id != except_session_id)
    db.execute(stmt.values(revoked_at=utcnow()))
