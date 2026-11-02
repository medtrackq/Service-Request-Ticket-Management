"""Staff ticket management API."""
from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.csv_utils import csv_response
from app.api.deps import current_user, staff_queue_enabled
from app.db import get_db
from app.models import Ticket, TicketAttachment, User
from app.schemas.common import Page
from app.schemas.tickets import (
    AssignIn,
    BulkAssignIn,
    BulkResult,
    CommentIn,
    StatusChangeIn,
    TicketDetailOut,
    TicketListItem,
    TokenOut,
)
from app.security import permissions as perm
from app.services import assignment, files, tracking, workflow
from app.services.audit import audit
from app.services.errors import DomainError, Forbidden, NotFound
from app.services.notifications import tracking_url
from app.services.serializers import attachment_out, ticket_detail, ticket_list_item
from app.services.ticket_query import TicketFilters, list_statement
from app.services.ticket_service import add_staff_comment, staff_upload

router = APIRouter(tags=["tickets"])


def ticket_filters(
    q: str | None = Query(default=None, max_length=100),
    status_: str | None = Query(default=None, alias="status", description="Comma separated status codes"),
    status_category: str | None = Query(default=None, pattern="^(ACTIVE|NEW|OPEN|WAITING|RESOLVED|CLOSED|CANCELLED)$"),
    request_type: str | None = Query(default=None, max_length=30),
    department_id: int | None = None,
    assigned: str | None = Query(default=None, max_length=12, description="me | none | <user id>"),
    priority: str | None = Query(default=None, pattern="^(LOW|NORMAL|HIGH|URGENT)$"),
    date_from: date | None = None,
    date_to: date | None = None,
    overdue: bool | None = None,
    include_sample: bool = True,
) -> TicketFilters:
    return TicketFilters(
        q=q, statuses=[s for s in (status_ or "").split(",") if s], status_category=status_category,
        request_type=request_type, department_id=department_id, assigned=assigned, priority=priority,
        date_from=date_from, date_to=date_to, overdue=overdue, include_sample=include_sample,
    )


def load_ticket(db: Session, ticket_id: int, user: User, *, for_update: bool = False) -> Ticket:
    stmt = select(Ticket).where(Ticket.id == ticket_id)
    if for_update:
        stmt = stmt.with_for_update(of=Ticket)
    ticket = db.scalar(stmt)
    # Same response for "missing" and "not allowed" so ticket IDs cannot be probed.
    if ticket is None or not perm.can_view(user, ticket, staff_queue_enabled(db)):
        raise NotFound("ไม่พบ Ticket", code="TICKET_NOT_FOUND")
    return ticket


