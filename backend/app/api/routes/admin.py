"""Administration API (System Administrator only unless noted)."""
from __future__ import annotations

import re
import secrets
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.config import get_settings
from app.db import get_db
from app.integrations.email_smtp import smtp_configured
from app.integrations.erpnext.adapter import upsert_mapping
from app.integrations.line.liff import liff_enabled
from app.models import (
    AssignmentRule,
    AuditLog,
    Customer,
    CustomerContact,
    Department,
    FormDefinition,
    FormField,
    IntegrationLog,
    IntegrationMapping,
    RequestType,
    Ticket,
    TicketNotification,
    TicketStatus,
    User,
    WorkflowTransition,
    utcnow,
)
from app.models.customers import CUSTOMER_TYPES
from app.models.workflow import PRIORITIES
from app.security.passwords import hash_password, password_policy_errors
from app.security.sessions import revoke_all_sessions
from app.services.audit import audit
from app.services.errors import Conflict, NotFound, ValidationFailed
from app.services.form_engine import validate_field_definitions
from app.services.settings_service import DEFAULTS, get_settings_map, set_setting
from app.services.ticket_query import bangkok_bounds

router = APIRouter(prefix="/admin", tags=["administration"])
ROLES = ("ADMIN", "MANAGER", "STAFF")


def _page(stmt, db: Session, page: int, page_size: int):
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    return total, list(db.scalars(stmt.limit(page_size).offset((page - 1) * page_size)).unique())


# ============================================================== users


class UserIn(BaseModel):
    username: str = Field(min_length=3, max_length=60, pattern=r"^[a-zA-Z0-9._-]+$")
    full_name: str = Field(min_length=1, max_length=150)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=30)
    role: str = Field(pattern="^(ADMIN|MANAGER|STAFF)$")
    department_ids: list[int] = []
    password: str | None = Field(default=None, max_length=128)
    is_active: bool = True


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=150)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=30)
    role: str | None = Field(default=None, pattern="^(ADMIN|MANAGER|STAFF)$")
    department_ids: list[int] | None = None
    is_active: bool | None = None
    preferred_language: str | None = Field(default=None, pattern="^(th|en)$")


def _user_out(u: User) -> dict[str, Any]:
    return {"id": u.id, "username": u.username, "full_name": u.full_name, "email": u.email, "phone": u.phone,
            "role": u.role, "is_active": u.is_active, "must_change_password": u.must_change_password,
            "locked_until": u.locked_until, "last_login_at": u.last_login_at, "created_at": u.created_at,
            "departments": [{"id": d.id, "name_th": d.name_th, "name_en": d.name_en} for d in u.departments],
            "department_ids": u.department_ids}


def _departments(db: Session, ids: list[int]) -> list[Department]:
    depts = list(db.scalars(select(Department).where(Department.id.in_(ids)))) if ids else []
    if len(depts) != len(set(ids)):
        raise ValidationFailed("ไม่พบแผนกบางรายการ", fields={"department_ids": "ไม่ถูกต้อง"})
    return depts


def _temp_password() -> str:
    return secrets.token_urlsafe(9) + "-" + str(secrets.randbelow(90) + 10)


