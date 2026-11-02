"""Notification service (transactional outbox).

Business operations call these helpers inside their own transaction. They only
INSERT rows into `ticket_notifications`:

* IN_APP rows are immediately visible in the staff notification inbox.
* EMAIL / LINE rows are PENDING and are delivered asynchronously by the worker
  (app/worker.py) with retries and error logging.

Because delivery happens after commit in a separate process, an SMTP/LINE outage
can never roll back or block ticket creation.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import utcnow, Department, Ticket, TicketNotification, TicketStatus, User, user_departments
from app.services.settings_service import get_setting

CUSTOMER_CREATED_EVENT = "TICKET_CREATED_CUSTOMER"


def staff_ticket_url(ticket: Ticket) -> str:
    return f"{get_settings().public_base_url}/admin/tickets/{ticket.id}"


def tracking_url(ticket_number: str, token: str | None = None) -> str:
    base = f"{get_settings().public_base_url}/track/{ticket_number}"
    # The token is placed in the URL fragment so it is never sent to servers/logs.
    return f"{base}#t={token}" if token else base


def _department_users(db: Session, department_id: int, roles: tuple[str, ...] | None = None) -> list[User]:
    stmt = (
        select(User)
        .join(user_departments, user_departments.c.user_id == User.id)
        .where(user_departments.c.department_id == department_id, User.is_active.is_(True))
    )
    if roles:
        stmt = stmt.where(User.role.in_(roles))
    return list(db.scalars(stmt).unique())


def _in_app(db: Session, ticket: Ticket, user: User, event: str, subject: str, body: str) -> None:
    db.add(
        TicketNotification(
            ticket_id=ticket.id, event_type=event, channel="IN_APP", recipient_user_id=user.id,
            subject=subject[:300], body=body, link_url=f"/admin/tickets/{ticket.id}", status="SENT",
            attempts=0, sent_at=utcnow(),
        )
    )


def _email(db: Session, ticket: Ticket, address: str | None, event: str, subject: str, body: str,
           user: User | None = None, link: str | None = None) -> None:
    if not address:
        return
    db.add(
        TicketNotification(
            ticket_id=ticket.id, event_type=event, channel="EMAIL", recipient_user_id=user.id if user else None,
            recipient_address=address, subject=subject[:300], body=body, link_url=link, status="PENDING",
        )
    )


def _line(db: Session, ticket: Ticket, event: str, text: str) -> None:
    """Queue a LINE push to the customer (future). Only when explicitly enabled and the
    customer's LINE identity was verified via LIFF."""
    settings = get_settings()
    if not get_setting(db, "notifications.line_enabled") or not settings.line_messaging_channel_access_token:
        return
    line_user_id = ticket.line_user_id
    if not line_user_id:
        return
    db.add(
        TicketNotification(
            ticket_id=ticket.id, event_type=event, channel="LINE", recipient_address=line_user_id,
            subject=f"Ticket {ticket.ticket_number}", body=text[:4900], status="PENDING",
        )
    )


def _notify_staff(db: Session, ticket: Ticket, users: list[User], event: str, subject: str, body: str,
                  exclude_user_id: int | None = None) -> None:
    email_on = bool(get_setting(db, "notifications.email_enabled"))
    seen: set[int] = set()
    for u in users:
        if u.id in seen or u.id == exclude_user_id:
            continue
        seen.add(u.id)
        _in_app(db, ticket, u, event, subject, body)
        if email_on and u.email:
            _email(db, ticket, u.email, event, subject, f"{body}\n\nเปิด Ticket: {staff_ticket_url(ticket)}",
                   user=u, link=staff_ticket_url(ticket))


def _ticket_summary(ticket: Ticket) -> str:
    return (
        f"เลขที่: {ticket.ticket_number}\n"
        f"ประเภท: {ticket.request_type.name_th}\n"
        f"เรื่อง: {ticket.subject}\n"
        f"ลูกค้า: {ticket.customer.name}\n"
        f"ความสำคัญ: {ticket.priority}"
    )


# --------------------------------------------------------------------------- events


def ticket_created(db: Session, ticket: Ticket, tracking_token: str) -> None:
    subject = f"[Ticket ใหม่] {ticket.ticket_number} {ticket.subject}"
    body = "มี Ticket ใหม่เข้าสู่แผนกของท่าน\n\n" + _ticket_summary(ticket)
    users = _department_users(db, ticket.department_id)
    if ticket.assigned_user is not None:
        users.append(ticket.assigned_user)
    _notify_staff(db, ticket, users, "TICKET_CREATED", subject, body)

    dept = db.get(Department, ticket.department_id)
    if dept and dept.email and get_setting(db, "notifications.email_enabled"):
        _email(db, ticket, dept.email, "TICKET_CREATED", subject,
               f"{body}\n\nเปิด Ticket: {staff_ticket_url(ticket)}", link=staff_ticket_url(ticket))

    if ticket.contact.email and get_setting(db, "notifications.customer_email_enabled"):
        url = tracking_url(ticket.ticket_number, tracking_token)
        _email(
            db, ticket, ticket.contact.email, CUSTOMER_CREATED_EVENT,
            f"[BUC] ได้รับคำขอของท่านแล้ว เลขที่ {ticket.ticket_number}",
            (
                f"เรียน คุณ{ticket.contact.name}\n\n"
                f"บริษัท บางกอกยูนิเทรด จำกัด ได้รับคำขอของท่านเรียบร้อยแล้ว\n\n"
                f"เลขที่ Ticket: {ticket.ticket_number}\nเรื่อง: {ticket.subject}\n\n"
                f"ติดตามสถานะได้ที่: {url}\n"
                "(กรุณาเก็บลิงก์นี้ไว้เป็นความลับ ลิงก์นี้ใช้สำหรับดูสถานะคำขอของท่าน)\n\n"
                "อีเมลนี้ส่งจากระบบอัตโนมัติ กรุณาอย่าตอบกลับ"
            ),
            link=url,
        )
    _line(db, ticket, "TICKET_CREATED", f"ได้รับคำขอเลขที่ {ticket.ticket_number} แล้ว")