@router.get("/tickets", response_model=Page[TicketListItem])
def list_tickets(
    filters: TicketFilters = Depends(ticket_filters),
    sort: str = Query(default="created_at"),
    direction: str = Query(default="desc", pattern="^(asc|desc)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> Page[TicketListItem]:
    stmt = list_statement(user, filters, staff_queue_enabled(db), sort, direction)
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    rows = db.scalars(stmt.limit(page_size).offset((page - 1) * page_size)).unique()
    return Page(items=[ticket_list_item(t) for t in rows], total=total, page=page, page_size=page_size)


@router.get("/tickets/export.csv")
def export_tickets(
    request: Request,
    filters: TicketFilters = Depends(ticket_filters),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    if not perm.can_export(user):
        raise Forbidden("ท่านไม่มีสิทธิ์ส่งออกข้อมูล")
    stmt = list_statement(user, filters, staff_queue_enabled(db)).limit(20_000)
    tickets = list(db.scalars(stmt).unique())
    audit(db, "ticket.export_csv", actor=user, request=request, details={"rows": len(tickets)})
    db.commit()
    header = ["Ticket Number", "Created", "Customer", "Contact", "Phone", "Request Type", "Subject", "Priority",
              "Status", "Department", "Assigned Staff", "Due", "First Response", "Resolved", "Closed",
              "Last Updated", "Sample"]
    rows = (
        [t.ticket_number, t.created_at, t.customer.name, t.contact.name, t.contact.phone, t.request_type.name_th,
         t.subject, t.priority, t.status_ref.name_th, t.department.name_th,
         t.assigned_user.full_name if t.assigned_user else "", t.due_at, t.first_response_at, t.resolved_at,
         t.closed_at, t.last_activity_at, "Y" if t.is_sample else ""]
        for t in tickets
    )
    return csv_response("tickets.csv", header, rows)


@router.post("/tickets/bulk-assign", response_model=BulkResult)
def bulk_assign(body: BulkAssignIn, request: Request, user: User = Depends(current_user),
                db: Session = Depends(get_db)) -> BulkResult:
    if user.role not in ("ADMIN", "MANAGER"):
        raise Forbidden("ท่านไม่มีสิทธิ์มอบหมายงานแบบกลุ่ม")
    updated: list[str] = []
    failed: list[dict] = []
    for tid in dict.fromkeys(body.ticket_ids):
        try:
            ticket = load_ticket(db, tid, user, for_update=True)
            assignment.assign(db, ticket, user, department_id=body.department_id,
                              assigned_user_id=body.assigned_user_id, unassign=body.unassign,
                              priority=body.priority, due_at=body.due_at, reason=body.reason)
            audit(db, "ticket.bulk_assign", actor=user, entity_type="ticket", entity_id=tid, request=request,
                  details=body.model_dump(mode="json", exclude={"ticket_ids"}))
            db.commit()
            updated.append(ticket.ticket_number)
        except DomainError as exc:
            db.rollback()
            failed.append({"ticket_id": tid, "code": exc.code, "message": exc.message})
    return BulkResult(updated=updated, failed=failed)


@router.get("/tickets/{ticket_id}", response_model=TicketDetailOut)
def get_ticket(ticket_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> TicketDetailOut:
    ticket = load_ticket(db, ticket_id, user)
    return ticket_detail(db, ticket, user, staff_queue_enabled(db))


@router.post("/tickets/{ticket_id}/status", response_model=TicketDetailOut)
def change_status(ticket_id: int, body: StatusChangeIn, request: Request, user: User = Depends(current_user),
                  db: Session = Depends(get_db)) -> TicketDetailOut:
    ticket = load_ticket(db, ticket_id, user, for_update=True)
    old = ticket.status
    workflow.change_status(db, ticket, user, body.to_status, comment=body.comment, public_message=body.public_message)
    audit(db, "ticket.status_changed", actor=user, entity_type="ticket", entity_id=ticket.id, request=request,
          details={"from": old, "to": body.to_status})
    db.commit()
    return ticket_detail(db, ticket, user, staff_queue_enabled(db))


@router.post("/tickets/{ticket_id}/assign", response_model=None,
             responses={200: {"description": "Ticket detail, or {code: TRANSFERRED_OUT} when the caller "
                                             "transferred the ticket out of their own access scope"}})
def assign_ticket(ticket_id: int, body: AssignIn, request: Request, user: User = Depends(current_user),
                  db: Session = Depends(get_db)) -> dict:
    ticket = load_ticket(db, ticket_id, user, for_update=True)
    assignment.assign(db, ticket, user, department_id=body.department_id, assigned_user_id=body.assigned_user_id,
                      unassign=body.unassign, priority=body.priority, due_at=body.due_at, reason=body.reason)
    audit(db, "ticket.assigned", actor=user, entity_type="ticket", entity_id=ticket.id, request=request,
          details=body.model_dump(mode="json"))
    db.commit()
    db.refresh(ticket)
    queue = staff_queue_enabled(db)
    if not perm.can_view(user, ticket, queue):
        # e.g. staff transferred the ticket out of their own department
        return {"code": "TRANSFERRED_OUT", "ticket_number": ticket.ticket_number,
                "message": "โอนงานเรียบร้อยแล้ว Ticket นี้ไม่อยู่ในขอบเขตสิทธิ์ของท่านแล้ว"}
    return ticket_detail(db, ticket, user, queue).model_dump(mode="json")


@router.post("/tickets/{ticket_id}/comments", response_model=TicketDetailOut)
def add_comment(ticket_id: int, body: CommentIn, request: Request, user: User = Depends(current_user),
                db: Session = Depends(get_db)) -> TicketDetailOut:
    ticket = load_ticket(db, ticket_id, user, for_update=True)
    if not perm.can_comment(user, ticket, staff_queue_enabled(db)):
        raise Forbidden("ท่านไม่มีสิทธิ์แสดงความคิดเห็น")
    add_staff_comment(db, ticket, user, body.body, body.visibility)
    audit(db, "ticket.comment_added", actor=user, entity_type="ticket", entity_id=ticket.id, request=request,
          details={"visibility": body.visibility})
    db.commit()
    return ticket_detail(db, ticket, user, staff_queue_enabled(db))


@router.post("/tickets/{ticket_id}/attachments", response_model=TicketDetailOut)
def upload_attachments(ticket_id: int, request: Request, files_: list[UploadFile] = File(alias="files"),
                       user: User = Depends(current_user), db: Session = Depends(get_db)) -> TicketDetailOut:
    ticket = load_ticket(db, ticket_id, user)
    staff_upload(db, ticket, user, files_, request=request)
    return ticket_detail(db, ticket, user, staff_queue_enabled(db))


@router.post("/tickets/{ticket_id}/tracking-token", response_model=TokenOut)
def regenerate_tracking_token(ticket_id: int, request: Request, user: User = Depends(current_user),
                              db: Session = Depends(get_db)) -> TokenOut:
    """Revoke existing tracking links and issue a new one (e.g. customer lost the link)."""
    ticket = load_ticket(db, ticket_id, user, for_update=True)
    if not (perm.can_manage_department(user, ticket.department_id) or ticket.assigned_user_id == user.id):
        raise Forbidden("ท่านไม่มีสิทธิ์ออกลิงก์ติดตามใหม่")
    token = tracking.regenerate_token(db, ticket, user)
    audit(db, "ticket.tracking_token_regenerated", actor=user, entity_type="ticket", entity_id=ticket.id,
          request=request)
    db.commit()
    return TokenOut(ticket_number=ticket.ticket_number, tracking_token=token,
                    tracking_url=tracking_url(ticket.ticket_number, token))


@router.get("/attachments/{attachment_id}")
def download_attachment(attachment_id: uuid.UUID, request: Request, download: bool = False,
                        user: User = Depends(current_user), db: Session = Depends(get_db)):
    att = db.get(TicketAttachment, attachment_id)
    if att is None or att.deleted_at is not None:
        raise NotFound("ไม่พบไฟล์")
    load_ticket(db, att.ticket_id, user)  # authorisation: must be able to view the ticket
    try:
        path = files.resolve_stored(att.stored_path)
    except ValueError:
        raise NotFound("ไม่พบไฟล์") from None
    if not path.is_file():
        raise NotFound("ไม่พบไฟล์")
    if download:
        audit(db, "attachment.downloaded", actor=user, entity_type="attachment", entity_id=att.id, request=request)
        db.commit()
    inline = att.kind == "IMAGE" and not download
    return FileResponse(
        path, media_type=att.mime_type, filename=att.original_filename,
        content_disposition_type="inline" if inline else "attachment",
        headers={"Cache-Control": "private, max-age=300", "X-Content-Type-Options": "nosniff",
                 "Content-Security-Policy": "default-src 'none'; img-src 'self'; sandbox"},
    )


__all__ = ["router", "attachment_out", "load_ticket", "ticket_filters"]
