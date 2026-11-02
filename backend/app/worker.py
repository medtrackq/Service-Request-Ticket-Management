"""Background worker: notification delivery, overdue detection and retention jobs.

Run with:  python -m app.worker

The queue is the `ticket_notifications` table (transactional outbox). Rows are
claimed with SELECT .. FOR UPDATE SKIP LOCKED, so several workers can run in
parallel safely. A claimed row is leased for LEASE minutes; if a worker dies
mid-delivery the lease expires and the row is retried.
"""
from __future__ import annotations

import logging
import signal
import time
from datetime import timedelta

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import SessionLocal
from app.integrations.email_smtp import EmailNotConfigured, send_email
from app.integrations.line.messaging import LineDeliveryError, push_text
from app.models import (
    AuditLog,
    CustomerContact,
    Ticket,
    TicketAttachment,
    TicketDetail,
    TicketNotification,
    TicketStatus,
    TicketTrackingToken,
    utcnow,
)
from app.services import files, notifications
from app.services.settings_service import get_setting

log = logging.getLogger("buc.worker")
LEASE = timedelta(minutes=10)
OVERDUE_EVERY = 300  # seconds
RETENTION_EVERY = 6 * 3600

_running = True


def backoff(attempts: int) -> timedelta:
    """1, 2, 4, 8, 16 ... minutes, capped at 6 hours."""
    return timedelta(minutes=min(2 ** max(attempts - 1, 0), 360))


def _redact(n: TicketNotification) -> None:
    """Customer creation e-mails contain the tracking token; do not keep it after delivery."""
    if n.event_type == notifications.CUSTOMER_CREATED_EVENT and n.link_url:
        n.body = n.body.replace(n.link_url, "[ลิงก์ติดตามสถานะถูกลบออกหลังส่งแล้ว]")
        n.link_url = None


def claim_batch(db: Session, limit: int) -> list[int]:
    now = utcnow()
    # Release expired leases (worker crashed while sending).
    db.execute(update(TicketNotification)
               .where(TicketNotification.status == "SENDING", TicketNotification.next_attempt_at < now)
               .values(status="PENDING"))
    rows = list(db.scalars(
        select(TicketNotification)
        .where(TicketNotification.status == "PENDING", TicketNotification.next_attempt_at <= now,
               TicketNotification.channel.in_(("EMAIL", "LINE")))
        .order_by(TicketNotification.next_attempt_at, TicketNotification.id)
        .limit(limit).with_for_update(skip_locked=True)
    ))
    for n in rows:
        n.status = "SENDING"
        n.next_attempt_at = now + LEASE
    db.commit()
    return [n.id for n in rows]


def deliver(db: Session, notification_id: int) -> str:
    n = db.get(TicketNotification, notification_id)
    if n is None or n.status != "SENDING":
        return "gone"
    n.attempts += 1
    try:
        if n.channel == "EMAIL":
            send_email(n.recipient_address or "", n.subject, n.body)
        elif n.channel == "LINE":
            push_text(n.recipient_address or "", n.body)
        n.status = "SENT"
        n.sent_at = utcnow()
        n.last_error = None
        _redact(n)
    except EmailNotConfigured as exc:
        n.status = "SKIPPED"
        n.last_error = str(exc)
        _redact(n)
    except LineDeliveryError as exc:
        _fail(n, str(exc), retryable=exc.retryable)
    except Exception as exc:  # SMTP errors, network errors, ...
        _fail(n, f"{type(exc).__name__}: {exc}", retryable=True)
    db.commit()
    return n.status


def _fail(n: TicketNotification, error: str, retryable: bool) -> None:
    n.last_error = error[:2000]
    if retryable and n.attempts < n.max_attempts:
        n.status = "PENDING"
        n.next_attempt_at = utcnow() + backoff(n.attempts)
        log.warning("notification %s failed (attempt %s), retrying: %s", n.id, n.attempts, error)
    else:
        n.status = "FAILED"
        _redact(n)
        log.error("notification %s failed permanently: %s", n.id, error)


def process_notifications(limit: int | None = None) -> int:
    limit = limit or get_settings().worker_batch_size
    with SessionLocal() as db:
        ids = claim_batch(db, limit)
    for nid in ids:
        with SessionLocal() as db:
            deliver(db, nid)
    return len(ids)


