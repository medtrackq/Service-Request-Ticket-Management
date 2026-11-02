"""Workflow transitions, history and timestamps."""
from __future__ import annotations

from sqlalchemy import select

from app.models import TicketStatusHistory
from tests.conftest import login, make_user, submit


def _ticket(client):
    make_user("boss", "ADMIN")
    make_user("mgr", "MANAGER", ("SERVICE",))
    staff_id = make_user("tech", "STAFF", ("SERVICE",))
    number = submit(client, "service").json()["ticket_number"]
    admin = login("boss")
    tid = admin.get("/api/v1/tickets", params={"q": number}).json()["items"][0]["id"]
    return admin, tid, staff_id


def test_full_lifecycle_records_history(client, db):
    admin, tid, staff_id = _ticket(client)
    staff = login("tech")
    login("mgr").post(f"/api/v1/tickets/{tid}/assign", json={"assigned_user_id": staff_id})
    assert staff.post(f"/api/v1/tickets/{tid}/status", json={"to_status": "IN_PROGRESS",
                                                            "comment": "เริ่มงาน"}).status_code == 200
    r = staff.post(f"/api/v1/tickets/{tid}/status", json={"to_status": "RESOLVED", "public_message": "ซ่อมเสร็จแล้ว"})
    assert r.status_code == 200
    d = r.json()
    assert d["resolved_at"] and d["first_response_at"]
    r = staff.post(f"/api/v1/tickets/{tid}/status", json={"to_status": "CLOSED"})
    assert r.status_code == 200 and r.json()["closed_at"]
    hist = db.scalars(select(TicketStatusHistory).where(TicketStatusHistory.ticket_id == tid)
                      .order_by(TicketStatusHistory.id)).all()
    assert [(h.from_status, h.to_status) for h in hist] == [
        (None, "NEW"), ("NEW", "ASSIGNED"), ("ASSIGNED", "IN_PROGRESS"), ("IN_PROGRESS", "RESOLVED"),
        ("RESOLVED", "CLOSED")]
    started = hist[2]
    assert started.changed_by_user_id == staff_id and started.comment == "เริ่มงาน" and started.created_at
    assert hist[1].actor_type == "SYSTEM"


def test_tickets_can_skip_statuses(client):
    admin, tid, _ = _ticket(client)
    assert admin.post(f"/api/v1/tickets/{tid}/status", json={"to_status": "RESOLVED"}).status_code == 200


def test_disallowed_transition(client):
    admin, tid, _ = _ticket(client)
    assert admin.post(f"/api/v1/tickets/{tid}/status", json={"to_status": "NEW"}).status_code == 422  # same status
    assert admin.post(f"/api/v1/tickets/{tid}/status", json={"to_status": "REVIEW"}).status_code == 200
    r = admin.post(f"/api/v1/tickets/{tid}/status", json={"to_status": "NEW"})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "TRANSITION_NOT_ALLOWED"
    assert admin.post(f"/api/v1/tickets/{tid}/status", json={"to_status": "BOGUS"}).status_code == 422


def test_role_restricted_transition_and_required_comment(client):
    admin, tid, staff_id = _ticket(client)
    login("mgr").post(f"/api/v1/tickets/{tid}/assign", json={"assigned_user_id": staff_id})
    staff = login("tech")
    r = staff.post(f"/api/v1/tickets/{tid}/status", json={"to_status": "CANCELLED", "comment": "ซ้ำ"})
    assert r.status_code == 403 and r.json()["detail"]["code"] == "TRANSITION_ROLE_FORBIDDEN"
    r = admin.post(f"/api/v1/tickets/{tid}/status", json={"to_status": "CANCELLED"})
    assert r.status_code == 422 and "comment" in r.json()["detail"]["fields"]
    r = admin.post(f"/api/v1/tickets/{tid}/status", json={"to_status": "CANCELLED", "comment": "ลูกค้าแจ้งซ้ำ"})
    assert r.status_code == 200 and r.json()["cancelled_at"]
    assert r.json()["allowed_transitions"] == [{"to_status": "REVIEW", "name_th": "กำลังตรวจสอบ",
                                                 "name_en": "Under Review", "requires_comment": True}]


def test_request_customer_information_requires_public_message(client):
    admin, tid, _ = _ticket(client)
    r = admin.post(f"/api/v1/tickets/{tid}/status", json={"to_status": "WAITING_CUSTOMER"})
    assert r.status_code == 422 and "public_message" in r.json()["detail"]["fields"]
    r = admin.post(f"/api/v1/tickets/{tid}/status",
                   json={"to_status": "WAITING_CUSTOMER", "public_message": "ขอ Serial Number"})
    assert r.status_code == 200
    assert any(c["visibility"] == "PUBLIC" and c["body"] == "ขอ Serial Number" for c in r.json()["comments"])


def test_reopen_clears_resolution(client):
    admin, tid, _ = _ticket(client)
    admin.post(f"/api/v1/tickets/{tid}/status", json={"to_status": "RESOLVED"})
    r = admin.post(f"/api/v1/tickets/{tid}/status", json={"to_status": "IN_PROGRESS", "comment": "ยังไม่หาย"})
    assert r.status_code == 200 and r.json()["resolved_at"] is None


def test_workflow_is_configurable(client):
    admin, tid, _ = _ticket(client)
    wf = admin.get("/api/v1/admin/workflow").json()
    keep = [t for t in wf["transitions"] if not (t["from_status"] == "NEW" and t["to_status"] == "RESOLVED")]
    payload = {"transitions": [{k: t[k] for k in ("from_status", "to_status", "allowed_roles", "requires_comment",
                                                  "is_active")} for t in keep]}
    assert admin.put("/api/v1/admin/workflow/transitions", json=payload).status_code == 200
    assert admin.post(f"/api/v1/tickets/{tid}/status", json={"to_status": "RESOLVED"}).status_code == 422


def test_comments_internal_and_public(client):
    admin, tid, _ = _ticket(client)
    r = admin.post(f"/api/v1/tickets/{tid}/comments", json={"body": "โน้ตภายใน", "visibility": "INTERNAL"})
    assert r.status_code == 200 and r.json()["first_response_at"] is None
    r = admin.post(f"/api/v1/tickets/{tid}/comments", json={"body": "แจ้งลูกค้า", "visibility": "PUBLIC"})
    assert r.json()["first_response_at"] is not None
    assert admin.post(f"/api/v1/tickets/{tid}/comments", json={"body": "x", "visibility": "SECRET"}).status_code == 422
