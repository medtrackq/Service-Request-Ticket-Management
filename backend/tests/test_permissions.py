"""Server-side RBAC: ticket visibility, actions, attachments and admin APIs."""
from __future__ import annotations

from app.db import SessionLocal
from app.services.settings_service import set_setting
from tests.conftest import dept_id, distinct_images, login, make_user, submit


def _setup(client):
    ids = {
        "admin": make_user("admin1", "ADMIN"),
        "svc_mgr": make_user("svcmgr", "MANAGER", ("SERVICE",)),
        "svc_a": make_user("svca", "STAFF", ("SERVICE",)),
        "svc_b": make_user("svcb", "STAFF", ("SERVICE",)),
        "sales_mgr": make_user("salesmgr", "MANAGER", ("SALES",)),
        "sales": make_user("sales1", "STAFF", ("SALES",)),
    }
    svc = submit(client, "service", files=distinct_images(2)).json()
    prd = submit(client, "product").json()
    return ids, svc, prd


def _ticket_id(s, number: str) -> int:
    items = s.get("/api/v1/tickets", params={"q": number}).json()["items"]
    return items[0]["id"]


def test_visibility_by_department(client):
    ids, svc, prd = _setup(client)
    admin = login("admin1")
    assert admin.get("/api/v1/tickets").json()["total"] == 2
    svc_staff = login("svca")
    numbers = [t["ticket_number"] for t in svc_staff.get("/api/v1/tickets").json()["items"]]
    assert numbers == [svc["ticket_number"]]
    sales = login("sales1")
    assert [t["ticket_number"] for t in sales.get("/api/v1/tickets").json()["items"]] == [prd["ticket_number"]]
    svc_id = _ticket_id(admin, svc["ticket_number"])
    # Other department: indistinguishable from "not found"
    assert sales.get(f"/api/v1/tickets/{svc_id}").status_code == 404
    assert login("salesmgr").get(f"/api/v1/tickets/{svc_id}").status_code == 404


def test_staff_queue_setting_off_limits_staff_to_assigned(client):
    ids, svc, _ = _setup(client)
    with SessionLocal() as db:
        set_setting(db, "access.staff_see_department_queue", False, None)
        db.commit()
    staff = login("svca")
    assert staff.get("/api/v1/tickets").json()["total"] == 0
    mgr = login("svcmgr")
    tid = _ticket_id(mgr, svc["ticket_number"])
    assert mgr.post(f"/api/v1/tickets/{tid}/assign", json={"assigned_user_id": ids["svc_a"]}).status_code == 200
    assert staff.get("/api/v1/tickets").json()["total"] == 1


def test_staff_status_change_requires_assignment_and_self_assign(client):
    ids, svc, _ = _setup(client)
    staff = login("svca")
    tid = _ticket_id(staff, svc["ticket_number"])
    detail = staff.get(f"/api/v1/tickets/{tid}").json()
    assert detail["permissions"]["can_change_status"] is False and detail["permissions"]["can_self_assign"] is True
    assert detail["allowed_transitions"] == []
    assert staff.post(f"/api/v1/tickets/{tid}/status", json={"to_status": "IN_PROGRESS"}).status_code == 403
    # staff cannot assign someone else
    r = staff.post(f"/api/v1/tickets/{tid}/assign", json={"assigned_user_id": ids["svc_b"]})
    assert r.status_code == 403
    # but can take the ticket
    r = staff.post(f"/api/v1/tickets/{tid}/assign", json={"assigned_user_id": ids["svc_a"]})
    assert r.status_code == 200 and r.json()["status"]["code"] == "ASSIGNED"
    assert staff.post(f"/api/v1/tickets/{tid}/status", json={"to_status": "IN_PROGRESS"}).status_code == 200
    # another staff member cannot take an already-assigned ticket
    other = login("svcb")
    assert other.post(f"/api/v1/tickets/{tid}/assign", json={"assigned_user_id": ids["svc_b"]}).status_code == 403


def test_manager_assigns_only_within_department(client):
    ids, svc, prd = _setup(client)
    mgr = login("svcmgr")
    tid = _ticket_id(mgr, svc["ticket_number"])
    # assignee must belong to the ticket department
    r = mgr.post(f"/api/v1/tickets/{tid}/assign", json={"assigned_user_id": ids["sales"]})
    assert r.status_code == 422
    r = mgr.post(f"/api/v1/tickets/{tid}/assign", json={"assigned_user_id": ids["svc_b"], "priority": "URGENT"})
    assert r.status_code == 200
    body = r.json()
    assert body["assigned_user"]["id"] == ids["svc_b"] and body["priority"] == "URGENT"


