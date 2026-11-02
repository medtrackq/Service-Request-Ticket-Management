"""Role-based access control for tickets.

Roles
-----
ADMIN    full access to every ticket and to administration.
MANAGER  tickets of departments the user belongs to (+ tickets assigned to them);
         can assign/transfer/bulk-assign/export within those departments.
STAFF    tickets assigned to them, plus (when the setting
         `access.staff_see_department_queue` is on) the queue of their departments.
         Staff may change status only on tickets assigned to them, may take
         (self-assign) unassigned tickets of their departments, and may transfer
         tickets of their departments to another department.

Customers never authenticate as staff; they access a single ticket with a
ticket number + tracking token (see services/tracking.py).
"""
from __future__ import annotations

from sqlalchemy import false, or_
from sqlalchemy.sql.elements import ColumnElement

from app.models import Ticket, User


def is_admin(user: User) -> bool:
    return user.role == "ADMIN"


def in_department(user: User, department_id: int) -> bool:
    return department_id in user.department_ids


def ticket_scope(user: User, staff_queue: bool) -> ColumnElement[bool] | None:
    """SQL filter restricting tickets to what `user` may see. None means unrestricted."""
    if is_admin(user):
        return None
    dept_ids = user.department_ids
    if user.role == "MANAGER" or (user.role == "STAFF" and staff_queue):
        conds = [Ticket.assigned_user_id == user.id]
        if dept_ids:
            conds.append(Ticket.department_id.in_(dept_ids))
        return or_(*conds)
    if user.role == "STAFF":
        return Ticket.assigned_user_id == user.id
    return false()


def can_view(user: User, ticket: Ticket, staff_queue: bool) -> bool:
    if is_admin(user) or ticket.assigned_user_id == user.id:
        return True
    if user.role == "MANAGER" or (user.role == "STAFF" and staff_queue):
        return in_department(user, ticket.department_id)
    return False


def can_comment(user: User, ticket: Ticket, staff_queue: bool) -> bool:
    return can_view(user, ticket, staff_queue)


def can_change_status(user: User, ticket: Ticket) -> bool:
    if is_admin(user) or ticket.assigned_user_id == user.id:
        return True
    return user.role == "MANAGER" and in_department(user, ticket.department_id)


def can_manage_department(user: User, department_id: int) -> bool:
    """Assign staff, set priority/due date, bulk-assign within a department."""
    return is_admin(user) or (user.role == "MANAGER" and in_department(user, department_id))


def can_self_assign(user: User, ticket: Ticket) -> bool:
    return (
        user.role in ("MANAGER", "STAFF")
        and in_department(user, ticket.department_id)
        and ticket.assigned_user_id in (None, user.id)
    )


def can_transfer(user: User, ticket: Ticket) -> bool:
    if is_admin(user):
        return True
    if user.role in ("MANAGER", "STAFF") and in_department(user, ticket.department_id):
        return True
    return ticket.assigned_user_id == user.id


def can_export(user: User) -> bool:
    return user.role in ("ADMIN", "MANAGER")


def can_view_reports(user: User) -> bool:
    return user.role in ("ADMIN", "MANAGER")