def ticket_assigned(db: Session, ticket: Ticket, assignee: User, actor: User | None) -> None:
    subject = f"[มอบหมายงาน] {ticket.ticket_number} {ticket.subject}"
    by = f" โดย {actor.full_name}" if actor else ""
    body = f"ท่านได้รับมอบหมาย Ticket{by}\n\n" + _ticket_summary(ticket)
    if ticket.due_at:
        body += f"\nกำหนดเสร็จ: {ticket.due_at.isoformat()}"
    _notify_staff(db, ticket, [assignee], "TICKET_ASSIGNED", subject, body,
                  exclude_user_id=actor.id if actor else None)


def ticket_transferred(db: Session, ticket: Ticket, from_department: Department | None, actor: User | None) -> None:
    subject = f"[โอนงาน] {ticket.ticket_number} {ticket.subject}"
    src = f" จากแผนก {from_department.name_th}" if from_department else ""
    body = f"Ticket ถูกโอนมายังแผนกของท่าน{src}\n\n" + _ticket_summary(ticket)
    _notify_staff(db, ticket, _department_users(db, ticket.department_id), "TICKET_TRANSFERRED", subject, body,
                  exclude_user_id=actor.id if actor else None)


def status_changed(db: Session, ticket: Ticket, new_status: TicketStatus, public_message: str | None,
                   actor: User | None) -> None:
    # Internal: tell the assignee when someone else changed their ticket.
    if ticket.assigned_user is not None and (actor is None or actor.id != ticket.assigned_user_id):
        _notify_staff(db, ticket, [ticket.assigned_user], "STATUS_CHANGED",
                      f"[สถานะ] {ticket.ticket_number}: {new_status.name_th}",
                      f"สถานะ Ticket เปลี่ยนเป็น {new_status.name_th}\n\n" + _ticket_summary(ticket))
    # Customer: status change e-mail (no internal comment, no staff names).
    if ticket.contact.email and get_setting(db, "notifications.customer_email_enabled") and not ticket.anonymized_at:
        msg = f"\n\nข้อความจากเจ้าหน้าที่:\n{public_message}" if public_message else ""
        _email(
            db, ticket, ticket.contact.email, "STATUS_CHANGED_CUSTOMER",
            f"[BUC] อัปเดตสถานะ {ticket.ticket_number}: {new_status.name_th}",
            (
                f"เรียน คุณ{ticket.contact.name}\n\n"
                f"คำขอเลขที่ {ticket.ticket_number} ({ticket.subject})\n"
                f"สถานะปัจจุบัน: {new_status.name_th}{msg}\n\n"
                f"ติดตามสถานะได้ที่ {tracking_url(ticket.ticket_number)} "
                "โดยใช้ลิงก์ติดตามสถานะที่ได้รับเมื่อส่งคำขอ\n\n"
                "อีเมลนี้ส่งจากระบบอัตโนมัติ กรุณาอย่าตอบกลับ"
            ),
        )
    _line(db, ticket, "STATUS_CHANGED", f"คำขอ {ticket.ticket_number} สถานะ: {new_status.name_th}")


def public_update(db: Session, ticket: Ticket, message: str) -> None:
    if ticket.contact.email and get_setting(db, "notifications.customer_email_enabled") and not ticket.anonymized_at:
        _email(
            db, ticket, ticket.contact.email, "PUBLIC_UPDATE_CUSTOMER",
            f"[BUC] ข้อความใหม่สำหรับคำขอ {ticket.ticket_number}",
            (
                f"เรียน คุณ{ticket.contact.name}\n\nข้อความจากเจ้าหน้าที่เกี่ยวกับคำขอ {ticket.ticket_number}:\n\n"
                f"{message}\n\nดูรายละเอียดได้ที่ {tracking_url(ticket.ticket_number)}\n\n"
                "อีเมลนี้ส่งจากระบบอัตโนมัติ กรุณาอย่าตอบกลับ"
            ),
        )
    _line(db, ticket, "PUBLIC_UPDATE", f"ข้อความใหม่สำหรับคำขอ {ticket.ticket_number}: {message[:300]}")


def customer_replied(db: Session, ticket: Ticket) -> None:
    users = [ticket.assigned_user] if ticket.assigned_user else _department_users(db, ticket.department_id)
    _notify_staff(db, ticket, users, "CUSTOMER_REPLY", f"[ลูกค้าตอบกลับ] {ticket.ticket_number}",
                  "ลูกค้าส่งข้อมูลเพิ่มเติม\n\n" + _ticket_summary(ticket))


def ticket_overdue(db: Session, ticket: Ticket) -> None:
    users = _department_users(db, ticket.department_id, roles=("MANAGER",))
    if ticket.assigned_user:
        users.append(ticket.assigned_user)
    _notify_staff(db, ticket, users, "TICKET_OVERDUE", f"[เกินกำหนด] {ticket.ticket_number} {ticket.subject}",
                  "Ticket เกินกำหนดเวลาดำเนินการ\n\n" + _ticket_summary(ticket))
