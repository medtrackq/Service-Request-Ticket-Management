"""Dashboard and reports API (scoped to the tickets the user may see)."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.csv_utils import csv_response
from app.api.deps import current_user, staff_queue_enabled
from app.api.routes.tickets import ticket_filters
from app.db import get_db
from app.models import User
from app.security import permissions as perm
from app.services.audit import audit
from app.services.errors import Forbidden
from app.services.reports import ReportContext
from app.services.ticket_query import TicketFilters

router = APIRouter(tags=["dashboard & reports"])


def _ctx(db: Session, user: User, filters: TicketFilters) -> ReportContext:
    return ReportContext(db, user, filters, staff_queue_enabled(db))


def _require_reports(user: User) -> None:
    if not perm.can_view_reports(user):
        raise Forbidden("ท่านไม่มีสิทธิ์ดูรายงาน")


@router.get("/dashboard")
def dashboard(filters: TicketFilters = Depends(ticket_filters), user: User = Depends(current_user),
              db: Session = Depends(get_db)) -> dict[str, Any]:
    return _ctx(db, user, filters).dashboard()


@router.get("/reports/summary")
def report_summary(request: Request, format: str = Query(default="json", pattern="^(json|csv)$"),
                   filters: TicketFilters = Depends(ticket_filters), user: User = Depends(current_user),
                   db: Session = Depends(get_db)):
    _require_reports(user)
    data = _ctx(db, user, filters).summary()
    if format == "json":
        return data
    audit(db, "report.export_csv", actor=user, request=request, details={"report": "summary"})
    db.commit()
    rows: list[list[Any]] = []
    for r in data["by_request_type"]:
        rows.append(["Request Type", r["name_th"], r["count"]])
    for r in data["by_department"]:
        rows.append(["Department", r["name_th"], r["count"]])
    for r in data["by_status"]:
        rows.append(["Status", r["name_th"], r["count"]])
    for r in data["by_month"]:
        rows.append(["Month", r["month"], r["count"]])
    return csv_response("ticket-summary.csv", ["Dimension", "Value", "Tickets"], rows)


@router.get("/reports/workload")
def report_workload(request: Request, format: str = Query(default="json", pattern="^(json|csv)$"),
                    filters: TicketFilters = Depends(ticket_filters), user: User = Depends(current_user),
                    db: Session = Depends(get_db)):
    _require_reports(user)
    data = _ctx(db, user, filters).workload()
    if format == "json":
        return {"rows": data}
    audit(db, "report.export_csv", actor=user, request=request, details={"report": "workload"})
    db.commit()
    return csv_response(
        "staff-workload.csv",
        ["Staff", "Role", "Departments", "Assigned", "Active", "Waiting", "Resolved", "Closed", "Overdue"],
        ([r["full_name"], r["role"], ", ".join(r["departments"]), r["assigned"], r["active"], r["waiting"],
          r["resolved"], r["closed"], r["overdue"]] for r in data),
    )


@router.get("/reports/performance")
def report_performance(request: Request, format: str = Query(default="json", pattern="^(json|csv)$"),
                       filters: TicketFilters = Depends(ticket_filters), user: User = Depends(current_user),
                       db: Session = Depends(get_db)):
    _require_reports(user)
    data = _ctx(db, user, filters).performance()
    if format == "json":
        return data
    audit(db, "report.export_csv", actor=user, request=request, details={"report": "performance"})
    db.commit()
    header = ["Group", "Tickets", "Responded", "First response avg (h)", "First response median (h)",
              "First response target met %", "Resolved", "Resolution avg (h)", "Resolution median (h)",
              "Resolution target met %"]

    def row(label: str, r: dict[str, Any]) -> list[Any]:
        return [label, r["tickets"], r["responded"], r["first_response_avg_hours"], r["first_response_median_hours"],
                r["first_response_target_met_pct"], r["resolved"], r["resolution_avg_hours"],
                r["resolution_median_hours"], r["resolution_target_met_pct"]]

    rows = [row("ทั้งหมด / Overall", data["overall"])]
    rows += [row(f"ประเภท: {r['request_type']}", r) for r in data["by_request_type"]]
    rows += [row(f"Priority: {r['priority']}", r) for r in data["by_priority"]]
    rows += [[f"Aging {a['bucket']}", a["count"]] for a in data["open_aging"]]
    return csv_response("ticket-performance.csv", header, rows)
