"""Administration: users, departments, forms, settings, rules, integrations, audit."""
from __future__ import annotations

from tests.conftest import PASSWORD, dept_id, login, make_user, submit


def test_user_lifecycle(client):
    make_user("root", "ADMIN")
    admin = login("root")
    r = admin.post("/api/v1/admin/users", json={"username": "new.staff", "full_name": "New Staff", "role": "STAFF",
                                                "department_ids": [dept_id("SERVICE")], "email": "n@example.com"})
    assert r.status_code == 201
    body = r.json()
    temp = body["temporary_password"]
    assert temp and body["must_change_password"] is True
    assert admin.post("/api/v1/admin/users", json={"username": "new.staff", "full_name": "x",
                                                   "role": "STAFF"}).status_code == 409
    s = login("new.staff", temp)
    assert s.get("/api/v1/tickets").json()["detail"]["code"] == "PASSWORD_CHANGE_REQUIRED"
    uid = body["id"]
    r = admin.patch(f"/api/v1/admin/users/{uid}", json={"role": "MANAGER", "department_ids": [dept_id("SALES")]})
    assert r.json()["role"] == "MANAGER" and r.json()["department_ids"] == [dept_id("SALES")]
    reset = admin.post(f"/api/v1/admin/users/{uid}/reset-password").json()["temporary_password"]
    assert reset != temp
    assert s.get("/api/v1/auth/me").status_code == 401  # sessions revoked on reset
    login("new.staff", reset)
    # admin cannot demote / deactivate themselves
    assert admin.patch("/api/v1/admin/users/1", json={"is_active": False}).status_code == 422
    audit = admin.get("/api/v1/admin/audit-logs", params={"action": "admin.user"}).json()
    assert {a["action"] for a in audit["items"]} >= {"admin.user_created", "admin.user_updated",
                                                      "admin.user_password_reset"}


def test_settings_validation(client):
    make_user("root", "ADMIN")
    admin = login("root")
    assert admin.put("/api/v1/admin/settings/assignment.auto_enabled", json={"value": "yes"}).status_code == 422
    assert admin.put("/api/v1/admin/settings/unknown.key", json={"value": 1}).status_code == 422
    targets = {p: {"first_response_hours": 1, "resolution_hours": 8} for p in ("LOW", "NORMAL", "HIGH", "URGENT")}
    assert admin.put("/api/v1/admin/settings/service_targets", json={"value": targets}).status_code == 200
    vals = {s["key"]: s["value"] for s in admin.get("/api/v1/admin/settings").json()}
    assert vals["service_targets"]["LOW"]["resolution_hours"] == 8


def test_auto_assignment_rules(client):
    make_user("root", "ADMIN")
    tech = make_user("lab", "STAFF", ("SERVICE",))
    admin = login("root")
    rt = {r["code"]: r["id"] for r in admin.get("/api/v1/admin/request-types").json()}
    rule = {"name": "Lab equipment", "request_type_id": rt["SERVICE"], "category": "LABORATORY",
            "department_id": dept_id("SERVICE"), "assigned_user_id": tech, "sort_order": 1}
    assert admin.post("/api/v1/admin/assignment-rules", json=rule).status_code == 201
    from tests.conftest import VALUES

    values = {**VALUES["service"], "equipment_type": "LABORATORY"}
    # Rules are ignored while automatic assignment is disabled (default)
    submit(client, "service", values=values)
    assert admin.get("/api/v1/tickets").json()["items"][0]["assigned_user"] is None
    admin.put("/api/v1/admin/settings/assignment.auto_enabled", json={"value": True})
    submit(client, "service", values=values)
    items = admin.get("/api/v1/tickets").json()["items"]
    assert items[0]["assigned_user"]["id"] == tech and items[0]["status"]["code"] == "NEW"
    d = admin.get(f"/api/v1/tickets/{items[0]['id']}").json()
    assert d["assignments"][0]["assignment_type"] == "AUTO"


