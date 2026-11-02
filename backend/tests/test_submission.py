"""Customer submissions for all six forms, uploads, validation and idempotency."""
from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.models import Ticket, TicketAttachment, TicketDetail, TicketNotification, TicketStatusHistory
from app.services.files import storage_root
from tests.conftest import VALUES, distinct_images, image_bytes, submit

EXPECTED = {
    "product": ("PRD", "SALES"), "delivery": ("DLV", "LOGISTICS"), "service": ("SRV", "SERVICE"),
    "quotation": ("QUO", "SALES"), "accounting": ("ACC", "ACCOUNTING"), "general": ("GEN", "CS"),
}


def _tmp_files() -> list[Path]:
    return list((storage_root() / "tmp").glob("*"))


@pytest.mark.parametrize("slug", list(EXPECTED))
def test_each_form_creates_ticket_with_default_department(client, db, slug):
    r = submit(client, slug)
    assert r.status_code == 201, r.text
    body = r.json()
    prefix, dept = EXPECTED[slug]
    assert body["ticket_number"].startswith(f"BUC-{prefix}-")
    assert body["tracking_token"] and body["tracking_url"].endswith(f"#t={body['tracking_token']}")
    t = db.scalar(select(Ticket).where(Ticket.ticket_number == body["ticket_number"]))
    assert t.status == "NEW"
    assert t.department.code == dept
    assert t.privacy_consent_version == "1.0"
    hist = db.scalars(select(TicketStatusHistory).where(TicketStatusHistory.ticket_id == t.id)).all()
    assert [(h.from_status, h.to_status) for h in hist] == [(None, "NEW")]


def test_service_request_maps_fields(client, db):
    r = submit(client, "service")
    t = db.scalar(select(Ticket).where(Ticket.ticket_number == r.json()["ticket_number"]))
    assert t.priority == "HIGH"  # from urgency
    assert t.category == "MEDICAL_DEVICE"
    assert t.subject == "แจ้งซ่อม: Infusion Pump - เครื่องเสีย / ใช้งานไม่ได้"
    assert t.description == "เครื่องไม่ทำงาน"
    assert t.customer.name == "โรงพยาบาลทดสอบ" and t.customer.customer_type == "GOV_HOSPITAL"
    assert t.contact.phone == "081-234-5678" and t.contact.department == "ICU"
    assert t.due_at is not None  # from configurable service targets
    details = {d.field_key: d.value_text for d in db.scalars(select(TicketDetail).where(TicketDetail.ticket_id == t.id))}
    assert details["serial_number"] == "SN-TEST-001"
    assert details["problem_type"] == "เครื่องเสีย / ใช้งานไม่ได้"
    # Customer/contact data is normalised, not duplicated into ticket_details.
    assert "organization" not in details and "phone" not in details and "organization_type" not in details


def test_service_request_without_images(client, db):
    r = submit(client, "service", files=[])
    assert r.status_code == 201 and r.json()["attachments"] == 0


def test_service_request_with_ten_images(client, db):
    r = submit(client, "service", files=distinct_images(10))
    assert r.status_code == 201, r.text
    assert r.json()["attachments"] == 10
    t = db.scalar(select(Ticket).where(Ticket.ticket_number == r.json()["ticket_number"]))
    atts = db.scalars(select(TicketAttachment).where(TicketAttachment.ticket_id == t.id)).all()
    assert len(atts) == 10
    for a in atts:
        path = storage_root() / a.stored_path
        assert path.is_file() and a.kind == "IMAGE" and a.width == 64
        assert str(t.id) in a.stored_path and a.original_filename not in a.stored_path


def test_more_than_ten_images_rejected_and_nothing_created(client, db):
    r = submit(client, "service", files=distinct_images(11))
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "TOO_MANY_FILES"
    assert db.scalar(select(func.count()).select_from(Ticket)) == 0
    assert _tmp_files() == []


def test_fake_image_rejected_by_content(client, db):
    r = submit(client, "service", files=[("evil.jpg", b"<script>alert(1)</script>", "image/jpeg")])
    assert r.status_code == 422
    assert "attachments" in r.json()["detail"]["fields"]
    assert db.scalar(select(func.count()).select_from(Ticket)) == 0
    assert _tmp_files() == []


def test_truncated_jpeg_rejected(client):
    data = image_bytes("JPEG")[:40]
    r = submit(client, "service", files=[("broken.jpg", data, "image/jpeg")])
    assert r.status_code == 422


def test_png_disguised_as_jpg_is_accepted_as_png(client, db):
    r = submit(client, "service", files=[("photo.jpg", image_bytes("PNG"), "image/jpeg")])
    assert r.status_code == 201
    att = db.scalar(select(TicketAttachment))
    assert att.mime_type == "image/png" and att.stored_path.endswith(".png")