@router.get("/users")
def list_users(q: str | None = None, include_inactive: bool = True, admin: User = Depends(require_admin),
               db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    stmt = select(User).order_by(User.is_active.desc(), User.full_name)
    if q:
        pat = f"%{q.strip()[:60]}%"
        stmt = stmt.where(or_(User.full_name.ilike(pat), User.username.ilike(pat), User.email.ilike(pat)))
    if not include_inactive:
        stmt = stmt.where(User.is_active.is_(True))
    return [_user_out(u) for u in db.scalars(stmt).unique()]


@router.post("/users", status_code=201)
def create_user(body: UserIn, request: Request, admin: User = Depends(require_admin),
                db: Session = Depends(get_db)) -> dict[str, Any]:
    password = body.password or _temp_password()
    errors = password_policy_errors(password, get_settings().password_min_length)
    if errors:
        raise ValidationFailed(errors[0], fields={"password": " / ".join(errors)})
    user = User(username=body.username.lower(), full_name=body.full_name.strip(),
                email=body.email.lower() if body.email else None, phone=body.phone, role=body.role,
                password_hash=hash_password(password), is_active=body.is_active, must_change_password=True)
    user.departments = _departments(db, body.department_ids)
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise Conflict("ชื่อผู้ใช้หรืออีเมลนี้มีอยู่แล้ว", fields={"username": "ซ้ำ"}) from None
    audit(db, "admin.user_created", actor=admin, entity_type="user", entity_id=user.id, request=request,
          details={"username": user.username, "role": user.role})
    db.commit()
    # The temporary password is returned once so the administrator can hand it over securely.
    return {**_user_out(user), "temporary_password": None if body.password else password}


@router.patch("/users/{user_id}")
def update_user(user_id: int, body: UserUpdate, request: Request, admin: User = Depends(require_admin),
                db: Session = Depends(get_db)) -> dict[str, Any]:
    user = db.get(User, user_id)
    if user is None:
        raise NotFound("ไม่พบผู้ใช้")
    data = body.model_dump(exclude_unset=True)
    if user.id == admin.id and (data.get("is_active") is False or data.get("role") not in (None, "ADMIN")):
        raise ValidationFailed("ไม่สามารถลดสิทธิ์หรือปิดใช้งานบัญชีของตนเองได้")
    if "department_ids" in data:
        user.departments = _departments(db, data.pop("department_ids") or [])
    if "email" in data and data["email"]:
        data["email"] = data["email"].lower()
    for k, v in data.items():
        setattr(user, k, v)
    if data.get("is_active") is False:
        revoke_all_sessions(db, user.id)
    if data.get("is_active") is True:
        user.locked_until = None
        user.failed_login_count = 0
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise Conflict("อีเมลนี้มีอยู่แล้ว", fields={"email": "ซ้ำ"}) from None
    audit(db, "admin.user_updated", actor=admin, entity_type="user", entity_id=user.id, request=request,
          details=body.model_dump(mode="json", exclude_unset=True))
    db.commit()
    return _user_out(user)


@router.post("/users/{user_id}/reset-password")
def reset_password(user_id: int, request: Request, admin: User = Depends(require_admin),
                   db: Session = Depends(get_db)) -> dict[str, Any]:
    user = db.get(User, user_id)
    if user is None:
        raise NotFound("ไม่พบผู้ใช้")
    password = _temp_password()
    user.password_hash = hash_password(password)
    user.must_change_password = True
    user.locked_until = None
    user.failed_login_count = 0
    revoke_all_sessions(db, user.id)
    audit(db, "admin.user_password_reset", actor=admin, entity_type="user", entity_id=user.id, request=request)
    db.commit()
    return {"temporary_password": password,
            "message": "ส่งรหัสผ่านชั่วคราวให้ผู้ใช้ทางช่องทางที่ปลอดภัย ผู้ใช้ต้องเปลี่ยนรหัสผ่านเมื่อเข้าสู่ระบบ"}


# ============================================================== departments


class DepartmentIn(BaseModel):
    code: str = Field(min_length=2, max_length=30, pattern=r"^[A-Z0-9_]+$")
    name_th: str = Field(min_length=1, max_length=150)
    name_en: str = Field(min_length=1, max_length=150)
    email: EmailStr | None = None
    is_active: bool = True
    sort_order: int = 0


class DepartmentUpdate(BaseModel):
    name_th: str | None = Field(default=None, min_length=1, max_length=150)
    name_en: str | None = Field(default=None, min_length=1, max_length=150)
    email: EmailStr | None = None
    is_active: bool | None = None
    sort_order: int | None = None


def _dept_out(d: Department, counts: dict[int, int]) -> dict[str, Any]:
    return {"id": d.id, "code": d.code, "name_th": d.name_th, "name_en": d.name_en, "email": d.email,
            "is_active": d.is_active, "sort_order": d.sort_order, "member_count": len(d.users),
            "open_tickets": counts.get(d.id, 0)}


@router.get("/departments")
def list_departments(admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    counts = dict(db.execute(
        select(Ticket.department_id, func.count()).join(TicketStatus, TicketStatus.code == Ticket.status)
        .where(TicketStatus.category.in_(("NEW", "OPEN", "WAITING"))).group_by(Ticket.department_id)).all())
    return [_dept_out(d, counts) for d in db.scalars(select(Department).order_by(Department.sort_order))]


@router.post("/departments", status_code=201)
def create_department(body: DepartmentIn, request: Request, admin: User = Depends(require_admin),
                      db: Session = Depends(get_db)) -> dict[str, Any]:
    d = Department(**body.model_dump())
    db.add(d)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise Conflict("รหัสแผนกนี้มีอยู่แล้ว", fields={"code": "ซ้ำ"}) from None
    audit(db, "admin.department_created", actor=admin, entity_type="department", entity_id=d.id, request=request,
          details=body.model_dump(mode="json"))
    db.commit()
    return _dept_out(d, {})


@router.patch("/departments/{department_id}")
def update_department(department_id: int, body: DepartmentUpdate, request: Request,
                      admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict[str, Any]:
    d = db.get(Department, department_id)
    if d is None:
        raise NotFound("ไม่พบแผนก")
    data = body.model_dump(exclude_unset=True)
    if data.get("is_active") is False and db.scalar(
            select(func.count()).select_from(RequestType).where(RequestType.default_department_id == d.id,
                                                                RequestType.is_active.is_(True))):
        raise ValidationFailed("แผนกนี้เป็นแผนกเริ่มต้นของประเภทคำขอที่ใช้งานอยู่ กรุณาเปลี่ยนก่อนปิดใช้งาน")
    for k, v in data.items():
        setattr(d, k, v)
    audit(db, "admin.department_updated", actor=admin, entity_type="department", entity_id=d.id, request=request,
          details=body.model_dump(mode="json", exclude_unset=True))
    db.commit()
    return _dept_out(d, {})


# ============================================================== request types & forms


class RequestTypeUpdate(BaseModel):
    name_th: str | None = Field(default=None, min_length=1, max_length=150)
    name_en: str | None = Field(default=None, min_length=1, max_length=150)
    description_th: str | None = Field(default=None, max_length=1000)
    description_en: str | None = Field(default=None, max_length=1000)
    default_department_id: int | None = None
    default_priority: str | None = Field(default=None, pattern="^(LOW|NORMAL|HIGH|URGENT)$")
    is_active: bool | None = None
    sort_order: int | None = None


def _rt_out(r: RequestType, db: Session) -> dict[str, Any]:
    active = db.scalar(select(FormDefinition).where(FormDefinition.request_type_id == r.id,
                                                    FormDefinition.is_active.is_(True)))
    base = get_settings().public_base_url
    return {"id": r.id, "code": r.code, "slug": r.slug, "ticket_prefix": r.ticket_prefix, "name_th": r.name_th,
            "name_en": r.name_en, "description_th": r.description_th, "description_en": r.description_en,
            "icon": r.icon, "default_department_id": r.default_department_id,
            "default_department_name": r.default_department.name_th, "default_priority": r.default_priority,
            "is_active": r.is_active, "sort_order": r.sort_order,
            "active_form_id": active.id if active else None, "active_form_version": active.version if active else None,
            "portal_url": f"{base}/request/{r.slug}"}


@router.get("/request-types")
def list_request_types(admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    return [_rt_out(r, db) for r in db.scalars(select(RequestType).order_by(RequestType.sort_order))]


@router.patch("/request-types/{rt_id}")
def update_request_type(rt_id: int, body: RequestTypeUpdate, request: Request, admin: User = Depends(require_admin),
                        db: Session = Depends(get_db)) -> dict[str, Any]:
    r = db.get(RequestType, rt_id)
    if r is None:
        raise NotFound("ไม่พบประเภทคำขอ")
    data = body.model_dump(exclude_unset=True)
    if "default_department_id" in data:
        d = db.get(Department, data["default_department_id"])
        if d is None or not d.is_active:
            raise ValidationFailed("แผนกไม่ถูกต้อง", fields={"default_department_id": "ไม่ถูกต้อง"})
    for k, v in data.items():
        setattr(r, k, v)
    audit(db, "admin.request_type_updated", actor=admin, entity_type="request_type", entity_id=r.id,
          request=request, details=body.model_dump(mode="json", exclude_unset=True))
    db.commit()
    db.refresh(r)
    return _rt_out(r, db)


def _field_out(f: FormField) -> dict[str, Any]:
    return {k: getattr(f, k) for k in ("key", "section", "field_type", "label_th", "label_en", "placeholder_th",
                                       "placeholder_en", "help_th", "help_en", "required", "sort_order", "options",
                                       "validation", "maps_to")}


@router.get("/request-types/{rt_id}/forms")
def list_forms(rt_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> list[dict]:
    forms = db.scalars(select(FormDefinition).where(FormDefinition.request_type_id == rt_id)
                       .order_by(FormDefinition.version.desc()))
    return [{"id": f.id, "version": f.version, "title_th": f.title_th, "title_en": f.title_en,
             "subject_template": f.subject_template, "is_active": f.is_active, "created_at": f.created_at,
             "fields": [_field_out(x) for x in f.fields]} for f in forms]


class FormVersionIn(BaseModel):
    title_th: str = Field(min_length=1, max_length=200)
    title_en: str = Field(min_length=1, max_length=200)
    subject_template: str = Field(min_length=1, max_length=300)
    fields: list[dict[str, Any]] = Field(min_length=1, max_length=60)


@router.post("/request-types/{rt_id}/forms", status_code=201)
def create_form_version(rt_id: int, body: FormVersionIn, request: Request, admin: User = Depends(require_admin),
                        db: Session = Depends(get_db)) -> dict[str, Any]:
    """Publish a new form version. Existing tickets keep referencing the version they used."""
    rt = db.get(RequestType, rt_id)
    if rt is None:
        raise NotFound("ไม่พบประเภทคำขอ")
    allowed = {"key", "section", "field_type", "label_th", "label_en", "placeholder_th", "placeholder_en", "help_th",
               "help_en", "required", "options", "validation", "maps_to"}
    fields = [{k: v for k, v in fd.items() if k in allowed} for fd in body.fields]
    problems = validate_field_definitions(fields)
    for key in re.findall(r"\{([a-z0-9_]+)\}", body.subject_template):
        if key not in {f.get("key") for f in fields}:
            problems.append(f"subject_template อ้างถึงฟิลด์ '{key}' ที่ไม่มีในแบบฟอร์ม")
    if problems:
        raise ValidationFailed("โครงสร้างแบบฟอร์มไม่ถูกต้อง", extra={"problems": problems})
    latest = db.scalar(select(func.max(FormDefinition.version)).where(FormDefinition.request_type_id == rt_id)) or 0
    for old in db.scalars(select(FormDefinition).where(FormDefinition.request_type_id == rt_id,
                                                       FormDefinition.is_active.is_(True))):
        old.is_active = False
    db.flush()
    form = FormDefinition(request_type_id=rt_id, version=latest + 1, title_th=body.title_th, title_en=body.title_en,
                          subject_template=body.subject_template, is_active=True, created_by_user_id=admin.id)
    db.add(form)
    db.flush()
    for i, fd in enumerate(fields):
        db.add(FormField(form_definition_id=form.id, sort_order=(i + 1) * 10, required=bool(fd.pop("required", False)),
                         **fd))
    audit(db, "admin.form_version_created", actor=admin, entity_type="form_definition", entity_id=form.id,
          request=request, details={"request_type": rt.code, "version": form.version})
    db.commit()
    return {"id": form.id, "version": form.version}


# ============================================================== statuses & workflow


class StatusUpdate(BaseModel):
    name_th: str | None = Field(default=None, min_length=1, max_length=100)
    name_en: str | None = Field(default=None, min_length=1, max_length=100)
    color: str | None = Field(default=None, pattern=r"^[a-z]+$", max_length=20)


@router.get("/workflow")
def get_workflow(admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict[str, Any]:
    return {
        "statuses": [{"code": s.code, "name_th": s.name_th, "name_en": s.name_en, "category": s.category,
                      "is_terminal": s.is_terminal, "color": s.color, "sort_order": s.sort_order}
                     for s in db.scalars(select(TicketStatus).order_by(TicketStatus.sort_order))],
        "transitions": [{"id": t.id, "from_status": t.from_status, "to_status": t.to_status,
                         "allowed_roles": t.allowed_roles, "requires_comment": t.requires_comment,
                         "is_active": t.is_active}
                        for t in db.scalars(select(WorkflowTransition).order_by(WorkflowTransition.from_status,
                                                                                WorkflowTransition.to_status))],
    }


@router.patch("/workflow/statuses/{code}")
def update_status(code: str, body: StatusUpdate, request: Request, admin: User = Depends(require_admin),
                  db: Session = Depends(get_db)) -> dict:
    s = db.get(TicketStatus, code)
    if s is None:
        raise NotFound("ไม่พบสถานะ")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(s, k, v)
    audit(db, "admin.status_updated", actor=admin, entity_type="ticket_status", entity_id=code, request=request,
          details=body.model_dump(mode="json", exclude_unset=True))
    db.commit()
    return {"message": "ok"}


class TransitionIn(BaseModel):
    from_status: str
    to_status: str
    allowed_roles: list[str] = Field(min_length=1)
    requires_comment: bool = False
    is_active: bool = True


class WorkflowIn(BaseModel):
    transitions: list[TransitionIn] = Field(max_length=200)


@router.put("/workflow/transitions")
def replace_transitions(body: WorkflowIn, request: Request, admin: User = Depends(require_admin),
                        db: Session = Depends(get_db)) -> dict:
    codes = set(db.scalars(select(TicketStatus.code)))
    seen: set[tuple[str, str]] = set()
    for t in body.transitions:
        if t.from_status not in codes or t.to_status not in codes or t.from_status == t.to_status:
            raise ValidationFailed(f"Transition {t.from_status} → {t.to_status} ไม่ถูกต้อง")
        if any(r not in ROLES for r in t.allowed_roles):
            raise ValidationFailed("บทบาทไม่ถูกต้อง")
        if (t.from_status, t.to_status) in seen:
            raise ValidationFailed(f"Transition {t.from_status} → {t.to_status} ซ้ำ")
        seen.add((t.from_status, t.to_status))
    db.execute(delete(WorkflowTransition))
    for t in body.transitions:
        db.add(WorkflowTransition(**t.model_dump()))
    audit(db, "admin.workflow_replaced", actor=admin, entity_type="workflow", request=request,
          details={"count": len(body.transitions)})
    db.commit()
    return {"message": "ok", "count": len(body.transitions)}


# ============================================================== assignment rules


class RuleIn(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    sort_order: int = 100
    request_type_id: int | None = None
    category: str | None = Field(default=None, max_length=60)
    customer_type: str | None = None
    priority: str | None = None
    department_id: int
    assigned_user_id: int | None = None
    is_active: bool = True


def _rule_out(r: AssignmentRule) -> dict[str, Any]:
    return {"id": r.id, "name": r.name, "sort_order": r.sort_order, "request_type_id": r.request_type_id,
            "request_type_name": r.request_type.name_th if r.request_type else None, "category": r.category,
            "customer_type": r.customer_type, "priority": r.priority, "department_id": r.department_id,
            "department_name": r.department.name_th, "assigned_user_id": r.assigned_user_id,
            "assigned_user_name": r.assigned_user.full_name if r.assigned_user else None, "is_active": r.is_active}


def _validate_rule(db: Session, body: RuleIn) -> None:
    if body.customer_type and body.customer_type not in CUSTOMER_TYPES:
        raise ValidationFailed("ประเภทลูกค้าไม่ถูกต้อง", fields={"customer_type": "ไม่ถูกต้อง"})
    if body.priority and body.priority not in PRIORITIES:
        raise ValidationFailed("ระดับความสำคัญไม่ถูกต้อง", fields={"priority": "ไม่ถูกต้อง"})
    if db.get(Department, body.department_id) is None:
        raise ValidationFailed("แผนกไม่ถูกต้อง", fields={"department_id": "ไม่ถูกต้อง"})
    if body.request_type_id and db.get(RequestType, body.request_type_id) is None:
        raise ValidationFailed("ประเภทคำขอไม่ถูกต้อง", fields={"request_type_id": "ไม่ถูกต้อง"})
    if body.assigned_user_id:
        u = db.get(User, body.assigned_user_id)
        if u is None or (u.role != "ADMIN" and body.department_id not in u.department_ids):
            raise ValidationFailed("ผู้รับผิดชอบต้องอยู่ในแผนกที่เลือก", fields={"assigned_user_id": "ไม่ถูกต้อง"})


@router.get("/assignment-rules")
def list_rules(admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    return [_rule_out(r) for r in db.scalars(select(AssignmentRule).order_by(AssignmentRule.sort_order,
                                                                             AssignmentRule.id)).unique()]


@router.post("/assignment-rules", status_code=201)
def create_rule(body: RuleIn, request: Request, admin: User = Depends(require_admin),
                db: Session = Depends(get_db)) -> dict[str, Any]:
    _validate_rule(db, body)
    r = AssignmentRule(**body.model_dump())
    db.add(r)
    db.flush()
    audit(db, "admin.assignment_rule_created", actor=admin, entity_type="assignment_rule", entity_id=r.id,
          request=request, details=body.model_dump(mode="json"))
    db.commit()
    db.refresh(r)
    return _rule_out(r)


@router.put("/assignment-rules/{rule_id}")
def update_rule(rule_id: int, body: RuleIn, request: Request, admin: User = Depends(require_admin),
                db: Session = Depends(get_db)) -> dict[str, Any]:
    r = db.get(AssignmentRule, rule_id)
    if r is None:
        raise NotFound("ไม่พบกฎ")
    _validate_rule(db, body)
    for k, v in body.model_dump().items():
        setattr(r, k, v)
    audit(db, "admin.assignment_rule_updated", actor=admin, entity_type="assignment_rule", entity_id=r.id,
          request=request, details=body.model_dump(mode="json"))
    db.commit()
    db.refresh(r)
    return _rule_out(r)


@router.delete("/assignment-rules/{rule_id}")
def delete_rule(rule_id: int, request: Request, admin: User = Depends(require_admin),
                db: Session = Depends(get_db)) -> dict:
    r = db.get(AssignmentRule, rule_id)
    if r is None:
        raise NotFound("ไม่พบกฎ")
    db.delete(r)
    audit(db, "admin.assignment_rule_deleted", actor=admin, entity_type="assignment_rule", entity_id=rule_id,
          request=request)
    db.commit()
    return {"message": "ok"}


# ============================================================== settings


@router.get("/settings")
def list_settings(admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    values = get_settings_map(db)
    return [{"key": k, "value": values[k], "default": d, "description": desc} for k, (d, desc) in DEFAULTS.items()]


class SettingIn(BaseModel):
    value: Any


@router.put("/settings/{key}")
def update_setting(key: str, body: SettingIn, request: Request, admin: User = Depends(require_admin),
                   db: Session = Depends(get_db)) -> dict:
    try:
        set_setting(db, key, body.value, admin.id)
    except ValueError as exc:
        raise ValidationFailed(str(exc), fields={"value": str(exc)}) from None
    audit(db, "admin.setting_updated", actor=admin, entity_type="setting", entity_id=key, request=request,
          details={"value": body.value if not key.startswith("privacy.notice") else "(text updated)"})
    db.commit()
    return {"key": key, "value": body.value}


# ============================================================== logs


@router.get("/audit-logs")
def audit_logs(action: str | None = None, entity_type: str | None = None, entity_id: str | None = None,
               actor_user_id: int | None = None, date_from: date | None = None, date_to: date | None = None,
               page: int = Query(default=1, ge=1), page_size: int = Query(default=50, ge=1, le=200),
               admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict[str, Any]:
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
    if action:
        stmt = stmt.where(AuditLog.action.ilike(f"{action}%"))
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if entity_id:
        stmt = stmt.where(AuditLog.entity_id == entity_id)
    if actor_user_id:
        stmt = stmt.where(AuditLog.actor_user_id == actor_user_id)
    start, end = bangkok_bounds(date_from, date_to)
    if start:
        stmt = stmt.where(AuditLog.created_at >= start)
    if end:
        stmt = stmt.where(AuditLog.created_at < end)
    total, rows = _page(stmt, db, page, page_size)
    names = {u.id: u.full_name for u in db.scalars(select(User)).unique()}
    return {"total": total, "page": page, "page_size": page_size, "items": [
        {"id": a.id, "created_at": a.created_at, "actor_user_id": a.actor_user_id,
         "actor_name": names.get(a.actor_user_id), "actor_type": a.actor_type, "action": a.action,
         "entity_type": a.entity_type, "entity_id": a.entity_id, "ip_address": a.ip_address, "details": a.details}
        for a in rows]}


@router.get("/notification-logs")
def notification_logs(status: str | None = Query(default=None, pattern="^(PENDING|SENDING|SENT|FAILED|SKIPPED)$"),
                      channel: str | None = Query(default=None, pattern="^(EMAIL|LINE|IN_APP)$"),
                      page: int = Query(default=1, ge=1), page_size: int = Query(default=50, ge=1, le=200),
                      admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict[str, Any]:
    stmt = select(TicketNotification).order_by(TicketNotification.created_at.desc(), TicketNotification.id.desc())
    stmt = stmt.where(TicketNotification.channel == channel) if channel else stmt.where(
        TicketNotification.channel != "IN_APP")
    if status:
        stmt = stmt.where(TicketNotification.status == status)
    total, rows = _page(stmt, db, page, page_size)
    numbers = dict(db.execute(select(Ticket.id, Ticket.ticket_number).where(
        Ticket.id.in_({n.ticket_id for n in rows if n.ticket_id} or {-1}))).all()) if total else {}
    # The message body is not returned: customer e-mails may contain tracking links.
    return {"total": total, "page": page, "page_size": page_size, "items": [
        {"id": n.id, "created_at": n.created_at, "ticket_id": n.ticket_id, "ticket_number": numbers.get(n.ticket_id),
         "event_type": n.event_type, "channel": n.channel, "recipient": n.recipient_address,
         "subject": n.subject, "status": n.status, "attempts": n.attempts, "max_attempts": n.max_attempts,
         "next_attempt_at": n.next_attempt_at, "last_error": n.last_error, "sent_at": n.sent_at} for n in rows]}


@router.post("/notification-logs/{notification_id}/retry")
def retry_notification(notification_id: int, request: Request, admin: User = Depends(require_admin),
                       db: Session = Depends(get_db)) -> dict:
    n = db.get(TicketNotification, notification_id)
    if n is None or n.channel == "IN_APP":
        raise NotFound("ไม่พบรายการ")
    if n.status not in ("FAILED", "SKIPPED"):
        raise ValidationFailed("ส่งซ้ำได้เฉพาะรายการที่ล้มเหลวหรือถูกข้าม")
    n.status = "PENDING"
    n.attempts = 0
    n.next_attempt_at = utcnow()
    audit(db, "admin.notification_retry", actor=admin, entity_type="notification", entity_id=n.id, request=request)
    db.commit()
    return {"message": "ok"}


# ============================================================== integrations


@router.get("/integrations")
def integrations(admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict[str, Any]:
    s = get_settings()
    base = s.public_base_url
    rich_menu = [{"code": r.code, "label_th": r.name_th, "label_en": r.name_en, "url": f"{base}/request/{r.slug}",
                  "is_active": r.is_active}
                 for r in db.scalars(select(RequestType).order_by(RequestType.sort_order))]
    return {
        "public_base_url": base,
        "line": {
            "rich_menu_mode": "URL actions (no Messaging API required)",
            "rich_menu": rich_menu,
            "tracking_url": f"{base}/track",
            "liff_login_configured": liff_enabled(),
            "messaging_api_configured": bool(s.line_messaging_channel_access_token),
        },
        "email": {"smtp_configured": smtp_configured(), "from": s.smtp_from},
        "erpnext": {
            "enabled": False,
            "configured": bool(s.erpnext_base_url and s.erpnext_api_key),
            "status": "Not implemented in this version — interfaces and mapping tables only",
            "mappings": db.scalar(select(func.count()).select_from(IntegrationMapping)) or 0,
        },
    }


class MappingIn(BaseModel):
    local_entity_type: str = Field(pattern="^(customer|ticket|request_type)$")
    local_id: str = Field(min_length=1, max_length=64)
    external_doctype: str = Field(min_length=1, max_length=80)
    external_name: str | None = Field(default=None, max_length=140)


@router.get("/integrations/mappings")
def list_mappings(local_entity_type: str | None = None, page: int = Query(default=1, ge=1),
                  page_size: int = Query(default=50, ge=1, le=200), admin: User = Depends(require_admin),
                  db: Session = Depends(get_db)) -> dict[str, Any]:
    stmt = select(IntegrationMapping).order_by(IntegrationMapping.updated_at.desc())
    if local_entity_type:
        stmt = stmt.where(IntegrationMapping.local_entity_type == local_entity_type)
    total, rows = _page(stmt, db, page, page_size)
    return {"total": total, "items": [
        {"id": m.id, "system": m.system, "local_entity_type": m.local_entity_type, "local_id": m.local_id,
         "external_doctype": m.external_doctype, "external_name": m.external_name, "sync_status": m.sync_status,
         "last_synced_at": m.last_synced_at, "last_error": m.last_error, "updated_at": m.updated_at} for m in rows]}


@router.post("/integrations/mappings")
def save_mapping(body: MappingIn, request: Request, admin: User = Depends(require_admin),
                 db: Session = Depends(get_db)) -> dict:
    if body.local_entity_type == "customer" and (not body.local_id.isdigit()
                                                 or db.get(Customer, int(body.local_id)) is None):
        raise ValidationFailed("ไม่พบลูกค้า", fields={"local_id": "ไม่ถูกต้อง"})
    m = upsert_mapping(db, local_entity_type=body.local_entity_type, local_id=body.local_id,
                       external_doctype=body.external_doctype, external_name=body.external_name, user_id=admin.id)
    audit(db, "admin.integration_mapping_saved", actor=admin, entity_type="integration_mapping",
          entity_id=f"{body.local_entity_type}:{body.local_id}", request=request, details=body.model_dump())
    db.commit()
    return {"id": m.id, "sync_status": m.sync_status}


@router.get("/integrations/logs")
def integration_logs(page: int = Query(default=1, ge=1), page_size: int = Query(default=50, ge=1, le=200),
                     admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict[str, Any]:
    total, rows = _page(select(IntegrationLog).order_by(IntegrationLog.created_at.desc()), db, page, page_size)
    return {"total": total, "items": [
        {"id": r.id, "created_at": r.created_at, "system": r.system, "direction": r.direction,
         "operation": r.operation, "local_entity_type": r.local_entity_type, "local_id": r.local_id,
         "external_doctype": r.external_doctype, "external_name": r.external_name, "status": r.status,
         "attempts": r.attempts, "error": r.error} for r in rows]}


# ============================================================== customers


class CustomerUpdate(BaseModel):
    code: str | None = Field(default=None, max_length=50)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    customer_type: str | None = None
    tax_id: str | None = Field(default=None, max_length=20)
    address: str | None = Field(default=None, max_length=2000)
    notes: str | None = Field(default=None, max_length=5000)
    is_active: bool | None = None


@router.get("/customers")
def list_customers(q: str | None = None, page: int = Query(default=1, ge=1),
                   page_size: int = Query(default=50, ge=1, le=200), admin: User = Depends(require_admin),
                   db: Session = Depends(get_db)) -> dict[str, Any]:
    stmt = select(Customer).order_by(Customer.name)
    if q:
        stmt = stmt.where(or_(Customer.name.ilike(f"%{q[:100]}%"), Customer.code.ilike(f"%{q[:100]}%")))
    total, rows = _page(stmt, db, page, page_size)
    rows = list(rows)
    ids = [c.id for c in rows] or [-1]
    counts = dict(db.execute(select(Ticket.customer_id, func.count()).where(Ticket.customer_id.in_(ids))
                             .group_by(Ticket.customer_id)).all())
    erp = dict(db.execute(select(IntegrationMapping.local_id, IntegrationMapping.external_name).where(
        IntegrationMapping.local_entity_type == "customer", IntegrationMapping.external_doctype == "Customer",
        IntegrationMapping.local_id.in_([str(i) for i in ids]))).all())
    return {"total": total, "items": [
        {"id": c.id, "code": c.code, "name": c.name, "customer_type": c.customer_type, "tax_id": c.tax_id,
         "address": c.address, "notes": c.notes, "is_active": c.is_active, "ticket_count": counts.get(c.id, 0),
         "erpnext_customer": erp.get(str(c.id)), "created_at": c.created_at} for c in rows]}


@router.get("/customers/{customer_id}/contacts")
def customer_contacts(customer_id: int, admin: User = Depends(require_admin),
                      db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    return [{"id": c.id, "name": c.name, "department": c.department, "phone": c.phone, "email": c.email,
             "line_verified": bool(c.line_user_id), "anonymized_at": c.anonymized_at, "created_at": c.created_at}
            for c in db.scalars(select(CustomerContact).where(CustomerContact.customer_id == customer_id)
                                .order_by(CustomerContact.name))]


@router.patch("/customers/{customer_id}")
def update_customer(customer_id: int, body: CustomerUpdate, request: Request, admin: User = Depends(require_admin),
                    db: Session = Depends(get_db)) -> dict:
    from app.services.customers import normalize_name

    c = db.get(Customer, customer_id)
    if c is None:
        raise NotFound("ไม่พบลูกค้า")
    data = body.model_dump(exclude_unset=True)
    if "customer_type" in data and data["customer_type"] not in CUSTOMER_TYPES:
        raise ValidationFailed("ประเภทลูกค้าไม่ถูกต้อง", fields={"customer_type": "ไม่ถูกต้อง"})
    if "name" in data:
        c.normalized_name = normalize_name(data["name"])
    for k, v in data.items():
        setattr(c, k, v or None if k in ("code", "tax_id") else v)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise Conflict("ชื่อหรือรหัสลูกค้านี้มีอยู่แล้ว") from None
    audit(db, "admin.customer_updated", actor=admin, entity_type="customer", entity_id=c.id, request=request,
          details=body.model_dump(mode="json", exclude_unset=True))
    db.commit()
    return {"message": "ok"}
