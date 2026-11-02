"""In-app notification inbox for staff."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.db import get_db
from app.models import Ticket, TicketNotification, User, utcnow
from app.services.errors import NotFound

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _inbox(user: User):
    return (TicketNotification.recipient_user_id == user.id, TicketNotification.channel == "IN_APP")


@router.get("")
def list_notifications(unread_only: bool = False, page: int = Query(default=1, ge=1),
                       page_size: int = Query(default=20, ge=1, le=100), user: User = Depends(current_user),
                       db: Session = Depends(get_db)) -> dict[str, Any]:
    conds = list(_inbox(user))
    if unread_only:
        conds.append(TicketNotification.read_at.is_(None))
    total = db.scalar(select(func.count()).select_from(TicketNotification).where(*conds)) or 0
    rows = db.execute(
        select(TicketNotification, Ticket.ticket_number)
        .outerjoin(Ticket, Ticket.id == TicketNotification.ticket_id)
        .where(*conds).order_by(TicketNotification.created_at.desc(), TicketNotification.id.desc())
        .limit(page_size).offset((page - 1) * page_size)
    ).all()
    return {
        "items": [{"id": n.id, "event_type": n.event_type, "subject": n.subject, "body": n.body,
                   "ticket_id": n.ticket_id, "ticket_number": num, "link_url": n.link_url,
                   "created_at": n.created_at, "read_at": n.read_at} for n, num in rows],
        "total": total, "page": page, "page_size": page_size,
    }


@router.get("/unread-count")
def unread_count(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict[str, int]:
    count = db.scalar(select(func.count()).select_from(TicketNotification)
                      .where(*_inbox(user), TicketNotification.read_at.is_(None))) or 0
    return {"count": count}


@router.post("/{notification_id}/read")
def mark_read(notification_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    n = db.get(TicketNotification, notification_id)
    if n is None or n.recipient_user_id != user.id or n.channel != "IN_APP":
        raise NotFound("ไม่พบการแจ้งเตือน")
    if n.read_at is None:
        n.read_at = utcnow()
        db.commit()
    return {"message": "ok"}


@router.post("/read-all")
def mark_all_read(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    db.execute(update(TicketNotification).where(*_inbox(user), TicketNotification.read_at.is_(None))
               .values(read_at=utcnow()))
    db.commit()
    return {"message": "ok"}
