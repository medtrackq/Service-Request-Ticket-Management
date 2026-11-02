"""Typed access to runtime-configurable settings stored in `system_settings`.

Every key has a default here, so the application works on an empty settings table.
Administrators override values through the admin API/UI.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import SystemSetting, utcnow

PRIVACY_NOTICE_TH = """บริษัท บางกอกยูนิเทรด จำกัด ("บริษัท") เก็บรวบรวม ใช้ และเปิดเผยข้อมูลส่วนบุคคลที่ท่านให้ไว้ในแบบฟอร์มนี้ \
ได้แก่ ชื่อผู้ติดต่อ หน่วยงาน แผนก หมายเลขโทรศัพท์ อีเมล และไฟล์แนบ เพื่อวัตถุประสงค์ในการรับเรื่อง ตรวจสอบ \
ดำเนินการตามคำขอ ติดต่อกลับ และติดตามสถานะการให้บริการ ตามฐานการปฏิบัติตามสัญญาและประโยชน์โดยชอบด้วยกฎหมาย \
ตามพระราชบัญญัติคุ้มครองข้อมูลส่วนบุคคล พ.ศ. 2562

ข้อมูลจะถูกเข้าถึงเฉพาะเจ้าหน้าที่ที่ได้รับมอบหมาย และจัดเก็บตามระยะเวลาที่บริษัทกำหนดในนโยบายการเก็บรักษาข้อมูล \
ท่านมีสิทธิขอเข้าถึง แก้ไข ลบ หรือคัดค้านการประมวลผลข้อมูลส่วนบุคคลของท่าน โดยติดต่อเจ้าหน้าที่คุ้มครองข้อมูลส่วนบุคคลของบริษัท

(ข้อความนี้เป็นค่าเริ่มต้น ผู้ดูแลระบบต้องตรวจสอบและแก้ไขให้ตรงกับนโยบายความเป็นส่วนตัวของบริษัทก่อนใช้งานจริง)"""

PRIVACY_NOTICE_EN = """The Bangkok Unitrade Co., Ltd. ("the Company") collects, uses and discloses the personal data you \
provide in this form (contact name, organisation, department, telephone, e-mail and attachments) to receive, review \
and fulfil your request, contact you and report its status, on the basis of contract performance and legitimate \
interest under the Thai Personal Data Protection Act B.E. 2562 (2019).

Data is accessible only to assigned staff and retained according to the Company's retention policy. You may request \
access, correction, deletion or object to processing by contacting the Company's data protection officer.

