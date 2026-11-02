"""Operational commands.

    python -m app.cli seed                       # reference data (idempotent)
    python -m app.cli create-admin --username admin --full-name "System Admin" --email admin@example.com
    python -m app.cli load-sample-data --tickets 60 [--with-users]
    python -m app.cli purge-sample-data
    python -m app.cli export-openapi docs/openapi.json
"""
from __future__ import annotations

import argparse
import getpass
import json
import os
import random
import secrets
import sys
from datetime import timedelta

from sqlalchemy import delete, func, select, update

from app.db import SessionLocal
from app.models import (
    Customer,
    CustomerContact,
    Department,
    Ticket,
    TicketAssignment,
    TicketComment,
    TicketNotification,
    TicketStatus,
    TicketStatusHistory,
    TicketTrackingToken,
    User,
    utcnow,
)
from app.security.passwords import hash_password, password_policy_errors
from app.seed import seed_reference_data

SAMPLE_PREFIX = "[ตัวอย่าง] "


def cmd_seed(_: argparse.Namespace) -> None:
    with SessionLocal() as db:
        created = seed_reference_data(db)
        db.commit()
    print("seed complete:", created)


def cmd_create_admin(args: argparse.Namespace) -> None:
    password = os.environ.get("BUC_ADMIN_PASSWORD") or args.password
    if not password:
        if sys.stdin.isatty():
            password = getpass.getpass("Password for the new administrator: ")
        else:
            password = secrets.token_urlsafe(12)
            print(f"Generated temporary password (change at first login): {password}")
    errors = password_policy_errors(password, 10)
    if errors:
        sys.exit("Password rejected: " + "; ".join(errors))
    with SessionLocal() as db:
        existing = db.scalar(select(User).where(func.lower(User.username) == args.username.lower()))
        if existing:
            print(f"user '{args.username}' already exists — nothing changed")
            return
        user = User(username=args.username.lower(), full_name=args.full_name, email=args.email, role="ADMIN",
                    password_hash=hash_password(password), must_change_password=not args.no_force_change)
        db.add(user)
        db.commit()
    print(f"administrator '{args.username}' created")


# ------------------------------------------------------------------ sample data

SAMPLE_ORGS = [
    ("โรงพยาบาลสมมติเวช", "PRIVATE_HOSPITAL"), ("โรงพยาบาลศูนย์ตัวอย่าง", "GOV_HOSPITAL"),
    ("คลินิกทดสอบการแพทย์", "CLINIC"), ("โรงพยาบาลจำลองนคร", "GOV_HOSPITAL"),
    ("บริษัท เดโม่ เฮลท์แคร์ จำกัด", "COMPANY"), ("โรงพยาบาลสาธิตราษฎร์", "PRIVATE_HOSPITAL"),
]
SAMPLE_PEOPLE = ["สมชาย ใจดี", "สมหญิง รักงาน", "วิชัย มั่นคง", "อรุณี แสงทอง", "ปกรณ์ สุขสันต์", "มาลี ศรีสุข"]
SAMPLE_DEPTS = ["ห้องผ่าตัด", "ICU", "ฝ่ายพัสดุ", "ห้องฉุกเฉิน", "แผนกเครื่องมือแพทย์", "ฝ่ายการเงิน"]


