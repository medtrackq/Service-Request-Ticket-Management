"""Configurable form engine: loads versioned form definitions and validates submissions.

Validation here is authoritative; the frontend mirrors these rules for UX only.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from email_validator import EmailNotValidError, validate_email
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import FormDefinition, FormField, RequestType
from app.models.forms import FIELD_MAPPINGS, FIELD_TYPES
from app.services.errors import NotFound, ValidationFailed

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_PHONE_ALLOWED = re.compile(r"^[0-9+\-()\s.,#/a-zA-Zก-๙]*$")
DEFAULT_TEXT_MAX = 255
DEFAULT_TEXTAREA_MAX = 5000

IMAGE_MIME = ("image/jpeg", "image/png")
DOCUMENT_MIME = ("application/pdf",)


@dataclass
class FileRules:
    max_files: int = 5
    max_size_mb: int = 10
    accept: tuple[str, ...] = IMAGE_MIME


@dataclass
class CleanedSubmission:
    form: FormDefinition
    values: dict[str, Any] = field(default_factory=dict)
    mapped: dict[str, Any] = field(default_factory=dict)

    def display_value(self, f: FormField, lang: str = "th") -> str | None:
        v = self.values.get(f.key)
        if v is None:
            return None
        if f.field_type == "select":
            return f.option_label(v, lang)
        return str(v)


def get_active_form_by_slug(db: Session, slug: str) -> FormDefinition:
    form = db.scalar(
        select(FormDefinition)
        .join(RequestType)
        .where(RequestType.slug == slug, RequestType.is_active.is_(True), FormDefinition.is_active.is_(True))
    )
    if form is None:
        raise NotFound("ไม่พบแบบฟอร์มที่ต้องการ", code="FORM_NOT_FOUND")
    return form


def file_rules(form: FormDefinition) -> tuple[FormField | None, FileRules]:
    for f in form.fields:
        if f.field_type == "file":
            v = f.validation or {}
            return f, FileRules(
                max_files=int(v.get("max_files", 5)),
                max_size_mb=int(v.get("max_size_mb", get_settings().max_upload_mb)),
                accept=tuple(v.get("accept", IMAGE_MIME)),
            )
    return None, FileRules(max_files=0)


def _clean_text(value: Any, multiline: bool) -> str:
    if not isinstance(value, (str, int, float)):
        raise ValueError("รูปแบบข้อมูลไม่ถูกต้อง")
    text = _CONTROL_CHARS.sub("", str(value)).replace("\r\n", "\n").strip()
    if not multiline:
        text = re.sub(r"\s+", " ", text)
    return text


def _today_bangkok() -> date:
    return datetime.now(ZoneInfo(get_settings().timezone)).date()


def _validate_value(f: FormField, raw: Any) -> Any:
    """Return the cleaned value (None when empty) or raise ValueError with a Thai message."""
    rules = f.validation or {}
    if raw is None or (isinstance(raw, str) and raw.strip() == ""):
        return None

    if f.field_type in ("text", "textarea"):
        text = _clean_text(raw, multiline=f.field_type == "textarea")
        if not text:
            return None
        max_len = int(rules.get("max_length", DEFAULT_TEXTAREA_MAX if f.field_type == "textarea" else DEFAULT_TEXT_MAX))
        if len(text) > max_len:
            raise ValueError(f"ความยาวต้องไม่เกิน {max_len} ตัวอักษร")
        min_len = int(rules.get("min_length", 0))
        if len(text) < min_len:
            raise ValueError(f"กรุณากรอกอย่างน้อย {min_len} ตัวอักษร")
        pattern = rules.get("pattern")
        if pattern and not re.fullmatch(pattern, text):
            raise ValueError(rules.get("pattern_message_th", "รูปแบบข้อมูลไม่ถูกต้อง"))
        return text

    if f.field_type == "email":
        text = _clean_text(raw, multiline=False)
        try:
            return validate_email(text, check_deliverability=False).normalized
        except EmailNotValidError:
            raise ValueError("รูปแบบอีเมลไม่ถูกต้อง") from None

    if f.field_type == "tel":
        text = _clean_text(raw, multiline=False)
        digits = re.sub(r"\D", "", text)
        if len(text) > 30 or not _PHONE_ALLOWED.match(text) or not 9 <= len(digits) <= 20:
            raise ValueError("รูปแบบเบอร์โทรศัพท์ไม่ถูกต้อง")
        return text

    if f.field_type == "number":
        try:
            num = float(str(raw).replace(",", "").strip())
        except ValueError:
            raise ValueError("ต้องเป็นตัวเลข") from None
        if num != num or num in (float("inf"), float("-inf")):
            raise ValueError("ต้องเป็นตัวเลข")
        if rules.get("integer", True):
            if not num.is_integer():
                raise ValueError("ต้องเป็นจำนวนเต็ม")
            num = int(num)
        if "min" in rules and num < rules["min"]:
            raise ValueError(f"ต้องไม่น้อยกว่า {rules['min']}")
        if "max" in rules and num > rules["max"]:
            raise ValueError(f"ต้องไม่เกิน {rules['max']}")
        return num

    if f.field_type == "date":
        try:
            d = date.fromisoformat(str(raw).strip()[:10])
        except ValueError:
            raise ValueError("รูปแบบวันที่ไม่ถูกต้อง") from None
        if d.year < 2000 or d.year > 2100:
            raise ValueError("วันที่ไม่ถูกต้อง")
        if rules.get("not_future") and d > _today_bangkok():
            raise ValueError("วันที่ต้องไม่เป็นวันในอนาคต")
        if rules.get("not_past") and d < _today_bangkok():
            raise ValueError("วันที่ต้องไม่เป็นวันที่ผ่านมาแล้ว")
        return d.isoformat()

    if f.field_type == "select":
        value = str(raw).strip()
        allowed = {o.get("value") for o in (f.options or [])}
        if value not in allowed:
            raise ValueError("กรุณาเลือกจากรายการที่กำหนด")
        return value

    raise ValueError("ประเภทฟิลด์ไม่รองรับ")


def validate_submission(form: FormDefinition, raw_values: dict[str, Any]) -> CleanedSubmission:
    if not isinstance(raw_values, dict):
        raise ValidationFailed("ข้อมูลแบบฟอร์มไม่ถูกต้อง")
    errors: dict[str, str] = {}
    cleaned = CleanedSubmission(form=form)
    for f in form.fields:
        if f.field_type == "file":
            continue  # files are validated separately (services/files.py)
        try:
            value = _validate_value(f, raw_values.get(f.key))
        except ValueError as exc:
            errors[f.key] = str(exc)
            continue
        if value is None and f.required:
            errors[f.key] = "กรุณากรอกข้อมูลนี้" if f.field_type != "select" else "กรุณาเลือกข้อมูลนี้"
            continue
        cleaned.values[f.key] = value
        if f.maps_to and value is not None:
            cleaned.mapped[f.maps_to] = value
    if errors:
        raise ValidationFailed("กรุณาตรวจสอบข้อมูลในแบบฟอร์ม", fields=errors)
    return cleaned


def render_subject(form: FormDefinition, cleaned: CleanedSubmission) -> str:
    """Fill `{field_key}` placeholders in the form's subject template."""
    by_key = {f.key: f for f in form.fields}

    def repl(m: re.Match[str]) -> str:
        f = by_key.get(m.group(1))
        if f is None:
            return ""
        return cleaned.display_value(f) or ""

    subject = re.sub(r"\{([a-z0-9_]+)\}", repl, form.subject_template)
    subject = re.sub(r"\s+", " ", subject).strip(" -:")
    return (subject or form.request_type.name_th)[:300]