def check_overdue() -> int:
    """Notify once per due date for open tickets past their due date."""
    with SessionLocal() as db:
        if not get_setting(db, "notifications.overdue_enabled"):
            return 0
        now = utcnow()
        tickets = list(db.scalars(
            select(Ticket).join(TicketStatus, TicketStatus.code == Ticket.status)
            .where(TicketStatus.category.in_(("NEW", "OPEN", "WAITING")), Ticket.due_at.is_not(None),
                   Ticket.due_at < now, Ticket.overdue_notified_at.is_(None), Ticket.is_sample.is_(False))
            .limit(200).with_for_update(of=Ticket, skip_locked=True)
        ).unique())
        for t in tickets:
            notifications.ticket_overdue(db, t)
            t.overdue_notified_at = now
        db.commit()
        return len(tickets)


def apply_retention() -> dict[str, int]:
    """PDPA retention: anonymise personal data of tickets closed/cancelled longer than the configured period."""
    result = {"tickets": 0, "audit_logs": 0}
    with SessionLocal() as db:
        days = int(get_setting(db, "privacy.retention_days") or 0)
        if days > 0:
            cutoff = utcnow() - timedelta(days=days)
            tickets = list(db.scalars(
                select(Ticket).where(Ticket.anonymized_at.is_(None), Ticket.status.in_(("CLOSED", "CANCELLED")),
                                     Ticket.updated_at < cutoff).limit(500)).unique())
            for t in tickets:
                anonymize_ticket(db, t)
                result["tickets"] += 1
            db.commit()
        audit_days = int(get_setting(db, "audit.retention_days") or 0)
        if audit_days > 0:
            res = db.execute(delete(AuditLog).where(AuditLog.created_at < utcnow() - timedelta(days=audit_days)))
            result["audit_logs"] = res.rowcount or 0
            db.commit()
    return result


def anonymize_ticket(db: Session, t: Ticket) -> None:
    now = utcnow()
    for a in db.scalars(select(TicketAttachment).where(TicketAttachment.ticket_id == t.id,
                                                       TicketAttachment.deleted_at.is_(None))):
        files.remove_stored([a.stored_path])
        a.deleted_at = now
    files.remove_ticket_dir(t.id)
    db.execute(update(TicketTrackingToken).where(TicketTrackingToken.ticket_id == t.id,
                                                 TicketTrackingToken.revoked_at.is_(None)).values(revoked_at=now))
    db.execute(update(TicketDetail).where(TicketDetail.ticket_id == t.id,
                                          TicketDetail.field_key == "additional_details").values(value_text=None))
    t.submitter_ip = None
    t.line_user_id = None
    t.anonymized_at = now
    # Contacts are shared between tickets; anonymise only when none of their tickets is still retained.
    others = db.scalar(select(Ticket.id).where(Ticket.contact_id == t.contact_id, Ticket.id != t.id,
                                               Ticket.anonymized_at.is_(None)).limit(1))
    if others is None:
        c = db.get(CustomerContact, t.contact_id)
        if c is not None and c.anonymized_at is None:
            c.name = "[ข้อมูลถูกลบตามนโยบาย]"
            c.phone = None
            c.email = None
            c.department = None
            c.line_user_id = None
            c.match_key = f"anonymized:{c.id}"
            c.anonymized_at = now


def _stop(*_: object) -> None:
    global _running
    _running = False


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    s = get_settings()
    log.info("worker started (poll=%ss)", s.worker_poll_seconds)
    last_overdue = 0.0
    last_retention = 0.0
    while _running:
        try:
            sent = process_notifications()
            now = time.monotonic()
            if now - last_overdue >= OVERDUE_EVERY:
                n = check_overdue()
                if n:
                    log.info("overdue notifications queued for %s tickets", n)
                last_overdue = now
            if now - last_retention >= RETENTION_EVERY:
                r = apply_retention()
                if any(r.values()):
                    log.info("retention applied: %s", r)
                last_retention = now
            if sent:
                continue
        except Exception:  # keep the worker alive; errors are logged and retried next loop
            log.exception("worker loop error")
        for _ in range(s.worker_poll_seconds * 10):
            if not _running:
                break
            time.sleep(0.1)
    log.info("worker stopped")


if __name__ == "__main__":
    main()
