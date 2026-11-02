"""Department / staff assignment, transfers and automatic assignment rules."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AssignmentRule, Department, RequestType, Ticket, TicketAssignment, User, utcnow
from app.models.workflow import PRIORITIES
from app.security import permissions as perm
from app.services import notifications, workflow
from app.services.errors import Forbidden, NotFound, ValidationFailed
from app.services.settings_service import get_setting


@dataclass
class InitialAssignment:
    department_id: int
    user_id: int | None
    rule: AssignmentRule | None


def resolve_initial(db: Session, request_type: RequestType, *, category: str | None, customer_type: str | None,
                    priority: str) -> InitialAssignment:
    """Default department from the request type; optionally overridden by the first matching rule."""
    result = InitialAssignment(request_type.default_department_id, None, None)
    if not get_setting(db, "assignment.auto_enabled"):
        return result
    rules = db.scalars(
        select(AssignmentRule).where(AssignmentRule.is_active.is_(True)).order_by(AssignmentRule.sort_order,
                                                                                 AssignmentRule.id)
    ).unique()
    for r in rules:
        if r.request_type_id is not None and r.request_type_id != request_type.id:
            continue
        if r.category is not None and r.category != category:
            continue
        if r.customer_type is not None and r.customer_type != customer_type:
            continue
        if r.priority is not None and r.priority != priority:
            continue
        user_id = None
        if r.assigned_user is not None and r.assigned_user.is_active:
            user_id = r.assigned_user.id
        return InitialAssignment(r.department_id, user_id, r)
    return result


def _eligible_assignee(user: User | None, department_id: int) -> bool:
    return bool(user and user.is_active and (user.role == "ADMIN" or department_id in user.department_ids))


def assign(
    db: Session,
    ticket: Ticket,
    actor: User,
    *,
    department_id: int | None = None,
    assigned_user_id: int | None = None,
    unassign: bool = False,
    priority: str | None = None,
    due_at: datetime | None = None,
    reason: str | None = None,
) -> Ticket:
    """Assign / transfer / re-prioritise a ticket, enforcing permissions server-side."""
    target_dept_id = department_id or ticket.department_id
    target_dept = db.get(Department, target_dept_id)
    if target_dept is None or not target_dept.is_active:
        raise NotFound("ไม่พบแผนกที่เลือก")
    transferring = target_dept_id != ticket.department_id

    if transferring and not perm.can_transfer(actor, ticket):
        raise Forbidden("ท่านไม่มีสิทธิ์โอนงานไปยังแผนกอื่น")

    new_user: User | None = ticket.assigned_user
    if transferring:
        new_user = None  # a transfer clears the assignee unless a new one is named
    if unassign:
        new_user = None
    if assigned_user_id is not None:
        new_user = db.get(User, assigned_user_id)
        if not _eligible_assignee(new_user, target_dept_id):
            raise ValidationFailed("ผู้รับผิดชอบต้องเป็นผู้ใช้งานที่ใช้งานอยู่และอยู่ในแผนกที่เลือก",
                                   fields={"assigned_user_id": "ไม่สามารถมอบหมายให้ผู้ใช้นี้ได้"})

    user_changed = (new_user.id if new_user else None) != ticket.assigned_user_id
    if user_changed and not transferring:
        self_take = new_user is not None and new_user.id == actor.id and perm.can_self_assign(actor, ticket)
        if not (self_take or perm.can_manage_department(actor, ticket.department_id)):
            raise Forbidden("ท่านไม่มีสิทธิ์มอบหมายงานนี้")
    if transferring and new_user is not None and new_user.id != actor.id:
        if not perm.can_manage_department(actor, target_dept_id) and not perm.can_manage_department(
            actor, ticket.department_id
        ):
            raise Forbidden("ท่านไม่มีสิทธิ์มอบหมายผู้รับผิดชอบในแผนกปลายทาง")

    if priority is not None:
        if priority not in PRIORITIES:
            raise ValidationFailed("ระดับความสำคัญไม่ถูกต้อง", fields={"priority": "ไม่ถูกต้อง"})
        if priority != ticket.priority and not perm.can_manage_department(actor, ticket.department_id) \
                and ticket.assigned_user_id != actor.id:
            raise Forbidden("ท่านไม่มีสิทธิ์เปลี่ยนระดับความสำคัญ")
    if due_at is not None and due_at != ticket.due_at and not perm.can_manage_department(actor, ticket.department_id):
        raise Forbidden("ท่านไม่มีสิทธิ์กำหนดวันครบกำหนด")

    changed_priority = priority is not None and priority != ticket.priority
    changed_due = due_at is not None and due_at != ticket.due_at
    if not (transferring or user_changed or changed_priority or changed_due):
        return ticket

    from_dept = ticket.department
    from_user_id = ticket.assigned_user_id
    if transferring:
        assignment_type = "TRANSFER"
    elif user_changed and new_user is not None and new_user.id == actor.id:
        assignment_type = "SELF"
    else:
        assignment_type = "MANUAL"

    ticket.department_id = target_dept_id
    ticket.department = target_dept
    ticket.assigned_user_id = new_user.id if new_user else None
    ticket.assigned_user = new_user
    if changed_priority:
        ticket.priority = priority  # type: ignore[assignment]
    if changed_due:
        ticket.due_at = due_at
        ticket.overdue_notified_at = None
    ticket.last_activity_at = utcnow()

    db.add(
        TicketAssignment(
            ticket_id=ticket.id, assignment_type=assignment_type,
            from_department_id=from_dept.id if from_dept else None, to_department_id=target_dept_id,
            from_user_id=from_user_id, to_user_id=ticket.assigned_user_id, assigned_by_user_id=actor.id,
            priority=ticket.priority, due_at=ticket.due_at, reason=(reason or None),
        )
    )

    # Assigning a person to a ticket that is still NEW/REVIEW moves it to ASSIGNED.
    if new_user is not None and user_changed and ticket.status in ("NEW", "REVIEW"):
        workflow.system_transition(db, ticket, "ASSIGNED", "มอบหมายงานแล้ว", actor=actor)

    if transferring:
        notifications.ticket_transferred(db, ticket, from_dept, actor)
    if new_user is not None and user_changed:
        notifications.ticket_assigned(db, ticket, new_user, actor)
    db.flush()
    return ticket