def validate_field_definitions(fields: list[dict[str, Any]]) -> list[str]:
    """Validate admin-supplied field definitions for a new form version."""
    problems: list[str] = []
    keys: set[str] = set()
    file_fields = 0
    required_maps = {"customer.name", "contact.name", "contact.phone", "ticket.description"}
    seen_maps: set[str] = set()
    for i, fd in enumerate(fields):
        key = fd.get("key", "")
        if not re.fullmatch(r"[a-z][a-z0-9_]{1,59}", key or ""):
            problems.append(f"field[{i}]: key ต้องเป็นตัวพิมพ์เล็ก a-z, 0-9, _")
        if key in keys:
            problems.append(f"field[{i}]: key '{key}' ซ้ำ")
        keys.add(key)
        if fd.get("field_type") not in FIELD_TYPES:
            problems.append(f"field[{i}]: field_type ไม่รองรับ")
        if fd.get("section") not in ("customer", "request", "attachments"):
            problems.append(f"field[{i}]: section ต้องเป็น customer, request หรือ attachments")
        if not fd.get("label_th") or not fd.get("label_en"):
            problems.append(f"field[{i}]: ต้องมี label_th และ label_en")
        if fd.get("field_type") == "select" and not fd.get("options"):
            problems.append(f"field[{i}]: select ต้องมี options")
        if fd.get("field_type") == "file":
            file_fields += 1
            accept = (fd.get("validation") or {}).get("accept", [])
            if any(a not in IMAGE_MIME + DOCUMENT_MIME for a in accept):
                problems.append(f"field[{i}]: accept รองรับเฉพาะ {', '.join(IMAGE_MIME + DOCUMENT_MIME)}")
            max_files = (fd.get("validation") or {}).get("max_files", 5)
            if not isinstance(max_files, int) or not 1 <= max_files <= 10:
                problems.append(f"field[{i}]: max_files ต้องอยู่ระหว่าง 1-10")
        mt = fd.get("maps_to")
        if mt:
            if mt not in FIELD_MAPPINGS:
                problems.append(f"field[{i}]: maps_to '{mt}' ไม่รองรับ")
            if mt in seen_maps:
                problems.append(f"field[{i}]: maps_to '{mt}' ซ้ำ")
            seen_maps.add(mt)
    if file_fields > 1:
        problems.append("แบบฟอร์มมีฟิลด์ไฟล์แนบได้ไม่เกิน 1 ฟิลด์")
    missing = required_maps - seen_maps
    if missing:
        problems.append("ต้องมีฟิลด์ที่ maps_to: " + ", ".join(sorted(missing)))
    return problems
