"""Public (customer) API: portal configuration, forms, submission and tracking.

No authentication; protected by rate limits, a honeypot field, strict validation
and (for tracking) ticket number + secret tracking token.
"""
from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Request, Response, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.integrations.line.liff import liff_enabled
from app.models import RequestType
from app.security.rate_limit import client_ip, enforce
from app.services import tracking
from app.services.errors import ValidationFailed
from app.services.form_engine import file_rules, get_active_form_by_slug
from app.services.notifications import tracking_url
from app.services.settings_service import PUBLIC_KEYS, get_setting, get_settings_map
from app.services.ticket_service import customer_reply, submit_request

router = APIRouter(prefix="/public", tags=["public"])

TRACK_FAILED = HTTPException(status.HTTP_404_NOT_FOUND, detail={
    "code": "TRACKING_NOT_FOUND",
    "message": "ไม่พบข้อมูล กรุณาตรวจสอบเลขที่ Ticket และลิงก์ติดตามสถานะอีกครั้ง"})


@router.get("/portal")
def portal(db: Session = Depends(get_db)) -> dict[str, Any]:
    cfg = get_settings_map(db, PUBLIC_KEYS)
    types = db.scalars(select(RequestType).where(RequestType.is_active.is_(True)).order_by(RequestType.sort_order))
    return {
        "settings": cfg,
        "liff_enabled": liff_enabled() and bool(cfg.get("line.liff_id")),
        "request_types": [
            {"code": t.code, "slug": t.slug, "name_th": t.name_th, "name_en": t.name_en,
             "description_th": t.description_th, "description_en": t.description_en, "icon": t.icon}
            for t in types
        ],
    }


@router.get("/privacy-notice")
def privacy_notice(db: Session = Depends(get_db)) -> dict[str, Any]:
    return {
        "version": get_setting(db, "privacy.notice_version"),
        "text_th": get_setting(db, "privacy.notice_th"),
        "text_en": get_setting(db, "privacy.notice_en"),
    }


@router.get("/forms/{slug}")
def get_form(slug: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    form = get_active_form_by_slug(db, slug)
    _, rules = file_rules(form)
    rt = form.request_type
    return {
        "id": form.id,
        "version": form.version,
        "title_th": form.title_th,
        "title_en": form.title_en,
        "request_type": {"code": rt.code, "slug": rt.slug, "name_th": rt.name_th, "name_en": rt.name_en,
                         "icon": rt.icon},
        "file_rules": {"max_files": rules.max_files, "max_size_mb": rules.max_size_mb, "accept": list(rules.accept)},
        "fields": [
            {
                "key": f.key, "section": f.section, "field_type": f.field_type, "label_th": f.label_th,
                "label_en": f.label_en, "placeholder_th": f.placeholder_th, "placeholder_en": f.placeholder_en,
                "help_th": f.help_th, "help_en": f.help_en, "required": f.required, "options": f.options,
                "validation": f.validation, "maps_to": f.maps_to,
            }
            for f in form.fields
        ],
    }


def _parse_payload(payload: str) -> dict[str, Any]:
    try:
        data = json.loads(payload)
    except ValueError:
        raise ValidationFailed("ข้อมูลที่ส่งไม่ถูกต้อง") from None
    if not isinstance(data, dict):
        raise ValidationFailed("ข้อมูลที่ส่งไม่ถูกต้อง")
    return data


@router.post("/requests/{slug}", status_code=status.HTTP_201_CREATED)
def create_request(
    slug: str,
    request: Request,
    response: Response,
    payload: str = Form(..., max_length=200_000, description="JSON: {form_definition_id, values, privacy_consent}"),
    files: list[UploadFile] = File(default=[]),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Submit a customer request. Creates a ticket atomically together with its attachments."""
    enforce(request, "submit", get_settings().rate_limit_submit_per_hour, 3600)
    data = _parse_payload(payload)
    if data.get("website"):  # honeypot field: invisible to humans, filled by bots
        raise ValidationFailed("ไม่สามารถส่งคำขอได้", code="SPAM_DETECTED")
    form_id = data.get("form_definition_id")
    result = submit_request(
        db,
        slug=slug,
        form_definition_id=int(form_id) if isinstance(form_id, (int, str)) and str(form_id).isdigit() else None,
        values=data.get("values") or {},
        privacy_consent=data.get("privacy_consent") is True,
        uploads=files,
        idempotency_key=idempotency_key,
        client_ip=client_ip(request),
        line_id_token=data.get("line_id_token") if isinstance(data.get("line_id_token"), str) else None,
        request=request,
    )
    if result.replayed:
        response.status_code = status.HTTP_200_OK
    t = result.ticket
    return {
        "ticket_number": t.ticket_number,
        "request_type_code": t.request_type.code,
        "request_type_name_th": t.request_type.name_th,
        "request_type_name_en": t.request_type.name_en,
        "subject": t.subject,
        "created_at": t.created_at,
        "tracking_token": result.tracking_token,
        "tracking_url": tracking_url(t.ticket_number, result.tracking_token) if result.tracking_token else None,
        "attachments": len(t.attachments),
        "replayed": result.replayed,
    }


class TrackIn(BaseModel):
    ticket_number: str = Field(min_length=5, max_length=30)
    token: str = Field(min_length=10, max_length=128)


@router.post("/track")
def track(body: TrackIn, request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    enforce(request, "track", get_settings().rate_limit_track_per_minute, 60)
    ticket = tracking.authenticate(db, body.ticket_number, body.token)
    if ticket is None:
        raise TRACK_FAILED
    view = tracking.public_view(db, ticket)
    db.commit()  # persists last_used_at
    return view


@router.post("/track/reply")
def track_reply(
    request: Request,
    payload: str = Form(..., max_length=20_000, description="JSON: {ticket_number, token, message}"),
    files: list[UploadFile] = File(default=[]),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Customer sends additional information for their ticket."""
    enforce(request, "track", get_settings().rate_limit_track_per_minute, 60)
    enforce(request, "submit", get_settings().rate_limit_submit_per_hour, 3600)
    data = _parse_payload(payload)
    ticket = tracking.authenticate(db, str(data.get("ticket_number") or ""), str(data.get("token") or ""))
    if ticket is None:
        raise TRACK_FAILED
    customer_reply(db, ticket, str(data.get("message") or ""), files, request=request)
    return tracking.public_view(db, ticket)