def _sample_values(code: str, rnd: random.Random) -> dict:
    org, otype = rnd.choice(SAMPLE_ORGS)
    v = {"organization": SAMPLE_PREFIX + org, "organization_type": otype, "department": rnd.choice(SAMPLE_DEPTS),
         "contact_name": rnd.choice(SAMPLE_PEOPLE), "phone": f"08{rnd.randint(10000000, 99999999)}",
         "email": f"sample{rnd.randint(1, 9)}@example.com"}
    equipment = ["เครื่องวัดความดันโลหิต", "เครื่องดูดเสมหะ", "เครื่องให้สารละลาย (Infusion Pump)",
                 "เตียงผู้ป่วยไฟฟ้า", "โคมไฟผ่าตัด", "เครื่องนึ่งฆ่าเชื้อ"]
    products = ["ชุดเครื่องมือผ่าตัดทั่วไป", "ถุงมือผ่าตัด", "เครื่องวัดออกซิเจนปลายนิ้ว", "สายสวนปัสสาวะ"]
    if code == "SERVICE":
        v |= {"equipment_type": rnd.choice(["MEDICAL_DEVICE", "SURGICAL_INSTRUMENT", "HOSPITAL_EQUIPMENT"]),
              "equipment_name": rnd.choice(equipment), "brand": "SampleMed", "model": f"SM-{rnd.randint(100, 999)}",
              "serial_number": f"SN{rnd.randint(100000, 999999)}", "install_location": "อาคาร 1 ชั้น 2",
              "problem_type": rnd.choice(["EQUIPMENT_FAILURE", "ABNORMAL_OPERATION", "INSPECTION_REQUEST",
                                          "PREVENTIVE_MAINTENANCE"]),
              "problem_description": "ข้อมูลตัวอย่าง: เครื่องแสดงข้อความผิดพลาดเมื่อเปิดใช้งาน",
              "urgency": rnd.choice(["LOW", "NORMAL", "NORMAL", "HIGH", "URGENT"])}
    elif code == "PRODUCT":
        v |= {"product_name": rnd.choice(products), "quantity": rnd.randint(1, 50),
              "question": "ข้อมูลตัวอย่าง: ขอทราบรายละเอียดสเปกและระยะเวลาจัดส่ง"}
    elif code == "DELIVERY":
        v |= {"po_number": f"PO-{rnd.randint(10000, 99999)}",
              "inquiry_details": "ข้อมูลตัวอย่าง: ต้องการทราบกำหนดส่งสินค้า"}
    elif code == "QUOTATION":
        v |= {"product_name": rnd.choice(products), "quantity": rnd.randint(1, 200),
              "specifications": "ข้อมูลตัวอย่าง: ตามสเปกที่แนบ"}
    elif code == "ACCOUNTING":
        v |= {"topic_type": rnd.choice(["INVOICE", "RECEIPT", "PAYMENT"]), "invoice_no": f"IV{rnd.randint(1000, 9999)}",
              "question": "ข้อมูลตัวอย่าง: ขอสำเนาเอกสาร"}
    else:
        v |= {"subject": "ข้อมูลตัวอย่าง: สอบถามช่องทางติดต่อ", "question_type": "GENERAL_INQUIRY",
              "details": "ข้อมูลตัวอย่าง: ต้องการติดต่อผู้แทนขาย"}
    return v


def _ensure_sample_users(db) -> list[str]:
    created = []
    for dept in db.scalars(select(Department)):
        for role in ("MANAGER", "STAFF"):
            username = f"sample.{dept.code.lower()}.{role.lower()}"
            if db.scalar(select(User.id).where(User.username == username)):
                continue
            pw = secrets.token_urlsafe(9) + "-7"
            u = User(username=username, full_name=f"{SAMPLE_PREFIX}{role.title()} {dept.name_en}", role=role,
                     password_hash=hash_password(pw), must_change_password=True)
            u.departments = [dept]
            db.add(u)
            created.append(f"{username} / {pw}")
    db.commit()
    return created


def cmd_load_sample(args: argparse.Namespace) -> None:
    from app.services.ticket_service import submit_request

    rnd = random.Random(args.seed)
    with SessionLocal() as db:
        if args.with_users:
            for line in _ensure_sample_users(db):
                print("sample user:", line)
        types = ["SERVICE", "SERVICE", "SERVICE", "PRODUCT", "DELIVERY", "QUOTATION", "ACCOUNTING", "GENERAL"]
        slugs = {"SERVICE": "service", "PRODUCT": "product", "DELIVERY": "delivery", "QUOTATION": "quotation",
                 "ACCOUNTING": "accounting", "GENERAL": "general"}
        statuses = {s.code: s for s in db.scalars(select(TicketStatus))}
        for i in range(args.tickets):
            code = rnd.choice(types)
            res = submit_request(db, slug=slugs[code], form_definition_id=None, values=_sample_values(code, rnd),
                                 privacy_consent=True, uploads=[], idempotency_key=f"sample{secrets.token_hex(12)}",
                                 client_ip=None)
            t = db.get(Ticket, res.ticket.id)
            created = utcnow() - timedelta(days=rnd.uniform(0, args.days), hours=rnd.uniform(0, 12))
            delta = created - t.created_at
            t.created_at = created
            if t.due_at:
                t.due_at += delta
            t.is_sample = True
            db.execute(update(TicketStatusHistory).where(TicketStatusHistory.ticket_id == t.id)
                       .values(created_at=created))
            db.execute(update(TicketAssignment).where(TicketAssignment.ticket_id == t.id).values(created_at=created))
            db.execute(delete(TicketNotification).where(TicketNotification.ticket_id == t.id))
            staff = [u for u in db.scalars(select(User).where(User.is_active.is_(True))).unique()
                     if t.department_id in u.department_ids]
            path = rnd.choices([["NEW"], ["REVIEW"], ["ASSIGNED", "IN_PROGRESS"], ["ASSIGNED", "WAITING_CUSTOMER"],
                                ["ASSIGNED", "IN_PROGRESS", "RESOLVED"],
                                ["ASSIGNED", "IN_PROGRESS", "RESOLVED", "CLOSED"], ["CANCELLED"]],
                               weights=[2, 1, 3, 1, 2, 4, 1])[0]
            clock = created
            prev = "NEW"
            assignee = rnd.choice(staff) if staff and path[0] != "NEW" and path[0] != "CANCELLED" else None
            if assignee:
                t.assigned_user_id = assignee.id
                db.add(TicketAssignment(ticket_id=t.id, assignment_type="MANUAL", from_department_id=t.department_id,
                                        to_department_id=t.department_id, to_user_id=assignee.id,
                                        priority=t.priority, created_at=clock + timedelta(hours=0.5),
                                        reason="ข้อมูลตัวอย่าง"))
            for st in path:
                clock += timedelta(hours=rnd.uniform(0.5, 60))
                if clock > utcnow():
                    break
                db.add(TicketStatusHistory(ticket_id=t.id, from_status=prev, to_status=st, actor_type="STAFF",
                                           changed_by_user_id=assignee.id if assignee else None,
                                           comment="ข้อมูลตัวอย่าง", created_at=clock))
                if t.first_response_at is None:
                    t.first_response_at = clock
                if st == "RESOLVED":
                    t.resolved_at = clock
                if st == "CLOSED":
                    t.closed_at = clock
                if st == "CANCELLED":
                    t.cancelled_at = clock
                prev = st
            t.status = prev
            t.status_ref = statuses[prev]
            t.last_activity_at = clock if clock <= utcnow() else utcnow()
            if prev in ("IN_PROGRESS", "WAITING_CUSTOMER"):
                db.add(TicketComment(ticket_id=t.id, author_type="STAFF", visibility="PUBLIC",
                                     author_user_id=assignee.id if assignee else None,
                                     body="ข้อมูลตัวอย่าง: เจ้าหน้าที่กำลังดำเนินการตรวจสอบ", created_at=clock))
            db.commit()
        print(f"created {args.tickets} sample tickets (flagged is_sample=true)")


