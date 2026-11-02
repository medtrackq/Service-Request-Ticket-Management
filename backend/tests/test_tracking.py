"""Customer tracking: secure credentials and customer-safe data only."""
from __future__ import annotations

import json

from tests.conftest import distinct_images, login, make_user, submit


def _track(client, number, token):
    return client.post("/api/v1/public/track", json={"ticket_number": number, "token": token})


def test_tracking_requires_matching_token(client):
    a = submit(client, "service").json()
    b = submit(client, "general").json()
    assert _track(client, a["ticket_number"], a["tracking_token"]).status_code == 200
    assert _track(client, a["ticket_number"].lower(), a["tracking_token"]).status_code == 200
    assert _track(client, a["ticket_number"], "x" * 43).status_code == 404
    # A valid token for another ticket must not unlock this one.
    assert _track(client, a["ticket_number"], b["tracking_token"]).status_code == 404
    # Ticket number alone is never enough.
    assert client.post("/api/v1/public/track", json={"ticket_number": a["ticket_number"]}).status_code == 422


def test_tracking_hides_internal_information(client):
    make_user("staffer", "ADMIN")
    t = submit(client, "service").json()
    s = login("staffer")
    tid = s.get("/api/v1/tickets").json()["items"][0]["id"]
    s.post(f"/api/v1/tickets/{tid}/assign", json={"assigned_user_id": 1, "reason": "SECRET-ASSIGN-NOTE"})
    s.post(f"/api/v1/tickets/{tid}/comments", json={"body": "SECRET-INTERNAL-NOTE", "visibility": "INTERNAL"})
    s.post(f"/api/v1/tickets/{tid}/status", json={"to_status": "IN_PROGRESS", "comment": "SECRET-REASON",
                                                  "public_message": "กำลังตรวจสอบเครื่อง"})
    r = _track(client, t["ticket_number"], t["tracking_token"])
    raw = r.text
    for secret in ("SECRET-INTERNAL-NOTE", "SECRET-ASSIGN-NOTE", "SECRET-REASON", "Staffer", "staffer",
                   "customer@example.com", "081-234-5678"):
        assert secret not in raw
    body = r.json()
    assert body["status"] == "IN_PROGRESS"
    msgs = [e for e in body["timeline"] if e["type"] == "MESSAGE"]
    assert msgs == [{"type": "MESSAGE", "at": msgs[0]["at"], "author": "STAFF", "body": "กำลังตรวจสอบเครื่อง"}]
    assert [e["status"] for e in body["timeline"] if e["type"] == "STATUS"] == ["NEW", "ASSIGNED", "IN_PROGRESS"]


def test_regenerate_token_revokes_old(client):
    make_user("staffer", "ADMIN")
    t = submit(client, "service").json()
    s = login("staffer")
    tid = s.get("/api/v1/tickets").json()["items"][0]["id"]
    r = s.post(f"/api/v1/tickets/{tid}/tracking-token")
    new = r.json()["tracking_token"]
    assert _track(client, t["ticket_number"], t["tracking_token"]).status_code == 404
    assert _track(client, t["ticket_number"], new).status_code == 200


def test_customer_reply_with_images_resumes_work(client):
    make_user("staffer", "ADMIN")
    t = submit(client, "service", files=distinct_images(8)).json()
    s = login("staffer")
    tid = s.get("/api/v1/tickets").json()["items"][0]["id"]
    s.post(f"/api/v1/tickets/{tid}/status", json={"to_status": "WAITING_CUSTOMER", "public_message": "ขอรูปเพิ่ม"})

    def reply(files, message="ส่งรูปเพิ่มแล้ว"):
        payload = json.dumps({"ticket_number": t["ticket_number"], "token": t["tracking_token"], "message": message})
        return client.post("/api/v1/public/track/reply", data={"payload": payload},
                           files=[("files", f) for f in files] or None)

    view = _track(client, t["ticket_number"], t["tracking_token"]).json()
    assert view["request_type_slug"] == "service"
    assert view["reply_file_rules"] == {"max_files": 2, "max_size_mb": 10, "accept": ["image/jpeg", "image/png"]}
    # 8 existing + 3 new would exceed the 10-image limit per Service Request ticket
    extra = distinct_images(11)[8:]
    assert reply(extra).status_code == 422
    r = reply(extra[:2])
    assert r.status_code == 200
    assert r.json()["status"] == "IN_PROGRESS"
    assert r.json()["reply_file_rules"]["max_files"] == 0
    d = s.get(f"/api/v1/tickets/{tid}").json()
    assert len(d["attachments"]) == 10
    assert d["comments"][-1]["author_type"] == "CUSTOMER"
    assert reply([], message="").status_code == 422


def test_reply_rejected_on_closed_ticket(client):
    make_user("staffer", "ADMIN")
    t = submit(client, "general").json()
    s = login("staffer")
    tid = s.get("/api/v1/tickets").json()["items"][0]["id"]
    s.post(f"/api/v1/tickets/{tid}/status", json={"to_status": "CLOSED", "comment": "ปิด"})
    payload = json.dumps({"ticket_number": t["ticket_number"], "token": t["tracking_token"], "message": "hi"})
    r = client.post("/api/v1/public/track/reply", data={"payload": payload})
    assert r.status_code == 409
    assert _track(client, t["ticket_number"], t["tracking_token"]).json()["can_reply"] is False