def test_new_form_version(client):
    make_user("root", "ADMIN")
    admin = login("root")
    rts = {r["code"]: r for r in admin.get("/api/v1/admin/request-types").json()}
    gen = rts["GENERAL"]
    current = admin.get(f"/api/v1/admin/request-types/{gen['id']}/forms").json()[0]
    fields = current["fields"] + [{"key": "contract_no", "section": "request", "field_type": "text",
                                   "label_th": "เลขที่สัญญา", "label_en": "Contract no.", "required": True}]
    bad = admin.post(f"/api/v1/admin/request-types/{gen['id']}/forms",
                     json={"title_th": "t", "title_en": "t", "subject_template": "{nope}", "fields": fields})
    assert bad.status_code == 422 and bad.json()["detail"]["problems"]
    ok = admin.post(f"/api/v1/admin/request-types/{gen['id']}/forms",
                    json={"title_th": "t", "title_en": "t", "subject_template": "{subject}", "fields": fields})
    assert ok.status_code == 201 and ok.json()["version"] == 2
    form = client.get("/api/v1/public/forms/general").json()
    assert form["version"] == 2 and any(f["key"] == "contract_no" for f in form["fields"])
    from tests.conftest import VALUES

    assert submit(client, "general").status_code == 422  # new required field
    assert submit(client, "general", values={**VALUES["general"], "contract_no": "C-1"}).status_code == 201


def test_request_type_and_department_admin(client):
    make_user("root", "ADMIN")
    admin = login("root")
    d = admin.post("/api/v1/admin/departments", json={"code": "BIOMED", "name_th": "วิศวกรรมชีวการแพทย์",
                                                      "name_en": "Biomedical Engineering"}).json()
    rts = {r["code"]: r for r in admin.get("/api/v1/admin/request-types").json()}
    assert rts["SERVICE"]["portal_url"] == "https://service.example.test/request/service"
    admin.patch(f"/api/v1/admin/request-types/{rts['SERVICE']['id']}", json={"default_department_id": d["id"]})
    number = submit(client, "service").json()["ticket_number"]
    t = admin.get("/api/v1/tickets", params={"q": number}).json()["items"][0]
    assert t["department"]["code"] == "BIOMED"
    # cannot deactivate a department that is the default for an active request type
    assert admin.patch(f"/api/v1/admin/departments/{d['id']}", json={"is_active": False}).status_code == 422


def test_integrations_overview_and_mapping(client):
    make_user("root", "ADMIN")
    admin = login("root")
    submit(client, "general")
    info = admin.get("/api/v1/admin/integrations").json()
    assert info["erpnext"]["enabled"] is False
    assert [m["url"] for m in info["line"]["rich_menu"]][0] == "https://service.example.test/request/product"
    cust = admin.get("/api/v1/admin/customers").json()["items"][0]
    r = admin.post("/api/v1/admin/integrations/mappings", json={"local_entity_type": "customer",
                                                                "local_id": str(cust["id"]),
                                                                "external_doctype": "Customer",
                                                                "external_name": "CUST-0001"})
    assert r.status_code == 200 and r.json()["sync_status"] == "MAPPED_MANUALLY"
    assert admin.get("/api/v1/admin/customers").json()["items"][0]["erpnext_customer"] == "CUST-0001"
    assert admin.get("/api/v1/admin/integrations/logs").json()["total"] == 1


def test_erpnext_adapter_refuses_calls():
    import pytest

    from app.integrations.erpnext import IntegrationDisabled, get_erpnext_adapter

    with pytest.raises(IntegrationDisabled):
        get_erpnext_adapter().get_item("ABC")


def test_lookups_do_not_leak_contact_details(client):
    make_user("tech", "STAFF", ("SERVICE",), email="tech@example.com")
    s = login("tech", PASSWORD)
    users = s.get("/api/v1/lookups").json()["users"]
    assert users and "email" not in users[0]