def cmd_purge_sample(_: argparse.Namespace) -> None:
    from app.services.files import remove_ticket_dir

    with SessionLocal() as db:
        ids = list(db.scalars(select(Ticket.id).where(Ticket.is_sample.is_(True))))
        contact_ids = set(db.scalars(select(Ticket.contact_id).where(Ticket.is_sample.is_(True))))
        for tid in ids:
            remove_ticket_dir(tid)
        db.execute(delete(TicketTrackingToken).where(TicketTrackingToken.ticket_id.in_(ids or [-1])))
        db.execute(delete(Ticket).where(Ticket.id.in_(ids or [-1])))
        db.flush()
        for cid in contact_ids:
            if not db.scalar(select(Ticket.id).where(Ticket.contact_id == cid).limit(1)):
                db.execute(delete(CustomerContact).where(CustomerContact.id == cid))
        db.flush()
        for c in db.scalars(select(Customer).where(Customer.name.startswith(SAMPLE_PREFIX))):
            if not db.scalar(select(Ticket.id).where(Ticket.customer_id == c.id).limit(1)):
                db.execute(delete(CustomerContact).where(CustomerContact.customer_id == c.id))
                db.delete(c)
        db.execute(update(User).where(User.username.startswith("sample.")).values(is_active=False))
        db.commit()
    print(f"purged {len(ids)} sample tickets; sample users deactivated (ticket number counters are not reset)")


def cmd_export_openapi(args: argparse.Namespace) -> None:
    from app.main import app

    with open(args.path, "w", encoding="utf-8") as fh:
        json.dump(app.openapi(), fh, ensure_ascii=False, indent=2)
    print("written", args.path)


def main() -> None:
    p = argparse.ArgumentParser(prog="python -m app.cli")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("seed").set_defaults(fn=cmd_seed)
    a = sub.add_parser("create-admin")
    a.add_argument("--username", required=True)
    a.add_argument("--full-name", required=True)
    a.add_argument("--email")
    a.add_argument("--password", help="prefer BUC_ADMIN_PASSWORD env var or the interactive prompt")
    a.add_argument("--no-force-change", action="store_true", help="do not require a password change at first login")
    a.set_defaults(fn=cmd_create_admin)
    s = sub.add_parser("load-sample-data")
    s.add_argument("--tickets", type=int, default=60)
    s.add_argument("--days", type=int, default=150)
    s.add_argument("--seed", type=int, default=42)
    s.add_argument("--with-users", action="store_true")
    s.set_defaults(fn=cmd_load_sample)
    sub.add_parser("purge-sample-data").set_defaults(fn=cmd_purge_sample)
    o = sub.add_parser("export-openapi")
    o.add_argument("path")
    o.set_defaults(fn=cmd_export_openapi)
    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