def test_oversized_image_rejected(client, db):
    big = image_bytes("JPEG") + b"\0" * (10 * 1024 * 1024)
    r = submit(client, "service", files=[("big.jpg", big, "image/jpeg")])
    assert r.status_code == 422
    assert "10 MB" in r.json()["detail"]["message"]
    assert db.scalar(select(func.count()).select_from(Ticket)) == 0


def test_pdf_rejected_for_service_but_accepted_for_quotation(client):
    pdf = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
    assert submit(client, "service", files=[("doc.pdf", pdf, "application/pdf")]).status_code == 422
    r = submit(client, "quotation", files=[("tor.pdf", pdf, "application/pdf")])
    assert r.status_code == 201 and r.json()["attachments"] == 1


def test_duplicate_images_in_one_submission_stored_once(client, db):
    img = image_bytes("JPEG")
    r = submit(client, "service", files=[("a.jpg", img, "image/jpeg"), ("b.jpg", img, "image/jpeg")])
    assert r.status_code == 201
    assert db.scalar(select(func.count()).select_from(TicketAttachment)) == 1


def test_idempotent_replay_returns_same_ticket(client, db):
    files = distinct_images(2)
    r1 = submit(client, "service", files=files, key="same-key-1234567890")
    r2 = submit(client, "service", files=files, key="same-key-1234567890")
    assert r1.status_code == 201 and r2.status_code == 200
    assert r2.json()["replayed"] is True
    assert r1.json()["ticket_number"] == r2.json()["ticket_number"]
    assert r1.json()["tracking_token"] == r2.json()["tracking_token"]
    assert db.scalar(select(func.count()).select_from(Ticket)) == 1
    assert db.scalar(select(func.count()).select_from(TicketAttachment)) == 2
    assert _tmp_files() == []


def test_reusing_key_with_different_data_conflicts(client):
    assert submit(client, "service", key="reused-key-1234567890").status_code == 201
    other = {**VALUES["service"], "equipment_name": "Other"}
    r = submit(client, "service", values=other, key="reused-key-1234567890")
    assert r.status_code == 409 and r.json()["detail"]["code"] == "IDEMPOTENCY_KEY_REUSED"


def test_validation_errors(client, db):
    bad = {**VALUES["service"], "phone": "12", "email": "not-an-email", "urgency": "SUPER", "problem_date": "2999-01-01"}
    del bad["equipment_name"]
    r = submit(client, "service", values=bad)
    assert r.status_code == 422
    fields = r.json()["detail"]["fields"]
    assert set(fields) >= {"phone", "email", "urgency", "problem_date", "equipment_name"}
    assert db.scalar(select(func.count()).select_from(Ticket)) == 0


def test_text_length_and_number_rules(client):
    r = submit(client, "quotation", values={**VALUES["quotation"], "quantity": 0, "product_name": "x" * 300})
    fields = r.json()["detail"]["fields"]
    assert "quantity" in fields and "product_name" in fields


def test_privacy_consent_required(client):
    r = submit(client, "service", consent=False)
    assert r.status_code == 422 and "privacy_consent" in r.json()["detail"]["fields"]


def test_honeypot_rejected(client):
    r = submit(client, "general", extra={"website": "http://spam.example"})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "SPAM_DETECTED"


def test_outdated_form_version_conflicts(client):
    r = submit(client, "service", extra={"form_definition_id": 999999})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "FORM_VERSION_CHANGED"


def test_unknown_form_404(client):
    assert client.get("/api/v1/public/forms/unknown").status_code == 404


def test_same_customer_reused(client, db):
    submit(client, "service")
    submit(client, "product", values={**VALUES["product"], "organization": "  โรงพยาบาลทดสอบ "})
    assert db.scalar(select(func.count(func.distinct(Ticket.customer_id)))) == 1
    assert db.scalar(select(func.count(func.distinct(Ticket.contact_id)))) == 1


def test_creation_enqueues_notifications_without_sending(client, db):
    from tests.conftest import make_user

    make_user("svc1", "STAFF", ("SERVICE",), email="svc1@example.com")
    r = submit(client, "service")
    assert r.status_code == 201
    rows = db.scalars(select(TicketNotification)).all()
    channels = {(n.channel, n.event_type, n.status) for n in rows}
    assert ("IN_APP", "TICKET_CREATED", "SENT") in channels
    assert ("EMAIL", "TICKET_CREATED", "PENDING") in channels
    assert ("EMAIL", "TICKET_CREATED_CUSTOMER", "PENDING") in channels


def test_rate_limit_on_submission(client):
    from app.config import get_settings
    from app.security.rate_limit import limiter

    limiter.enabled = True
    limit = get_settings().rate_limit_submit_per_hour
    codes = [submit(client, "general").status_code for _ in range(limit + 1)]
    assert codes[-1] == 429 and codes.count(201) == limit