def test_transfer_department_preserves_history(client):
    ids, svc, _ = _setup(client)
    mgr = login("svcmgr")
    tid = _ticket_id(mgr, svc["ticket_number"])
    mgr.post(f"/api/v1/tickets/{tid}/assign", json={"assigned_user_id": ids["svc_a"]})
    r = mgr.post(f"/api/v1/tickets/{tid}/assign", json={"department_id": dept_id("SALES"), "reason": "เป็นงานขาย"})
    assert r.status_code == 200
    assert r.json()["code"] == "TRANSFERRED_OUT"  # manager of SERVICE can no longer see it
    admin = login("admin1")
    d = admin.get(f"/api/v1/tickets/{tid}").json()
    assert d["department"]["code"] == "SALES" and d["assigned_user"] is None
    types = [a["assignment_type"] for a in d["assignments"]]
    assert types == ["INITIAL", "MANUAL", "TRANSFER"]
    assert d["assignments"][-1]["from_department"] and d["assignments"][-1]["reason"] == "เป็นงานขาย"
    assert login("sales1").get(f"/api/v1/tickets/{tid}").status_code == 200


def test_attachment_access_control(client):
    ids, svc, _ = _setup(client)
    admin = login("admin1")
    tid = _ticket_id(admin, svc["ticket_number"])
    att = admin.get(f"/api/v1/tickets/{tid}").json()["attachments"][0]
    r = admin.get(att["url"])
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"
    assert r.headers["x-content-type-options"] == "nosniff"
    assert login("svca").get(att["url"]).status_code == 200
    assert login("sales1").get(att["url"]).status_code == 404
    assert client.get(att["url"]).status_code == 401
    dl = admin.get(att["url"], params={"download": "true"})
    assert dl.headers["content-disposition"].startswith("attachment")


def test_admin_api_requires_admin(client):
    _setup(client)
    for user in ("svcmgr", "svca"):
        s = login(user)
        assert s.get("/api/v1/admin/users").status_code == 403
        assert s.put("/api/v1/admin/settings/assignment.auto_enabled", json={"value": True}).status_code == 403


def test_export_and_reports_restricted_to_managers(client):
    _setup(client)
    staff = login("svca")
    assert staff.get("/api/v1/tickets/export.csv").status_code == 403
    assert staff.get("/api/v1/reports/summary").status_code == 403
    assert staff.get("/api/v1/dashboard").status_code == 200  # scoped dashboard is allowed
    mgr = login("svcmgr")
    assert mgr.get("/api/v1/tickets/export.csv").status_code == 200
    assert mgr.get("/api/v1/reports/workload").status_code == 200


def test_bulk_assign_permissions(client):
    ids, svc, prd = _setup(client)
    admin = login("admin1")
    t1 = _ticket_id(admin, svc["ticket_number"])
    t2 = _ticket_id(admin, prd["ticket_number"])
    assert login("svca").post("/api/v1/tickets/bulk-assign", json={"ticket_ids": [t1]}).status_code == 403
    r = login("svcmgr").post("/api/v1/tickets/bulk-assign",
                             json={"ticket_ids": [t1, t2], "assigned_user_id": ids["svc_a"]})
    assert r.status_code == 200
    body = r.json()
    assert body["updated"] == [svc["ticket_number"]]
    assert len(body["failed"]) == 1 and body["failed"][0]["code"] == "TICKET_NOT_FOUND"


def test_staff_upload_attachments(client):
    ids, svc, _ = _setup(client)
    admin = login("admin1")
    tid = _ticket_id(admin, svc["ticket_number"])
    pdf = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
    r = admin.post(f"/api/v1/tickets/{tid}/attachments",
                   files=[("files", ("report.pdf", pdf, "application/pdf")),
                          ("files", ("x.jpg", b"not really", "image/jpeg"))])
    assert r.status_code == 422  # one invalid file rejects the whole upload
    r = admin.post(f"/api/v1/tickets/{tid}/attachments", files=[("files", ("report.pdf", pdf, "application/pdf"))])
    assert r.status_code == 200
    staff_files = [a for a in r.json()["attachments"] if a["source"] == "STAFF"]
    assert len(staff_files) == 1 and staff_files[0]["kind"] == "DOCUMENT"
    # PDFs are always served as downloads, never inline
    assert admin.get(staff_files[0]["url"]).headers["content-disposition"].startswith("attachment")
    assert login("sales1").post(f"/api/v1/tickets/{tid}/attachments",
                                files=[("files", ("r.pdf", pdf, "application/pdf"))]).status_code == 404
