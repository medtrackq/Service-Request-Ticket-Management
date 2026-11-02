"""Ticket creation (customer submission), comments, customer replies and staff uploads."""
from __future__ import annotations

import hashlib
import json
import logging
import re
import uuid
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from fastapi import Request, UploadFile
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.integrations.line.liff import LiffVerificationError, verify_liff_id_token
from app.models import (
    Department,
    FormDefinition,
    Ticket,
    TicketAssignment,
    TicketAttachment,
    TicketComment,
    TicketDetail,
    TicketStatus,
    TicketStatusHistory,
    User,
    utcnow,
)
from app.security.tokens import derive_tracking_token
from app.services import assignment, customers, files, notifications, tracking, workflow
from app.services.audit import audit
from app.services.errors import Conflict, ValidationFailed
from app.services.form_engine import (
    DOCUMENT_MIME,
    IMAGE_MIME,
    FileRules,
    file_rules,
    get_active_form_by_slug,
    render_subject,
    validate_submission,
)
from app.services.settings_service import get_setting, service_target_hours

log = logging.getLogger(__name__)
IDEMPOTENCY_RE = re.compile(r"^[A-Za-z0-9_-]{16,64}$")
MAX_MESSAGE = 5000
# Values stored in normalised tables/columns (customers, customer_contacts, tickets) — not repeated in ticket_details.
# ticket.priority / ticket.category are kept in ticket_details too, to preserve the customer's chosen label.
NORMALIZED_MAPPINGS = ("customer.name", "customer.customer_type", "contact.name", "contact.department",
                       "contact.phone", "contact.email", "ticket.description")


@dataclass
class SubmissionResult:
    ticket: Ticket
    tracking_token: str | None
    replayed: bool


def _submission_hash(values: dict[str, Any], uploads: list[UploadFile]) -> str:
    payload = {
        "values": values,
        "files": sorted([(u.filename or "", u.size or 0) for u in uploads]),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str, ensure_ascii=False).encode()).hexdigest()


def _replay(db: Session, ticket: Ticket, idem_key: str, submission_hash: str) -> SubmissionResult:
    if ticket.submission_hash and ticket.submission_hash != submission_hash:
        raise Conflict("รหัสการส่งแบบฟอร์มนี้ถูกใช้กับข้อมูลอื่นแล้ว กรุณาโหลดหน้าใหม่", code="IDEMPOTENCY_KEY_REUSED")
    token = derive_tracking_token(idem_key)
    return SubmissionResult(ticket, token if tracking.token_is_active(db, ticket, token) else None, True)


def submit_request(
    db: Session,
    *,
    slug: str,
    form_definition_id: int | None,
    values: dict[str, Any],
    privacy_consent: bool,
    uploads: list[UploadFile],
    idempotency_key: str | None,
    client_ip: str | None,
    line_id_token: str | None = None,
    request: Request | None = None,
) -> SubmissionResult:
    form = get_active_form_by_slug(db, slug)
    if form_definition_id is not None and form_definition_id != form.id:
        raise Conflict("แบบฟอร์มมีการปรับปรุง กรุณาโหลดหน้าใหม่แล้วส่งอีกครั้ง", code="FORM_VERSION_CHANGED")
    if not privacy_consent:
        raise ValidationFailed("กรุณายอมรับประกาศความเป็นส่วนตัวก่อนส่งคำขอ",
                               fields={"privacy_consent": "กรุณายอมรับประกาศความเป็นส่วนตัว"})
    cleaned = validate_submission(form, values)

    if idempotency_key is not None and not IDEMPOTENCY_RE.match(idempotency_key):
        raise ValidationFailed("Idempotency-Key ไม่ถูกต้อง")
    idem_key = idempotency_key or uuid.uuid4().hex
    sub_hash = _submission_hash(cleaned.values, uploads)

    existing = db.scalar(select(Ticket).where(Ticket.idempotency_key == idem_key))
    if existing is not None:
        return _replay(db, existing, idem_key, sub_hash)

    _, rules = file_rules(form)
    received = files.receive_uploads(uploads, rules)

    line_user_id = None
    if line_id_token:
        try:
            line_user_id = verify_liff_id_token(line_id_token)
        except LiffVerificationError as exc:  # never block a customer because LINE is unavailable
            log.warning("LIFF ID token rejected: %s", exc)

    stored: list[str] = []
    try:
        result = _create(db, form, cleaned, received, stored, idem_key=idem_key, sub_hash=sub_hash,
                         client_ip=client_ip, line_user_id=line_user_id, request=request)
        db.commit()
        return result
    except IntegrityError as exc:
        db.rollback()
        files.remove_stored(stored)
        files.discard(received)
        if "idempotency_key" in str(exc.orig):
            existing = db.scalar(select(Ticket).where(Ticket.idempotency_key == idem_key))
            if existing is not None:
                return _replay(db, existing, idem_key, sub_hash)
        raise
    except BaseException:
        db.rollback()
        files.remove_stored(stored)
        files.discard(received)
        raise