(Default text — the administrator must review it against the Company's privacy policy before go-live.)"""

# key -> (default value, description)
DEFAULTS: dict[str, tuple[Any, str]] = {
    "portal.company_name_th": ("บริษัท บางกอกยูนิเทรด จำกัด", "ชื่อบริษัทที่แสดงบนพอร์ทัลลูกค้า"),
    "portal.company_name_en": ("The Bangkok Unitrade Co., Ltd.", "Company name shown on the customer portal"),
    "portal.welcome_th": (
        "ยินดีต้อนรับสู่ระบบบริการลูกค้า บริษัท บางกอกยูนิเทรด จำกัด",
        "ข้อความต้อนรับ (ภาษาไทย)",
    ),
    "portal.welcome_en": (
        "Welcome to the customer service system of The Bangkok Unitrade Co., Ltd.",
        "Welcome message (English)",
    ),
    "portal.contact_phone": ("", "เบอร์โทรศัพท์ติดต่อที่แสดงบนพอร์ทัล (ว่าง = ไม่แสดง)"),
    "portal.contact_email": ("", "อีเมลติดต่อที่แสดงบนพอร์ทัล (ว่าง = ไม่แสดง)"),
    "privacy.notice_version": ("1.0", "เวอร์ชันประกาศความเป็นส่วนตัว (บันทึกพร้อมความยินยอมในแต่ละ Ticket)"),
    "privacy.notice_th": (PRIVACY_NOTICE_TH, "ประกาศความเป็นส่วนตัว (ภาษาไทย)"),
    "privacy.notice_en": (PRIVACY_NOTICE_EN, "Privacy notice (English)"),
    "privacy.retention_days": (
        0,
        "จำนวนวันหลังปิดงาน/ยกเลิกที่จะลบข้อมูลส่วนบุคคลและไฟล์แนบของ Ticket (0 = ปิดใช้งาน)",
    ),
    "audit.retention_days": (0, "จำนวนวันที่เก็บ Audit Log (0 = เก็บไม่จำกัด)"),
    "assignment.auto_enabled": (False, "เปิดใช้การมอบหมายงานอัตโนมัติตาม Assignment Rules"),
    "access.staff_see_department_queue": (
        True,
        "Staff เห็น Ticket ทั้งหมดในแผนกของตน (ปิด = เห็นเฉพาะ Ticket ที่ได้รับมอบหมาย)",
    ),
    "service_targets": (
        {
            "URGENT": {"first_response_hours": 2, "resolution_hours": 24},
            "HIGH": {"first_response_hours": 4, "resolution_hours": 72},
            "NORMAL": {"first_response_hours": 8, "resolution_hours": 120},
            "LOW": {"first_response_hours": 24, "resolution_hours": 240},
        },
        "เป้าหมายการให้บริการภายใน (ชั่วโมง) ตามระดับความสำคัญ ใช้คำนวณกำหนดเสร็จและงานเกินกำหนด "
        "— เป็นค่าตัวอย่าง ไม่ใช่ SLA ตามสัญญา ต้องกำหนดตามนโยบายบริษัทก่อนใช้งานจริง",
    ),
    "notifications.email_enabled": (True, "ส่งอีเมลแจ้งเตือนเจ้าหน้าที่ (ต้องตั้งค่า SMTP)"),
    "notifications.customer_email_enabled": (True, "ส่งอีเมลแจ้งลูกค้าเมื่อสร้าง Ticket / เปลี่ยนสถานะ"),
    "notifications.overdue_enabled": (True, "แจ้งเตือนเมื่อ Ticket เกินกำหนด"),
    "notifications.line_enabled": (
        False,
        "ส่งแจ้งเตือนลูกค้าทาง LINE Messaging API (ต้องตั้งค่า Channel Access Token และลูกค้าต้องยืนยันตัวตนผ่าน LIFF)",
    ),
    "tracking.token_expiry_days": (0, "อายุของลิงก์ติดตามสถานะ (วัน, 0 = ไม่หมดอายุ)"),
    "line.liff_id": ("", "LIFF ID (ใช้เมื่อเปิดใช้ LINE Login/LIFF เพื่อยืนยันตัวตนลูกค้า)"),
}

PUBLIC_KEYS = (
    "portal.company_name_th",
    "portal.company_name_en",
    "portal.welcome_th",
    "portal.welcome_en",
    "portal.contact_phone",
    "portal.contact_email",
    "privacy.notice_version",
    "line.liff_id",
)


def get_setting(db: Session, key: str) -> Any:
    row = db.get(SystemSetting, key)
    if row is not None:
        return row.value
    if key in DEFAULTS:
        return DEFAULTS[key][0]
    raise KeyError(key)


def get_settings_map(db: Session, keys: tuple[str, ...] | None = None) -> dict[str, Any]:
    keys = keys or tuple(DEFAULTS)
    rows = {r.key: r.value for r in db.scalars(select(SystemSetting).where(SystemSetting.key.in_(keys)))}
    return {k: rows.get(k, DEFAULTS[k][0]) for k in keys}


def validate_setting(key: str, value: Any) -> Any:
    if key not in DEFAULTS:
        raise ValueError("ไม่รู้จักการตั้งค่านี้")
    default = DEFAULTS[key][0]
    if isinstance(default, bool):
        if not isinstance(value, bool):
            raise ValueError("ต้องเป็นค่า true/false")
    elif isinstance(default, int):
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError("ต้องเป็นจำนวนเต็มที่ไม่ติดลบ")
    elif isinstance(default, str):
        if not isinstance(value, str) or len(value) > 20000:
            raise ValueError("ต้องเป็นข้อความ")
    elif key == "service_targets":
        if not isinstance(value, dict):
            raise ValueError("รูปแบบไม่ถูกต้อง")
        for prio in ("LOW", "NORMAL", "HIGH", "URGENT"):
            item = value.get(prio)
            if not isinstance(item, dict):
                raise ValueError(f"ต้องระบุเป้าหมายสำหรับ {prio}")
            for f in ("first_response_hours", "resolution_hours"):
                v = item.get(f)
                if v is not None and (not isinstance(v, (int, float)) or v <= 0):
                    raise ValueError(f"{prio}.{f} ต้องเป็นตัวเลขมากกว่า 0 หรือ null")
    return value


def set_setting(db: Session, key: str, value: Any, user_id: int | None) -> SystemSetting:
    value = validate_setting(key, value)
    row = db.get(SystemSetting, key)
    if row is None:
        row = SystemSetting(key=key, value=value, description=DEFAULTS[key][1], updated_by_user_id=user_id)
        db.add(row)
    else:
        row.value = value
        row.updated_by_user_id = user_id
        row.updated_at = utcnow()
    return row


def service_target_hours(db: Session, priority: str, kind: str) -> float | None:
    targets = get_setting(db, "service_targets") or {}
    item = targets.get(priority) or {}
    value = item.get(kind)
    return float(value) if value else None
