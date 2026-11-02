"""Audit logging helper. Audit rows are written in the caller's transaction."""
from __future__ import annotations

from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from app.models import AuditLog, User


def audit(
    db: Session,
    action: str,
    *,
    actor: User | None = None,
    actor_type: str | None = None,
    entity_type: str | None = None,
    entity_id: Any = None,
    request: Request | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    ip = None
    ua = None
    if request is not None:
        ip = request.client.host if request.client else None
        ua = (request.headers.get("user-agent") or "")[:300]
    db.add(
        AuditLog(
            actor_user_id=actor.id if actor else None,
            actor_type=actor_type or ("STAFF" if actor else "ANONYMOUS"),
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            ip_address=ip,
            user_agent=ua,
            details=details,
        )
    )