def _create(db: Session, form: FormDefinition, cleaned, received: list[files.ValidatedFile], stored: list[str], *,
            idem_key: str, sub_hash: str, client_ip: str | None, line_user_id: str | None,
            request: Request | None) -> SubmissionResult:
    from app.services.ticket_numbers import allocate_ticket_number

    rt = form.request_type
    m = cleaned.mapped
    customer = customers.find_or_create_customer(db, m["customer.name"], m.get("customer.customer_type"))
    contact = customers.find_or_create_contact(
        db, customer, name=m["contact.name"], department=m.get("contact.department"),
        phone=m.get("contact.phone"), email=m.get("contact.email"), line_user_id=line_user_id,
    )
    now = utcnow()
    number = allocate_ticket_number(db, rt, now)
    priority = m.get("ticket.priority") or rt.default_priority
    category = m.get("ticket.category")
    initial = assignment.resolve_initial(db, rt, category=category, customer_type=customer.customer_type,
                                         priority=priority)
    department = db.get(Department, initial.department_id)
    assignee = db.get(User, initial.user_id) if initial.user_id else None
    hours = service_target_hours(db, priority, "resolution_hours")

    ticket = Ticket(
        ticket_number=number, request_type=rt, request_type_id=rt.id, form_definition_id=form.id,
        customer=customer, customer_id=customer.id, contact=contact, contact_id=contact.id,
        subject=render_subject(form, cleaned), description=m["ticket.description"], category=category,
        priority=priority, status="NEW", status_ref=db.get(TicketStatus, "NEW"),
        department=department, department_id=department.id,
        assigned_user=assignee, assigned_user_id=assignee.id if assignee else None,
        due_at=now + timedelta(hours=hours) if hours else None, last_activity_at=now,
        source="LINE" if line_user_id else "WEB", line_user_id=line_user_id,
        idempotency_key=idem_key, submission_hash=sub_hash,
        privacy_consent_version=str(get_setting(db, "privacy.notice_version")), privacy_consent_at=now,
        submitter_ip=client_ip, created_at=now, updated_at=now,
    )
    db.add(ticket)
    db.flush()

    for f in form.fields:
        if f.field_type == "file" or f.maps_to in NORMALIZED_MAPPINGS:
            continue
        value = cleaned.values.get(f.key)
        if value is None:
            continue
        label = cleaned.display_value(f, "th")
        db.add(TicketDetail(
            ticket_id=ticket.id, form_field_id=f.id, field_key=f.key, label_th=f.label_th, label_en=f.label_en,
            value_text=label if f.field_type == "select" else str(value),
            value_json={"value": value, "label_th": label, "label_en": cleaned.display_value(f, "en")}
            if f.field_type == "select" else None,
            sort_order=f.sort_order,
        ))

    db.add(TicketStatusHistory(ticket_id=ticket.id, from_status=None, to_status="NEW", actor_type="CUSTOMER",
                               comment="สร้าง Ticket จากแบบฟอร์มลูกค้า"))
    db.add(TicketAssignment(
        ticket_id=ticket.id, assignment_type="AUTO" if initial.rule else "INITIAL", to_department_id=department.id,
        to_user_id=ticket.assigned_user_id, priority=priority, due_at=ticket.due_at,
        reason=f"Assignment rule: {initial.rule.name}" if initial.rule else "Default department for request type",
    ))
    token = tracking.issue_token(db, ticket, derive_tracking_token(idem_key))

    for vf in received:
        rel = files.persist(vf, ticket.id)
        stored.append(rel)
        db.add(TicketAttachment(
            ticket_id=ticket.id, original_filename=vf.original_filename, stored_path=rel, mime_type=vf.mime_type,
            size_bytes=vf.size, sha256=vf.sha256, kind=vf.kind, width=vf.width, height=vf.height, source="CUSTOMER",
        ))

    notifications.ticket_created(db, ticket, token)
    audit(db, "ticket.created", actor_type="CUSTOMER", entity_type="ticket", entity_id=ticket.id, request=request,
          details={"ticket_number": number, "attachments": len(received)})
    db.flush()
    return SubmissionResult(ticket, token, False)


# --------------------------------------------------------------------------- comments


def _clean_message(body: str | None, field: str = "body") -> str:
    text = (body or "").replace("\r\n", "\n").strip()
    if not text:
        raise ValidationFailed("กรุณากรอกข้อความ", fields={field: "กรุณากรอกข้อความ"})
    if len(text) > MAX_MESSAGE:
        raise ValidationFailed(f"ข้อความยาวเกิน {MAX_MESSAGE} ตัวอักษร", fields={field: "ยาวเกินไป"})
    return text


