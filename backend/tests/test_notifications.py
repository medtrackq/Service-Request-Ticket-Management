"""Notification outbox, worker delivery, retries, failure logging, overdue and retention."""
from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import select, update

from app import worker
from app.models import CustomerContact, Ticket, TicketAttachment, TicketNotification, utcnow
from app.services.files import storage_root
from app.services.settings_service import set_setting
from tests.conftest import distinct_images, login, make_user, submit


def _emails(db):
    return db.scalars(select(TicketNotification).where(TicketNotification.channel == "EMAIL")
                      .order_by(TicketNotification.id)).all()


def test_in_app_notifications_for_department_and_assignee(client, db):
    mgr = make_user("mgr", "MANAGER", ("SERVICE",))
    tech = make_user("tech", "STAFF", ("SERVICE",))
    make_user("other", "STAFF", ("SALES",))
    submit(client, "service")
    inbox = login("tech")
    assert inbox.get("/api/v1/notifications/unread-count").json() == {"count": 1}
    assert login("other").get("/api/v1/notifications/unread-count").json() == {"count": 0}
    m = login("mgr")
    tid = m.get("/api/v1/tickets").json()["items"][0]["id"]
    m.post(f"/api/v1/tickets/{tid}/assign", json={"assigned_user_id": tech})
    items = inbox.get("/api/v1/notifications").json()["items"]
    assert [i["event_type"] for i in items] == ["TICKET_ASSIGNED", "TICKET_CREATED"]
    assert inbox.post(f"/api/v1/notifications/{items[0]['id']}/read").status_code == 200
    assert inbox.get("/api/v1/notifications/unread-count").json() == {"count": 1}
    # cannot mark someone else's notification
    assert m.post(f"/api/v1/notifications/{items[1]['id']}/read").status_code == 404
    assert inbox.post("/api/v1/notifications/read-all").status_code == 200
    assert inbox.get("/api/v1/notifications/unread-count").json() == {"count": 0}
    assert mgr


def test_worker_skips_when_smtp_not_configured(client, db):
    submit(client, "service")
    worker.process_notifications()
    db.expire_all()
    rows = _emails(db)
    assert rows and all(n.status == "SKIPPED" and "SMTP" in n.last_error for n in rows)
    # tracking token removed from the stored customer e-mail
    cust = [n for n in rows if n.event_type == "TICKET_CREATED_CUSTOMER"][0]
    assert "#t=" not in cust.body and cust.link_url is None


def test_worker_sends_and_redacts(client, db, monkeypatch):
    sent = []
    monkeypatch.setattr(worker, "send_email", lambda to, subject, body: sent.append((to, subject, body)))
    r = submit(client, "service").json()
    worker.process_notifications()
    db.expire_all()
    assert any(r["tracking_token"] in body for _, _, body in sent)
    cust = [n for n in _emails(db) if n.event_type == "TICKET_CREATED_CUSTOMER"][0]
    assert cust.status == "SENT" and cust.sent_at and r["tracking_token"] not in cust.body


def test_delivery_failure_retries_then_fails_without_affecting_ticket(client, db, monkeypatch):
    def boom(*_):
        raise ConnectionRefusedError("smtp down")

    monkeypatch.setattr(worker, "send_email", boom)
    number = submit(client, "general").json()["ticket_number"]
    worker.process_notifications()
    db.expire_all()
    n = _emails(db)[0]
    assert n.status == "PENDING" and n.attempts == 1 and "smtp down" in n.last_error
    assert n.next_attempt_at > utcnow()
    for _ in range(10):
        db.execute(update(TicketNotification).values(next_attempt_at=utcnow() - timedelta(seconds=1))
                   .where(TicketNotification.status == "PENDING"))
        db.commit()
        worker.process_notifications()
    db.expire_all()
    n = _emails(db)[0]
    assert n.status == "FAILED" and n.attempts == n.max_attempts
    # The ticket itself is untouched by delivery failures.
    assert db.scalar(select(Ticket).where(Ticket.ticket_number == number)).status == "NEW"


def test_admin_can_retry_failed_notification(client, db):
    make_user("root", "ADMIN")
    submit(client, "general")
    worker.process_notifications()
    admin = login("root")
    logs = admin.get("/api/v1/admin/notification-logs").json()
    assert logs["total"] >= 1 and "body" not in logs["items"][0]
    nid = logs["items"][0]["id"]
    assert admin.post(f"/api/v1/admin/notification-logs/{nid}/retry").status_code == 200
    db.expire_all()
    assert db.get(TicketNotification, nid).status == "PENDING"


def test_expired_lease_is_released(client, db):
    submit(client, "general")
    db.execute(update(TicketNotification).where(TicketNotification.channel == "EMAIL")
               .values(status="SENDING", next_attempt_at=utcnow() - timedelta(minutes=1)))
    db.commit()
    assert worker.process_notifications() >= 1


def test_overdue_notified_once(client, db):
    make_user("mgr", "MANAGER", ("SERVICE",))
    submit(client, "service")
    db.execute(update(Ticket).values(due_at=utcnow() - timedelta(hours=1)))
    db.commit()
    assert worker.check_overdue() == 1
    assert worker.check_overdue() == 0
    events = db.scalars(select(TicketNotification.event_type).where(TicketNotification.channel == "IN_APP")).all()
    assert events.count("TICKET_OVERDUE") == 1


@pytest.mark.parametrize("attempts,minutes", [(1, 1), (2, 2), (3, 4), (20, 360)])
def test_backoff(attempts, minutes):
    assert worker.backoff(attempts) == timedelta(minutes=minutes)


def test_retention_anonymises_closed_tickets(client, db):
    make_user("root", "ADMIN")
    t = submit(client, "service", files=distinct_images(2)).json()
    admin = login("root")
    tid = admin.get("/api/v1/tickets").json()["items"][0]["id"]
    admin.post(f"/api/v1/tickets/{tid}/status", json={"to_status": "CLOSED", "comment": "done"})
    set_setting(db, "privacy.retention_days", 30, None)
    db.commit()
    db.execute(update(Ticket).values(updated_at=utcnow() - timedelta(days=31)))
    db.commit()
    paths = [a.stored_path for a in db.scalars(select(TicketAttachment))]
    assert worker.apply_retention()["tickets"] == 1
    db.expire_all()
    ticket = db.get(Ticket, tid)
    assert ticket.anonymized_at and ticket.submitter_ip is None
    contact = db.get(CustomerContact, ticket.contact_id)
    assert contact.phone is None and contact.email is None
    assert all(not (storage_root() / p).exists() for p in paths)
    r = client.post("/api/v1/public/track", json={"ticket_number": t["ticket_number"], "token": t["tracking_token"]})
    assert r.status_code == 404
