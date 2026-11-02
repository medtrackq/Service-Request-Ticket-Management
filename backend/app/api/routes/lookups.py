"""Reference lists for staff screens (filters, assignment dropdowns)."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.db import get_db
from app.models import Department, RequestType, TicketStatus, User
from app.models.customers import CUSTOMER_TYPES
from app.models.workflow import PRIORITIES

router = APIRouter(tags=["lookups"])


@router.get("/lookups")
def lookups(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    departments = db.scalars(select(Department).order_by(Department.sort_order, Department.id))
    users = db.scalars(select(User).where(User.is_active.is_(True)).order_by(User.full_name)).unique()
    return {
        "departments": [{"id": d.id, "code": d.code, "name_th": d.name_th, "name_en": d.name_en,
                         "is_active": d.is_active} for d in departments],
        "request_types": [{"id": r.id, "code": r.code, "slug": r.slug, "name_th": r.name_th, "name_en": r.name_en}
                          for r in db.scalars(select(RequestType).order_by(RequestType.sort_order))],
        "statuses": [{"code": s.code, "name_th": s.name_th, "name_en": s.name_en, "category": s.category,
                      "color": s.color, "is_terminal": s.is_terminal}
                     for s in db.scalars(select(TicketStatus).where(TicketStatus.is_active.is_(True))
                                         .order_by(TicketStatus.sort_order))],
        "priorities": list(PRIORITIES),
        "customer_types": list(CUSTOMER_TYPES),
        # Minimal staff directory for assignment: no contact details.
        "users": [{"id": u.id, "full_name": u.full_name, "role": u.role, "department_ids": u.department_ids}
                  for u in users],
    }
