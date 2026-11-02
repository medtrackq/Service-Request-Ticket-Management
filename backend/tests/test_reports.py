"""Dashboard and report calculations from controlled data."""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import update

from app.api.csv_utils import cell
from app.models import Ticket, utcnow
from tests.conftest import login, make_user, submit


def _seed(client, db):
    make_user("root", "ADMIN")
    tech = make_user("tech", "STAFF", ("SERVICE",))
    for slug in ("service", "service", "service", "product", "general"):
        submit(client, slug)
    admin = login("root")
    items = sorted(admin.get("/api/v1/tickets", params={"page_size": 50}).json()["items"], key=lambda t: t["id"])
    ids = [t["id"] for t in items]
    # ticket 1: resolved in 10h, first response after 2h (HIGH priority; targets 4h / 72h)
    admin.post(f"/api/v1/tickets/{ids[0]}/assign", json={"assigned_user_id": tech})
    admin.post(f"/api/v1/tickets/{ids[0]}/status", json={"to_status": "RESOLVED"})
    now = utcnow()
    db.execute(update(Ticket).where(Ticket.id == ids[0]).values(
        created_at=now - timedelta(hours=10), first_response_at=now - timedelta(hours=8), resolved_at=now))
    # ticket 2: waiting for customer, overdue
    admin.post(f"/api/v1/tickets/{ids[1]}/status", json={"to_status": "WAITING_CUSTOMER", "public_message": "ขอข้อมูล"})
    db.execute(update(Ticket).where(Ticket.id == ids[1]).values(due_at=now - timedelta(hours=1),
                                                                 created_at=now - timedelta(days=5)))
    # ticket 3: closed in 100h -> resolution target (72h for HIGH) missed
    admin.post(f"/api/v1/tickets/{ids[2]}/status", json={"to_status": "CLOSED", "comment": "ปิด"})
    db.execute(update(Ticket).where(Ticket.id == ids[2]).values(
        created_at=now - timedelta(hours=100), first_response_at=now - timedelta(hours=99), resolved_at=now,
        closed_at=now))
    # ticket 5 is sample data
    db.execute(update(Ticket).where(Ticket.id == ids[4]).values(is_sample=True))
    db.commit()
    return admin, ids, tech


def test_dashboard_kpis(client, db):
    admin, ids, _ = _seed(client, db)
    d = admin.get("/api/v1/dashboard").json()
    k = d["kpis"]
    assert k == {"total": 5, "new": 2, "open": 3, "in_progress": 0, "waiting": 1, "resolved": 1, "closed": 1,
                 "cancelled": 0, "overdue": 1, "sample": 1}
    assert sum(r["count"] for r in d["by_request_type"]) == 5
    assert {r["code"]: r["count"] for r in d["by_request_type"]}["SERVICE"] == 3
    res = {r["code"]: r["avg_hours"] for r in d["resolution_by_request_type"]}
    assert res["SERVICE"] == 55.0  # (10 + 100) / 2
    no_sample = admin.get("/api/v1/dashboard", params={"include_sample": "false"}).json()["kpis"]
    assert no_sample["total"] == 4 and no_sample["sample"] == 0
    filtered = admin.get("/api/v1/dashboard", params={"request_type": "PRODUCT"}).json()["kpis"]
    assert filtered["total"] == 1


def test_performance_report(client, db):
    admin, ids, _ = _seed(client, db)
    p = admin.get("/api/v1/reports/performance").json()
    o = p["overall"]
    assert o["resolved"] == 2
    assert o["resolution_avg_hours"] == 55.0 and o["resolution_median_hours"] == 55.0
    assert o["resolution_target_met_pct"] == 50.0
    assert o["first_response_target_met_pct"] is not None
    assert [x["ticket_number"] for x in p["overdue"]] == [admin.get(f"/api/v1/tickets/{ids[1]}").json()["ticket_number"]]
    assert sum(b["count"] for b in p["open_aging"]) == 3
    assert next(b for b in p["open_aging"] if b["bucket"] == "3-7d")["count"] == 1
    csv = admin.get("/api/v1/reports/performance", params={"format": "csv"})
    assert csv.status_code == 200 and csv.text.startswith("﻿Group")


def test_workload_report(client, db):
    admin, ids, tech = _seed(client, db)
    rows = admin.get("/api/v1/reports/workload").json()["rows"]
    t = next(r for r in rows if r["user_id"] == tech)
    assert t["assigned"] == 1 and t["resolved"] == 1 and t["active"] == 0
    assert rows[-1]["user_id"] is None


def test_summary_report_and_ticket_filters(client, db):
    admin, ids, _ = _seed(client, db)
    s = admin.get("/api/v1/reports/summary").json()
    assert s["total"] == 5 and sum(m["count"] for m in s["by_month"]) == 5
    assert admin.get("/api/v1/tickets", params={"overdue": "true"}).json()["total"] == 1
    assert admin.get("/api/v1/tickets", params={"status_category": "ACTIVE"}).json()["total"] == 3
    assert admin.get("/api/v1/tickets", params={"q": "SN-TEST-001"}).json()["total"] == 3
    assert admin.get("/api/v1/tickets", params={"q": "100%_"}).json()["total"] == 0
    sorted_ = admin.get("/api/v1/tickets", params={"sort": "priority", "direction": "desc"}).json()["items"]
    assert sorted_[0]["priority"] == "HIGH"


def test_csv_formula_injection_guard():
    assert cell("=HYPERLINK(\"x\")") == "'=HYPERLINK(\"x\")"
    assert cell("+1") == "'+1" and cell("@x") == "'@x" and cell("ปกติ") == "ปกติ"
