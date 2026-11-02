"""Shared ticket filtering used by the ticket list, CSV export, dashboard and reports."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import Select, and_, case, or_, select
from sqlalchemy.sql.elements import ColumnElement

from app.config import get_settings
from app.models import Customer, CustomerContact, RequestType, Ticket, TicketDetail, TicketStatus, User, utcnow
from app.security.permissions import ticket_scope

OPEN_CATEGORIES = ("NEW", "OPEN", "WAITING")
SORTABLE = {"created_at", "last_activity_at", "ticket_number", "priority", "status", "due_at"}
PRIORITY_RANK = {"URGENT": 4, "HIGH": 3, "NORMAL": 2, "LOW": 1}


@dataclass
class TicketFilters:
    q: str | None = None
    statuses: list[str] = field(default_factory=list)
    status_category: str | None = None
    request_type: str | None = None
    department_id: int | None = None
    assigned: str | None = None  # "me" | "none" | user id
    priority: str | None = None
    date_from: date | None = None
    date_to: date | None = None
    overdue: bool | None = None
    include_sample: bool = True


def bangkok_bounds(d_from: date | None, d_to: date | None) -> tuple[datetime | None, datetime | None]:
    tz = ZoneInfo(get_settings().timezone)
    start = datetime.combine(d_from, time.min, tz) if d_from else None
    end = datetime.combine(d_to + timedelta(days=1), time.min, tz) if d_to else None
    return start, end


def _escape_like(s: str) -> str:
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def is_open_expr() -> ColumnElement[bool]:
    return Ticket.status.in_(select(TicketStatus.code).where(TicketStatus.category.in_(OPEN_CATEGORIES)))


def overdue_expr(now: datetime | None = None) -> ColumnElement[bool]:
    return and_(Ticket.due_at.is_not(None), Ticket.due_at < (now or utcnow()), is_open_expr())


def conditions(user: User, f: TicketFilters, staff_queue: bool) -> list[ColumnElement[bool]]:
    conds: list[ColumnElement[bool]] = []
    scope = ticket_scope(user, staff_queue)
    if scope is not None:
        conds.append(scope)
    if f.q:
        q = f.q.strip()[:100]
        pat = f"%{_escape_like(q)}%"
        conds.append(or_(
            Ticket.ticket_number.ilike(pat, escape="\\"),
            Ticket.subject.ilike(pat, escape="\\"),
            Ticket.customer_id.in_(select(Customer.id).where(Customer.name.ilike(pat, escape="\\"))),
            Ticket.contact_id.in_(select(CustomerContact.id).where(or_(
                CustomerContact.name.ilike(pat, escape="\\"), CustomerContact.phone.ilike(pat, escape="\\")))),
            Ticket.id.in_(select(TicketDetail.ticket_id).where(TicketDetail.value_text.ilike(pat, escape="\\"))),
        ))
    if f.statuses:
        conds.append(Ticket.status.in_(f.statuses))
    if f.status_category:
        cats = OPEN_CATEGORIES if f.status_category == "ACTIVE" else (f.status_category,)
        conds.append(Ticket.status.in_(select(TicketStatus.code).where(TicketStatus.category.in_(cats))))
    if f.request_type:
        conds.append(Ticket.request_type_id.in_(select(RequestType.id).where(RequestType.code == f.request_type)))
    if f.department_id:
        conds.append(Ticket.department_id == f.department_id)
    if f.assigned == "me":
        conds.append(Ticket.assigned_user_id == user.id)
    elif f.assigned == "none":
        conds.append(Ticket.assigned_user_id.is_(None))
    elif f.assigned and f.assigned.isdigit():
        conds.append(Ticket.assigned_user_id == int(f.assigned))
    if f.priority:
        conds.append(Ticket.priority == f.priority)
    start, end = bangkok_bounds(f.date_from, f.date_to)
    if start:
        conds.append(Ticket.created_at >= start)
    if end:
        conds.append(Ticket.created_at < end)
    if f.overdue:
        conds.append(overdue_expr())
    if not f.include_sample:
        conds.append(Ticket.is_sample.is_(False))
    return conds


def list_statement(user: User, f: TicketFilters, staff_queue: bool, sort: str = "created_at",
                   direction: str = "desc") -> Select:
    stmt = select(Ticket).where(*conditions(user, f, staff_queue))
    if sort not in SORTABLE:
        sort = "created_at"
    if sort == "priority":
        col = case({k: v for k, v in PRIORITY_RANK.items()}, value=Ticket.priority)
    elif sort == "status":
        col = select(TicketStatus.sort_order).where(TicketStatus.code == Ticket.status).scalar_subquery()
    else:
        col = getattr(Ticket, sort)
    order = col.asc().nulls_last() if direction == "asc" else col.desc().nulls_last()
    return stmt.order_by(order, Ticket.id.desc())