def add_staff_comment(db: Session, ticket: Ticket, actor: User, body: str, visibility: str) -> TicketComment:
    if visibility not in ("INTERNAL", "PUBLIC"):
        raise ValidationFailed("ประเภทความคิดเห็นไม่ถูกต้อง", fields={"visibility": "ไม่ถูกต้อง"})
    text = _clean_message(body)
    comment = TicketComment(ticket_id=ticket.id, author_user_id=actor.id, author_type="STAFF",
                            visibility=visibility, body=text)
    db.add(comment)
    now = utcnow()
    ticket.last_activity_at = now
    if visibility == "PUBLIC":
        if ticket.first_response_at is None:
            ticket.first_response_at = now
        notifications.public_update(db, ticket, text)
    db.flush()
    return comment


def customer_reply(db: Session, ticket: Ticket, message: str, uploads: list[UploadFile],
                   request: Request | None = None) -> TicketComment:
    status = db.get(TicketStatus, ticket.status)
    if status is None or status.is_terminal or ticket.anonymized_at is not None:
        raise Conflict("Ticket นี้ปิดแล้ว ไม่สามารถส่งข้อมูลเพิ่มเติมได้", code="TICKET_CLOSED")
    text = _clean_message(message, "message")
    form = db.get(FormDefinition, ticket.form_definition_id)
    _, rules = file_rules(form)
    existing = db.scalar(select(func.count()).select_from(TicketAttachment).where(
        TicketAttachment.ticket_id == ticket.id, TicketAttachment.source == "CUSTOMER",
        TicketAttachment.deleted_at.is_(None)))
    received = files.receive_uploads(uploads, rules, existing_count=existing or 0)
    stored: list[str] = []
    try:
        comment = TicketComment(ticket_id=ticket.id, author_type="CUSTOMER", visibility="PUBLIC", body=text)
        db.add(comment)
        db.flush()
        known = set(db.scalars(select(TicketAttachment.sha256).where(TicketAttachment.ticket_id == ticket.id)))
        for vf in received:
            if vf.sha256 in known:
                vf.temp_path.unlink(missing_ok=True)
                continue
            rel = files.persist(vf, ticket.id)
            stored.append(rel)
            db.add(TicketAttachment(
                ticket_id=ticket.id, comment_id=comment.id, original_filename=vf.original_filename, stored_path=rel,
                mime_type=vf.mime_type, size_bytes=vf.size, sha256=vf.sha256, kind=vf.kind, width=vf.width,
                height=vf.height, source="CUSTOMER",
            ))
        ticket.last_activity_at = utcnow()
        if ticket.status == "WAITING_CUSTOMER":
            workflow.system_transition(db, ticket, "IN_PROGRESS", "ลูกค้าส่งข้อมูลเพิ่มเติม", actor_type="CUSTOMER")
        notifications.customer_replied(db, ticket)
        audit(db, "ticket.customer_reply", actor_type="CUSTOMER", entity_type="ticket", entity_id=ticket.id,
              request=request, details={"attachments": len(stored)})
        db.commit()
        return comment
    except BaseException:
        db.rollback()
        files.remove_stored(stored)
        files.discard(received)
        raise


def staff_upload(db: Session, ticket: Ticket, actor: User, uploads: list[UploadFile],
                 request: Request | None = None) -> list[TicketAttachment]:
    rules = FileRules(max_files=10, max_size_mb=get_settings().max_upload_mb,
                      accept=IMAGE_MIME + DOCUMENT_MIME)
    received = files.receive_uploads(uploads, rules)
    if not received:
        raise ValidationFailed("กรุณาเลือกไฟล์", fields={"files": "กรุณาเลือกไฟล์"})
    stored: list[str] = []
    created: list[TicketAttachment] = []
    try:
        known = set(db.scalars(select(TicketAttachment.sha256).where(TicketAttachment.ticket_id == ticket.id)))
        for vf in received:
            if vf.sha256 in known:
                vf.temp_path.unlink(missing_ok=True)
                continue
            rel = files.persist(vf, ticket.id)
            stored.append(rel)
            att = TicketAttachment(
                ticket_id=ticket.id, original_filename=vf.original_filename, stored_path=rel, mime_type=vf.mime_type,
                size_bytes=vf.size, sha256=vf.sha256, kind=vf.kind, width=vf.width, height=vf.height,
                source="STAFF", uploaded_by_user_id=actor.id,
            )
            db.add(att)
            created.append(att)
        ticket.last_activity_at = utcnow()
        audit(db, "ticket.attachment_uploaded", actor=actor, entity_type="ticket", entity_id=ticket.id,
              request=request, details={"count": len(created)})
        db.commit()
        return created
    except BaseException:
        db.rollback()
        files.remove_stored(stored)
        files.discard(received)
        raise
