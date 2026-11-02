"""Convert ORM objects into API payloads (staff views)."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Ticket,
    TicketAssignment,
    TicketAttachment,
    TicketComment,
    TicketStatusHistory,
    User,
    utcnow,
)
from app.schemas.tickets import (
    AssignmentOut,
    AttachmentOut,
    CommentOut,
    ContactOut,
    CustomerOut,
    DetailValue,
    HistoryOut,
    NamedRef,
    StatusRef,
    TicketDetailOut,
    TicketListItem,
    TicketPermissions,
    TransitionOut,
    UserRef,
)
from app.security import permissions as perm
from app.services import workflow


def _status(t: Ticket) -> StatusRef:
    s = t.status_ref
    return StatusRef(code=s.code, name_th=s.name_th, name_en=s.name_en, category=s.category, color=s.color)


def _is_overdue(t: Ticket) -> bool:
    return bool(t.due_at and t.due_at < utcnow() and t.status_ref.category in ("NEW", "OPEN", "WAITING"))


def _dept(t: Ticket) -> NamedRef:
    d = t.department
    return NamedRef(id=d.id, code=d.code, name_th=d.name_th, name_en=d.name_en)


def ticket_list_item(t: Ticket) -> TicketListItem:
    return TicketListItem(
        id=t.id, ticket_number=t.ticket_number, created_at=t.created_at, last_activity_at=t.last_activity_at,
        customer_name=t.customer.name, contact_name=t.contact.name, request_type_code=t.request_type.code,
        request_type_name_th=t.request_type.name_th, request_type_name_en=t.request_type.name_en, subject=t.subject,
        priority=t.priority, status=_status(t), department=_dept(t),
        assigned_user=UserRef(id=t.assigned_user.id, full_name=t.assigned_user.full_name) if t.assigned_user else None,
        due_at=t.due_at, is_overdue=_is_overdue(t), is_sample=t.is_sample,
    )


def attachment_out(a: TicketAttachment) -> AttachmentOut:
    return AttachmentOut(
        id=a.id, original_filename=a.original_filename, mime_type=a.mime_type, size_bytes=a.size_bytes, kind=a.kind,
        width=a.width, height=a.height, source=a.source, comment_id=a.comment_id,
        uploaded_by_name=a.uploaded_by.full_name if a.uploaded_by else None, created_at=a.created_at,
        url=f"/api/v1/attachments/{a.id}",
    )


def ticket_detail(db: Session, t: Ticket, user: User, staff_queue: bool) -> TicketDetailOut:
    history = db.scalars(select(TicketStatusHistory).where(TicketStatusHistory.ticket_id == t.id)
                         .order_by(TicketStatusHistory.created_at, TicketStatusHistory.id)).unique()
    assignments = db.scalars(select(TicketAssignment).where(TicketAssignment.ticket_id == t.id)
                             .order_by(TicketAssignment.created_at, TicketAssignment.id)).unique()
    comments = db.scalars(select(TicketComment).where(TicketComment.ticket_id == t.id)
                          .order_by(TicketComment.created_at, TicketComment.id)).unique()
    attachments = db.scalars(select(TicketAttachment).where(TicketAttachment.ticket_id == t.id,
                                                            TicketAttachment.deleted_at.is_(None))
                             .order_by(TicketAttachment.created_at)).unique()
    transitions = workflow.allowed_transitions(db, t, user)
    status_names = {}
    if transitions:
        from app.models import TicketStatus

        status_names = {s.code: s for s in db.scalars(select(TicketStatus))}
    can_manage = perm.can_manage_department(user, t.department_id)
    return TicketDetailOut(
        id=t.id, ticket_number=t.ticket_number,
        request_type=NamedRef(id=t.request_type.id, code=t.request_type.code, name_th=t.request_type.name_th,
                              name_en=t.request_type.name_en),
        subject=t.subject, description=t.description, category=t.category, priority=t.priority, status=_status(t),
        source=t.source, created_at=t.created_at, updated_at=t.updated_at, last_activity_at=t.last_activity_at,
        due_at=t.due_at, first_response_at=t.first_response_at, resolved_at=t.resolved_at, closed_at=t.closed_at,
        cancelled_at=t.cancelled_at, is_overdue=_is_overdue(t), is_sample=t.is_sample, anonymized_at=t.anonymized_at,
        privacy_consent_version=t.privacy_consent_version, privacy_consent_at=t.privacy_consent_at,
        customer=CustomerOut(id=t.customer.id, name=t.customer.name, customer_type=t.customer.customer_type,
                             code=t.customer.code),
        contact=ContactOut(id=t.contact.id, name=t.contact.name, department=t.contact.department,
                           phone=t.contact.phone, email=t.contact.email),
        department=_dept(t),
        assigned_user=UserRef(id=t.assigned_user.id, full_name=t.assigned_user.full_name) if t.assigned_user else None,
        details=[DetailValue(key=d.field_key, label_th=d.label_th, label_en=d.label_en,
                             value=(d.value_json or {}).get("label_th") if d.value_json else d.value_text)
                 for d in t.details],
        attachments=[attachment_out(a) for a in attachments],
        history=[HistoryOut(id=h.id, created_at=h.created_at, from_status=h.from_status, to_status=h.to_status,
                            actor_type=h.actor_type, actor_name=h.changed_by.full_name if h.changed_by else None,
                            comment=h.comment) for h in history],
        assignments=[AssignmentOut(
            id=a.id, created_at=a.created_at, assignment_type=a.assignment_type,
            from_department=a.from_department.name_th if a.from_department else None,
            to_department=a.to_department.name_th, from_user=a.from_user.full_name if a.from_user else None,
            to_user=a.to_user.full_name if a.to_user else None,
            assigned_by=a.assigned_by.full_name if a.assigned_by else None, priority=a.priority, due_at=a.due_at,
            reason=a.reason) for a in assignments],
        comments=[CommentOut(id=c.id, created_at=c.created_at, author_type=c.author_type,
                             author_name=c.author.full_name if c.author else None, visibility=c.visibility,
                             body=c.body) for c in comments],
        allowed_transitions=[TransitionOut(to_status=tr.to_status, name_th=status_names[tr.to_status].name_th,
                                           name_en=status_names[tr.to_status].name_en,
                                           requires_comment=tr.requires_comment) for tr in transitions],
        permissions=TicketPermissions(
            can_change_status=perm.can_change_status(user, t),
            can_assign=can_manage,
            can_self_assign=perm.can_self_assign(user, t) and t.assigned_user_id != user.id,
            can_transfer=perm.can_transfer(user, t),
            can_comment=perm.can_comment(user, t, staff_queue),
            can_upload=perm.can_comment(user, t, staff_queue),
            can_regenerate_token=can_manage or t.assigned_user_id == user.id,
        ),
    )
