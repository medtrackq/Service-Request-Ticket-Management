"""Customer tracking credentials and the customer-safe ticket view."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models import (
    FormDefinition,
    Ticket,
    TicketAttachment,
    TicketComment,
    TicketStatus,
    TicketStatusHistory,
    TicketTrackingToken,
    User,
    utcnow,
)
from app.security.tokens import new_token, sha256_hex
from app.services.form_engine import file_rules
from app.services.settings_service import get_setting


def issue_token(db: Session, ticket: Ticket, token: str | None = None, created_by: User | None = None) -> str:
    """Store a tracking token hash for the ticket and return the plain token (shown once)."""
    token = token or new_token(32)
    days = int(get_setting(db, "tracking.token_expiry_days") or 0)
    db.add(
        TicketTrackingToken(
            ticket_id=ticket.id, token_hash=sha256_hex(token), created_by_user_id=created_by.id if created_by else None,
            expires_at=utcnow() + timedelta(days=days) if days > 0 else None,
        )
    )
    return token


def regenerate_token(db: Session, ticket: Ticket, actor: User) -> str:
    db.execute(
        update(TicketTrackingToken)
        .where(TicketTrackingToken.ticket_id == ticket.id, TicketTrackingToken.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )
    return issue_token(db, ticket, created_by=actor)


def token_is_active(db: Session, ticket: Ticket, token: str) -> bool:
    row = db.scalar(select(TicketTrackingToken).where(TicketTrackingToken.token_hash == sha256_hex(token)))
    now = utcnow()
    return bool(row and row.ticket_id == ticket.id and row.revoked_at is None
                and (row.expires_at is None or row.expires_at > now))


def authenticate(db: Session, ticket_number: str, token: str) -> Ticket | None:
    """Return the ticket only if the token is valid for exactly this ticket number."""
    if not ticket_number or not token or len(token) > 128 or len(ticket_number) > 30:
        return None
    row = db.scalar(select(TicketTrackingToken).where(TicketTrackingToken.token_hash == sha256_hex(token)))
    if row is None or row.revoked_at is not None:
        return None
    now = utcnow()
    if row.expires_at is not None and row.expires_at <= now:
        return None
    ticket = db.get(Ticket, row.ticket_id)
    if ticket is None or ticket.ticket_number != ticket_number.strip().upper():
        return None
    row.last_used_at = now
    return ticket


def public_view(db: Session, ticket: Ticket) -> dict[str, Any]:
    """Customer-safe representation: no internal notes, staff identities or assignment data."""
    statuses = {s.code: s for s in db.scalars(select(TicketStatus))}
    timeline: list[dict[str, Any]] = []
    for h in db.scalars(
        select(TicketStatusHistory).where(TicketStatusHistory.ticket_id == ticket.id)
        .order_by(TicketStatusHistory.created_at, TicketStatusHistory.id)
    ):
        st = statuses.get(h.to_status)
        timeline.append({
            "type": "STATUS",
            "at": h.created_at,
            "status": h.to_status,
            "status_name_th": st.name_th if st else h.to_status,
            "status_name_en": st.name_en if st else h.to_status,
        })
    for c in db.scalars(
        select(TicketComment).where(TicketComment.ticket_id == ticket.id, TicketComment.visibility == "PUBLIC")
        .order_by(TicketComment.created_at)
    ):
        timeline.append({
            "type": "MESSAGE",
            "at": c.created_at,
            "author": "CUSTOMER" if c.author_type == "CUSTOMER" else "STAFF",
            "body": c.body,
        })
    timeline.sort(key=lambda e: (e["at"], 0 if e["type"] == "STATUS" else 1))
    customer_files = db.scalar(
        select(func.count()).select_from(TicketAttachment).where(
            TicketAttachment.ticket_id == ticket.id, TicketAttachment.source == "CUSTOMER",
            TicketAttachment.deleted_at.is_(None))
    ) or 0
    # Reply uploads follow the rules of the form version the ticket was submitted with.
    _, rules = file_rules(db.get(FormDefinition, ticket.form_definition_id))
    st = statuses[ticket.status]
    return {
        "ticket_number": ticket.ticket_number,
        "request_type_code": ticket.request_type.code,
        "request_type_slug": ticket.request_type.slug,
        "request_type_name_th": ticket.request_type.name_th,
        "request_type_name_en": ticket.request_type.name_en,
        "subject": ticket.subject,
        "created_at": ticket.created_at,
        "status": ticket.status,
        "status_name_th": st.name_th,
        "status_name_en": st.name_en,
        "status_category": st.category,
        "can_reply": not st.is_terminal and ticket.anonymized_at is None,
        "has_attachments": customer_files > 0,
        "reply_file_rules": {
            "max_files": max(rules.max_files - customer_files, 0),  # remaining for this ticket
            "max_size_mb": rules.max_size_mb,
            "accept": list(rules.accept),
        },
        "timeline": timeline,
    }
