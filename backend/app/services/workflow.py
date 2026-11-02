"""Ticket status workflow with configurable transitions and role permissions."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Ticket, TicketComment, TicketStatus, TicketStatusHistory, User, WorkflowTransition, utcnow
from app.security import permissions as perm
from app.services import notifications
from app.services.errors import Forbidden, ValidationFailed

REOPEN_FROM = ("RESOLVED", "CLOSED", "CANCELLED")


def get_status(db: Session, code: str) -> TicketStatus:
    st = db.get(TicketStatus, code)
    if st is None or not st.is_active:
        raise ValidationFailed("สถานะไม่ถูกต้อง", fields={"to_status": "สถานะไม่ถูกต้อง"})
    return st


def allowed_transitions(db: Session, ticket: Ticket, user: User) -> list[WorkflowTransition]:
    if not perm.can_change_status(user, ticket):
        return []
    rows = db.scalars(
        select(WorkflowTransition)
        .join(TicketStatus, TicketStatus.code == WorkflowTransition.to_status)
        .where(WorkflowTransition.from_status == ticket.status, WorkflowTransition.is_active.is_(True),
               TicketStatus.is_active.is_(True))
        .order_by(TicketStatus.sort_order)
    )
    return [t for t in rows if user.role in (t.allowed_roles or [])]


def _apply(db: Session, ticket: Ticket, new: TicketStatus, *, actor: User | None, actor_type: str,
           comment: str | None) -> TicketStatusHistory:
    old_code = ticket.status
    now = utcnow()
    ticket.status = new.code
    ticket.status_ref = new
    ticket.last_activity_at = now
    if new.code == "RESOLVED":
        ticket.resolved_at = now
    elif new.code == "CLOSED":
        ticket.closed_at = now
        if ticket.resolved_at is None:
            ticket.resolved_at = now
    elif new.code == "CANCELLED":
        ticket.cancelled_at = now
    if old_code in REOPEN_FROM and new.category not in ("RESOLVED", "CLOSED", "CANCELLED"):
        ticket.resolved_at = None
        ticket.closed_at = None
        ticket.cancelled_at = None
    if actor_type == "STAFF" and ticket.first_response_at is None:
        ticket.first_response_at = now  # status changes are visible on the customer timeline
    hist = TicketStatusHistory(
        ticket_id=ticket.id, from_status=old_code, to_status=new.code, created_at=now,
        changed_by_user_id=actor.id if actor else None, actor_type=actor_type, comment=comment or None,
    )
    db.add(hist)
    return hist


def change_status(db: Session, ticket: Ticket, actor: User, to_status: str, *, comment: str | None,
                  public_message: str | None) -> TicketStatusHistory:
    if to_status == ticket.status:
        raise ValidationFailed("Ticket อยู่ในสถานะนี้แล้ว", fields={"to_status": "สถานะเดิม"})
    if not perm.can_change_status(actor, ticket):
        raise Forbidden("ท่านไม่มีสิทธิ์เปลี่ยนสถานะ Ticket นี้")
    transition = db.scalar(
        select(WorkflowTransition).where(
            WorkflowTransition.from_status == ticket.status, WorkflowTransition.to_status == to_status,
            WorkflowTransition.is_active.is_(True),
        )
    )
    if transition is None:
        raise ValidationFailed("ไม่สามารถเปลี่ยนเป็นสถานะนี้ได้จากสถานะปัจจุบัน",
                               fields={"to_status": "ไม่อนุญาตตาม Workflow"}, code="TRANSITION_NOT_ALLOWED")
    if actor.role not in (transition.allowed_roles or []):
        raise Forbidden("บทบาทของท่านไม่ได้รับอนุญาตให้เปลี่ยนเป็นสถานะนี้", code="TRANSITION_ROLE_FORBIDDEN")
    comment = (comment or "").strip() or None
    public_message = (public_message or "").strip() or None
    if transition.requires_comment and not (comment or public_message):
        raise ValidationFailed("กรุณาระบุเหตุผลหรือหมายเหตุ", fields={"comment": "จำเป็นต้องระบุ"})
    if to_status == "WAITING_CUSTOMER" and not public_message:
        raise ValidationFailed("กรุณาระบุข้อมูลที่ต้องการจากลูกค้า (ลูกค้าจะเห็นข้อความนี้)",
                               fields={"public_message": "จำเป็นต้องระบุ"})
    new = get_status(db, to_status)
    hist = _apply(db, ticket, new, actor=actor, actor_type="STAFF", comment=comment)
    if public_message:
        db.add(TicketComment(ticket_id=ticket.id, author_user_id=actor.id, author_type="STAFF",
                             visibility="PUBLIC", body=public_message, created_at=hist.created_at))
    notifications.status_changed(db, ticket, new, public_message, actor)
    db.flush()
    return hist


def system_transition(db: Session, ticket: Ticket, to_status: str, comment: str, *, actor: User | None = None,
                      actor_type: str = "SYSTEM") -> TicketStatusHistory | None:
    """Automatic transition triggered by another action (assignment, customer reply).

    Recorded in history like any other change; not subject to role rules because the
    triggering action was itself authorised."""
    if ticket.status == to_status:
        return None
    return _apply(db, ticket, get_status(db, to_status), actor=actor, actor_type=actor_type, comment=comment)
