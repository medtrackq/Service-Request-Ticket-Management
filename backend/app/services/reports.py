"""Dashboard statistics and operational reports, computed from database records.

Calculation definitions (also documented in docs/REPORTS.md):

* Open ticket       status category in NEW, OPEN, WAITING (i.e. not RESOLVED/CLOSED/CANCELLED).
* Waiting ticket    status category WAITING (WAITING_CUSTOMER, WAITING_INTERNAL).
* Overdue ticket    open ticket whose due_at is earlier than now.
* First response    first_response_at - created_at, where first_response_at is the first
                    customer-visible staff action: a manual status change or a customer-visible
                    update. Automatic transitions and internal notes do not count.
* Resolution time   resolved_at - created_at for tickets currently RESOLVED or CLOSED
                    (closed_at is used when a ticket was closed without passing RESOLVED;
                    a reopened ticket's resolved_at is cleared and set again when re-resolved).
* Open ticket aging now - created_at for open tickets, bucketed.
* Target met        duration <= the configurable internal target for the ticket's priority
                    (system setting `service_targets`); tickets without a target are excluded.
* Monthly grouping  calendar month of created_at in Asia/Bangkok
                    (resolution-time-by-month uses the month of resolution).
* The date filter applies to ticket creation date (Asia/Bangkok).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import and_, case, extract, func, literal, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Department, RequestType, Ticket, TicketStatus, User, user_departments, utcnow
from app.models.workflow import PRIORITIES
from app.services.settings_service import get_setting
from app.services.ticket_query import OPEN_CATEGORIES, TicketFilters, conditions

AGING_BUCKETS = [("0-1d", 0, 1), ("1-3d", 1, 3), ("3-7d", 3, 7), ("7-14d", 7, 14), ("14-30d", 14, 30),
                 ("30d+", 30, None)]


def _tz() -> str:
    return get_settings().timezone


def _month_expr(col):
    return func.to_char(func.timezone(_tz(), col), "YYYY-MM")


def _hours(expr):
    return extract("epoch", expr) / 3600.0


def _resolution_ts():
    return func.coalesce(Ticket.resolved_at, Ticket.closed_at)


def _target_case(kind: str, targets: dict[str, Any]):
    whens = [(Ticket.priority == p, float(targets[p][kind])) for p in PRIORITIES
             if targets.get(p, {}).get(kind)]
    return case(*whens, else_=None) if whens else literal(None)


def _round(v: float | None, n: int = 1) -> float | None:
    return round(float(v), n) if v is not None else None


def _months_between(start: date, end: date) -> list[str]:
    out = []
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m > 12:
            y, m = y + 1, 1
    return out


class ReportContext:
    def __init__(self, db: Session, user: User, filters: TicketFilters, staff_queue: bool) -> None:
        self.db = db
        self.user = user
        self.filters = filters
        self.conds = conditions(user, filters, staff_queue)
        self.now = utcnow()

    def _base(self, *cols):
        return (select(*cols).select_from(Ticket).join(TicketStatus, TicketStatus.code == Ticket.status)
                .where(*self.conds))

    # ----------------------------------------------------------------- dashboard

    def kpis(self) -> dict[str, int]:
        is_open = TicketStatus.category.in_(OPEN_CATEGORIES)
        row = self.db.execute(self._base(
            func.count().label("total"),
            func.count().filter(Ticket.status == "NEW").label("new"),
            func.count().filter(is_open).label("open"),
            func.count().filter(Ticket.status == "IN_PROGRESS").label("in_progress"),
            func.count().filter(TicketStatus.category == "WAITING").label("waiting"),
            func.count().filter(Ticket.status == "RESOLVED").label("resolved"),
            func.count().filter(Ticket.status == "CLOSED").label("closed"),
            func.count().filter(Ticket.status == "CANCELLED").label("cancelled"),
            func.count().filter(and_(is_open, Ticket.due_at.is_not(None), Ticket.due_at < self.now)).label("overdue"),
            func.count().filter(Ticket.is_sample.is_(True)).label("sample"),
        )).one()
        return dict(row._mapping)

    def volume_by_month(self) -> list[dict[str, Any]]:
        f = self.filters
        tz = ZoneInfo(_tz())
        end = f.date_to or datetime.now(tz).date()
        start = f.date_from or (end.replace(day=1) - timedelta(days=330)).replace(day=1)
        month = _month_expr(Ticket.created_at)
        stmt = self._base(month.label("month"), func.count().label("count"))
        if not f.date_from:
            stmt = stmt.where(Ticket.created_at >= datetime.combine(start, datetime.min.time(), tz))
        rows = {r.month: r.count for r in self.db.execute(stmt.group_by(month))}
        return [{"month": m, "count": rows.get(m, 0)} for m in _months_between(start, end)]

    def by_request_type(self) -> list[dict[str, Any]]:
        stmt = (self._base(RequestType.code, RequestType.name_th, RequestType.name_en, func.count().label("count"))
                .join(RequestType, RequestType.id == Ticket.request_type_id)
                .group_by(RequestType.code, RequestType.name_th, RequestType.name_en, RequestType.sort_order)
                .order_by(RequestType.sort_order))
        return [dict(r._mapping) for r in self.db.execute(stmt)]

    def by_department(self) -> list[dict[str, Any]]:
        stmt = (self._base(Department.id, Department.name_th, Department.name_en, func.count().label("count"))
                .join(Department, Department.id == Ticket.department_id)
                .group_by(Department.id, Department.name_th, Department.name_en, Department.sort_order)
                .order_by(Department.sort_order))
        return [dict(r._mapping) for r in self.db.execute(stmt)]

    def by_status(self) -> list[dict[str, Any]]:
        stmt = (self._base(TicketStatus.code, TicketStatus.name_th, TicketStatus.name_en, TicketStatus.color,
                           func.count().label("count"))
                .group_by(TicketStatus.code, TicketStatus.name_th, TicketStatus.name_en, TicketStatus.color,
                          TicketStatus.sort_order)
                .order_by(TicketStatus.sort_order))
        return [dict(r._mapping) for r in self.db.execute(stmt)]

    def by_priority(self) -> list[dict[str, Any]]:
        rows = {r.priority: r.count for r in self.db.execute(
            self._base(Ticket.priority, func.count().label("count")).group_by(Ticket.priority))}
        return [{"priority": p, "count": rows.get(p, 0)} for p in PRIORITIES]

    def resolution_by_request_type(self) -> list[dict[str, Any]]:
        hours = _hours(_resolution_ts() - Ticket.created_at)
        stmt = (self._base(RequestType.code, RequestType.name_th, RequestType.name_en,
                           func.avg(hours).label("avg_hours"), func.count().label("count"))
                .join(RequestType, RequestType.id == Ticket.request_type_id)
                .where(TicketStatus.category.in_(("RESOLVED", "CLOSED")), _resolution_ts().is_not(None))
                .group_by(RequestType.code, RequestType.name_th, RequestType.name_en, RequestType.sort_order)
                .order_by(RequestType.sort_order))
        return [{**dict(r._mapping), "avg_hours": _round(r.avg_hours)} for r in self.db.execute(stmt)]

    def resolution_by_month(self) -> list[dict[str, Any]]:
        month = _month_expr(_resolution_ts())
        hours = _hours(_resolution_ts() - Ticket.created_at)
        stmt = (self._base(month.label("month"), func.avg(hours).label("avg_hours"), func.count().label("count"))
                .where(TicketStatus.category.in_(("RESOLVED", "CLOSED")), _resolution_ts().is_not(None))
                .group_by(month).order_by(month))
        return [{"month": r.month, "avg_hours": _round(r.avg_hours), "count": r.count} for r in self.db.execute(stmt)]

    def dashboard(self) -> dict[str, Any]:
        return {
            "kpis": self.kpis(),
            "volume_by_month": self.volume_by_month(),
            "by_request_type": self.by_request_type(),
            "by_department": self.by_department(),
            "by_status": self.by_status(),
            "by_priority": self.by_priority(),
            "resolution_by_request_type": self.resolution_by_request_type(),
            "resolution_by_month": self.resolution_by_month(),
            "generated_at": self.now,
        }

    # ----------------------------------------------------------------- reports

    def summary(self) -> dict[str, Any]:
        month = _month_expr(Ticket.created_at)
        by_month = [{"month": r.month, "count": r.count} for r in self.db.execute(
            self._base(month.label("month"), func.count().label("count")).group_by(month).order_by(month))]
        return {
            "total": self.kpis()["total"],
            "by_request_type": self.by_request_type(),
            "by_department": self.by_department(),
            "by_status": self.by_status(),
            "by_month": by_month,
        }

    def workload(self) -> list[dict[str, Any]]:
        """Per staff member, based on the CURRENT assignee of tickets matching the filters."""
        is_open = TicketStatus.category.in_(OPEN_CATEGORIES)
        stmt = (
            self._base(
                Ticket.assigned_user_id.label("user_id"),
                func.count().label("assigned"),
                func.count().filter(is_open).label("active"),
                func.count().filter(TicketStatus.category == "WAITING").label("waiting"),
                func.count().filter(Ticket.status == "RESOLVED").label("resolved"),
                func.count().filter(Ticket.status == "CLOSED").label("closed"),
                func.count().filter(and_(is_open, Ticket.due_at < self.now)).label("overdue"),
            )
            .where(Ticket.assigned_user_id.is_not(None))
            .group_by(Ticket.assigned_user_id)
        )
        stats = {r.user_id: dict(r._mapping) for r in self.db.execute(stmt)}
        users_stmt = select(User).where(User.is_active.is_(True)).order_by(User.full_name)
        if self.user.role != "ADMIN":
            users_stmt = users_stmt.where(User.id.in_(
                select(user_departments.c.user_id).where(user_departments.c.department_id.in_(
                    self.user.department_ids or [-1]))))
        out = []
        for u in self.db.scalars(users_stmt).unique():
            s = stats.pop(u.id, None) or {}
            out.append({"user_id": u.id, "full_name": u.full_name, "role": u.role,
                        "departments": [d.name_th for d in u.departments],
                        **{k: s.get(k, 0) for k in ("assigned", "active", "waiting", "resolved", "closed",
                                                     "overdue")}})
        unassigned = self.db.scalar(self._base(func.count()).where(Ticket.assigned_user_id.is_(None),
                                                                   TicketStatus.category.in_(OPEN_CATEGORIES)))
        out.sort(key=lambda r: (-r["active"], r["full_name"]))
        return [*out, {"user_id": None, "full_name": "(ยังไม่มอบหมาย / Unassigned)", "role": "", "departments": [],
                       "assigned": unassigned, "active": unassigned, "waiting": 0, "resolved": 0, "closed": 0,
                       "overdue": 0}]

    def performance(self) -> dict[str, Any]:
        targets = get_setting(self.db, "service_targets") or {}
        fr_hours = _hours(Ticket.first_response_at - Ticket.created_at)
        res_hours = _hours(_resolution_ts() - Ticket.created_at)
        fr_target = _target_case("first_response_hours", targets)
        res_target = _target_case("resolution_hours", targets)
        resolved_filter = and_(TicketStatus.category.in_(("RESOLVED", "CLOSED")), _resolution_ts().is_not(None))

        def block(group_col=None):
            cols = [
                func.count().filter(Ticket.first_response_at.is_not(None)).label("responded"),
                func.avg(fr_hours).filter(Ticket.first_response_at.is_not(None)).label("fr_avg"),
                func.percentile_cont(0.5).within_group(fr_hours).filter(
                    Ticket.first_response_at.is_not(None)).label("fr_median"),
                func.count().filter(and_(Ticket.first_response_at.is_not(None), fr_target.is_not(None))
                                    ).label("fr_with_target"),
                func.count().filter(and_(Ticket.first_response_at.is_not(None), fr_hours <= fr_target)
                                    ).label("fr_met"),
                func.count().filter(resolved_filter).label("resolved"),
                func.avg(res_hours).filter(resolved_filter).label("res_avg"),
                func.percentile_cont(0.5).within_group(res_hours).filter(resolved_filter).label("res_median"),
                func.count().filter(and_(resolved_filter, res_target.is_not(None))).label("res_with_target"),
                func.count().filter(and_(resolved_filter, res_hours <= res_target)).label("res_met"),
                func.count().label("tickets"),
            ]
            if group_col is not None:
                cols.insert(0, group_col)
            return cols

        def fmt(r) -> dict[str, Any]:
            m = dict(r._mapping)
            return {
                **{k: m[k] for k in m if k not in ("fr_avg", "fr_median", "res_avg", "res_median")},
                "first_response_avg_hours": _round(m["fr_avg"]),
                "first_response_median_hours": _round(m["fr_median"]),
                "first_response_target_met_pct": _round(100 * m["fr_met"] / m["fr_with_target"])
                if m["fr_with_target"] else None,
                "resolution_avg_hours": _round(m["res_avg"]),
                "resolution_median_hours": _round(m["res_median"]),
                "resolution_target_met_pct": _round(100 * m["res_met"] / m["res_with_target"])
                if m["res_with_target"] else None,
            }

        overall = fmt(self.db.execute(self._base(*block())).one())
        by_type = [fmt(r) for r in self.db.execute(
            self._base(*block(RequestType.name_th.label("request_type")))
            .join(RequestType, RequestType.id == Ticket.request_type_id)
            .group_by(RequestType.name_th, RequestType.sort_order).order_by(RequestType.sort_order))]
        by_priority_rows = {r.priority: fmt(r) for r in self.db.execute(
            self._base(*block(Ticket.priority.label("priority"))).group_by(Ticket.priority))}
        by_priority = [by_priority_rows[p] for p in reversed(PRIORITIES) if p in by_priority_rows]

        age_days = extract("epoch", literal(self.now) - Ticket.created_at) / 86400.0
        is_open = TicketStatus.category.in_(OPEN_CATEGORIES)
        aging_cols = []
        for label, lo, hi in AGING_BUCKETS:
            cond = and_(is_open, age_days >= lo) if hi is None else and_(is_open, age_days >= lo, age_days < hi)
            aging_cols.append(func.count().filter(cond).label(label.replace("-", "_").replace("+", "_plus")))
        aging_row = self.db.execute(self._base(*aging_cols)).one()
        aging = [{"bucket": label, "count": aging_row[i]} for i, (label, _, _) in enumerate(AGING_BUCKETS)]

        overdue_rows = self.db.scalars(
            select(Ticket).join(TicketStatus, TicketStatus.code == Ticket.status)
            .where(*self.conds, is_open, Ticket.due_at.is_not(None), Ticket.due_at < self.now)
            .order_by(Ticket.due_at).limit(100)).unique()
        overdue = [{
            "id": t.id, "ticket_number": t.ticket_number, "subject": t.subject, "priority": t.priority,
            "status_name_th": t.status_ref.name_th, "department": t.department.name_th,
            "assigned_user": t.assigned_user.full_name if t.assigned_user else None, "due_at": t.due_at,
            "hours_overdue": _round((self.now - t.due_at).total_seconds() / 3600),
        } for t in overdue_rows]

        return {"overall": overall, "by_request_type": by_type, "by_priority": by_priority,
                "open_aging": aging, "overdue": overdue, "targets": targets}
