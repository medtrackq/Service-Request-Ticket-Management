"""Reference data: departments, request types, the six request forms, statuses, workflow.

`seed_reference_data` is idempotent: it only inserts rows that do not exist yet,
so administrator changes are never overwritten when the seed runs again
(e.g. on every container start).
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Department, FormDefinition, FormField, RequestType, TicketStatus, WorkflowTransition

DEPARTMENTS = [
    ("SALES", "ฝ่ายขาย", "Sales", 1),
    ("LOGISTICS", "ฝ่ายโลจิสติกส์", "Logistics", 2),
    ("SERVICE", "ฝ่ายบริการ / ซ่อมบำรุง", "Service", 3),
    ("ACCOUNTING", "ฝ่ายบัญชี", "Accounting", 4),
    ("CS", "ฝ่ายบริการลูกค้า", "Customer Service", 5),
]

# code, slug, prefix, name_th, name_en, desc_th, desc_en, icon, department, sort
REQUEST_TYPES = [
    ("PRODUCT", "product", "PRD", "สอบถามผลิตภัณฑ์", "Product Inquiry",
     "สอบถามข้อมูลสินค้า รุ่น คุณสมบัติ และความพร้อมของสินค้า",
     "Ask about products, models, specifications and availability", "product", "SALES", 1),
    ("DELIVERY", "delivery", "DLV", "ติดตามการจัดส่ง", "Delivery Tracking",
     "ติดตามสถานะการจัดส่งสินค้าตามใบสั่งซื้อ", "Track deliveries for your purchase orders", "truck",
     "LOGISTICS", 2),
    ("SERVICE", "service", "SRV", "แจ้งซ่อม / บริการ", "Service Request",
     "แจ้งซ่อม ตรวจเช็ค หรือบำรุงรักษาเครื่องมือแพทย์", "Repair, inspection or maintenance of equipment",
     "wrench", "SERVICE", 3),
    ("QUOTATION", "quotation", "QUO", "ขอใบเสนอราคา", "Quotation Request",
     "ขอใบเสนอราคาสินค้าและบริการ", "Request a quotation for products or services", "document", "SALES", 4),
    ("ACCOUNTING", "accounting", "ACC", "ติดต่อฝ่ายบัญชี", "Accounting Inquiry",
     "สอบถามใบแจ้งหนี้ ใบเสร็จ การชำระเงิน และเอกสารบัญชี",
     "Invoices, receipts, payments and accounting documents", "calculator", "ACCOUNTING", 5),
    ("GENERAL", "general", "GEN", "ติดต่อเจ้าหน้าที่", "General Contact",
     "ติดต่อเจ้าหน้าที่ในเรื่องอื่น ๆ", "Contact our staff about anything else", "chat", "CS", 6),
]

STATUSES = [
    ("NEW", "รับเรื่องใหม่", "New", "NEW", False, 1, "blue"),
    ("REVIEW", "กำลังตรวจสอบ", "Under Review", "OPEN", False, 2, "indigo"),
    ("ASSIGNED", "มอบหมายงานแล้ว", "Assigned", "OPEN", False, 3, "violet"),
    ("IN_PROGRESS", "กำลังดำเนินการ", "In Progress", "OPEN", False, 4, "amber"),
    ("WAITING_CUSTOMER", "รอข้อมูลลูกค้า", "Waiting for Customer", "WAITING", False, 5, "orange"),
    ("WAITING_INTERNAL", "รอหน่วยงานภายใน", "Waiting Internal", "WAITING", False, 6, "yellow"),
    ("RESOLVED", "ดำเนินการเสร็จสิ้น", "Resolved", "RESOLVED", False, 7, "green"),
    ("CLOSED", "ปิดงาน", "Closed", "CLOSED", True, 8, "slate"),
    ("CANCELLED", "ยกเลิก", "Cancelled", "CANCELLED", True, 9, "red"),
]

ALL = ["ADMIN", "MANAGER", "STAFF"]
MGR = ["ADMIN", "MANAGER"]
OPEN_STATES = ["NEW", "REVIEW", "ASSIGNED", "IN_PROGRESS", "WAITING_CUSTOMER", "WAITING_INTERNAL"]

# (from, to, roles, requires_comment). Tickets do not have to pass through every status.
TRANSITIONS: list[tuple[str, str, list[str], bool]] = []
for _src in OPEN_STATES:
    for _dst in ["REVIEW", "ASSIGNED", "IN_PROGRESS", "WAITING_CUSTOMER", "WAITING_INTERNAL", "RESOLVED"]:
        if _src == _dst or (_dst in ("REVIEW", "ASSIGNED") and _src not in ("NEW", "REVIEW", "ASSIGNED")):
            continue
        TRANSITIONS.append((_src, _dst, ALL, False))
    TRANSITIONS.append((_src, "CANCELLED", MGR, True))
    TRANSITIONS.append((_src, "CLOSED", MGR, True))
TRANSITIONS += [
    ("RESOLVED", "CLOSED", ALL, False),
    ("RESOLVED", "IN_PROGRESS", ALL, True),  # reopen
    ("CLOSED", "IN_PROGRESS", MGR, True),  # reopen a closed ticket
    ("CANCELLED", "REVIEW", ["ADMIN"], True),  # restore a cancelled ticket
]


def _opt(*pairs: tuple[str, str, str]) -> list[dict[str, str]]:
    return [{"value": v, "label_th": th, "label_en": en} for v, th, en in pairs]


def _f(key: str, section: str, field_type: str, label_th: str, label_en: str, *, required: bool = False,
       maps_to: str | None = None, options: list[dict[str, str]] | None = None,
       validation: dict[str, Any] | None = None, placeholder_th: str | None = None,
       placeholder_en: str | None = None, help_th: str | None = None, help_en: str | None = None) -> dict:
    return {
        "key": key, "section": section, "field_type": field_type, "label_th": label_th, "label_en": label_en,
        "required": required, "maps_to": maps_to, "options": options, "validation": validation,
        "placeholder_th": placeholder_th, "placeholder_en": placeholder_en, "help_th": help_th, "help_en": help_en,
    }


ORG_TYPES = _opt(
    ("GOV_HOSPITAL", "โรงพยาบาลรัฐ", "Government hospital"),
    ("PRIVATE_HOSPITAL", "โรงพยาบาลเอกชน", "Private hospital"),
    ("CLINIC", "คลินิก", "Clinic"),
    ("COMPANY", "บริษัท / ห้างร้าน", "Company"),
    ("OTHER", "อื่น ๆ", "Other"),
)


def common_customer_fields() -> list[dict]:
    return [
        _f("organization", "customer", "text", "ชื่อโรงพยาบาล / บริษัท / หน่วยงาน", "Hospital / Company / Organization",
           required=True, maps_to="customer.name", validation={"max_length": 255},
           placeholder_th="เช่น โรงพยาบาลตัวอย่าง", placeholder_en="e.g. Example Hospital"),
        _f("organization_type", "customer", "select", "ประเภทหน่วยงาน", "Organization type",
           maps_to="customer.customer_type", options=ORG_TYPES),
        _f("department", "customer", "text", "แผนก", "Department", maps_to="contact.department",
           validation={"max_length": 150}, placeholder_th="เช่น ห้องผ่าตัด", placeholder_en="e.g. Operating room"),
        _f("contact_name", "customer", "text", "ชื่อผู้ติดต่อ", "Contact name", required=True, maps_to="contact.name",
           validation={"max_length": 150}),
        _f("phone", "customer", "tel", "เบอร์โทรศัพท์", "Telephone", required=True, maps_to="contact.phone",
           placeholder_th="เช่น 081-234-5678", placeholder_en="e.g. 081-234-5678"),
        _f("email", "customer", "email", "อีเมล", "Email", maps_to="contact.email",
           help_th="ระบุเพื่อรับการแจ้งเตือนสถานะทางอีเมล", help_en="Provide to receive status updates by email"),
    ]


def additional_details() -> dict:
    return _f("additional_details", "request", "textarea", "รายละเอียดเพิ่มเติม", "Additional details",
              validation={"max_length": 3000})


def attachments(label_th: str, label_en: str, *, images_only: bool, max_files: int, help_th: str,
                help_en: str) -> dict:
    accept = ["image/jpeg", "image/png"] if images_only else ["image/jpeg", "image/png", "application/pdf"]
    return _f("attachments", "attachments", "file", label_th, label_en, maps_to="ticket.attachments",
              validation={"max_files": max_files, "max_size_mb": 10, "accept": accept},
              help_th=help_th, help_en=help_en)


QTY = {"integer": True, "min": 1, "max": 1_000_000}

FORMS: dict[str, dict[str, Any]] = {
    "PRODUCT": {
        "title_th": "แบบฟอร์มสอบถามผลิตภัณฑ์", "title_en": "Product Inquiry Form",
        "subject": "สอบถามผลิตภัณฑ์: {product_name}",
        "fields": [
            _f("product_name", "request", "text", "ชื่อผลิตภัณฑ์", "Product name", required=True),
            _f("item_code", "request", "text", "รหัสสินค้า (Item Code)", "Item code", validation={"max_length": 60}),
            _f("brand", "request", "text", "ยี่ห้อ", "Brand", validation={"max_length": 100}),
            _f("model", "request", "text", "รุ่นสินค้า", "Model", validation={"max_length": 100}),
            _f("quantity", "request", "number", "จำนวนที่ต้องการ", "Quantity required", validation=QTY),
            _f("question", "request", "textarea", "รายละเอียดคำถาม", "Question details", required=True,
               maps_to="ticket.description"),
            additional_details(),
            attachments("รูปภาพประกอบ / ไฟล์แนบ", "Images / attachments", images_only=False, max_files=5,
                        help_th="รูปสินค้า ป้ายรุ่น หรือเอกสาร (JPG, PNG, PDF) สูงสุด 5 ไฟล์ ไฟล์ละไม่เกิน 10 MB",
                        help_en="Product photos, labels or documents (JPG, PNG, PDF), up to 5 files, 10 MB each"),
        ],
    },
    "DELIVERY": {
        "title_th": "แบบฟอร์มติดตามการจัดส่ง", "title_en": "Delivery Tracking Form",
        "subject": "ติดตามการจัดส่ง PO {po_number}",
        "fields": [
            _f("po_number", "request", "text", "เลขที่ Purchase Order", "Purchase Order number", required=True,
               validation={"max_length": 60}),
            _f("delivery_note_no", "request", "text", "เลขที่ Delivery Note (ถ้ามี)", "Delivery Note number (if any)",
               validation={"max_length": 60}),
            _f("order_date", "request", "date", "วันที่สั่งซื้อ (ถ้าทราบ)", "Order date (if known)",
               validation={"not_future": True}),
            _f("inquiry_details", "request", "textarea", "รายละเอียดที่ต้องการสอบถาม", "Inquiry details",
               required=True, maps_to="ticket.description"),
            additional_details(),
            attachments("ไฟล์แนบ", "Attachments", images_only=False, max_files=5,
                        help_th="เช่น สำเนาใบสั่งซื้อ (JPG, PNG, PDF) สูงสุด 5 ไฟล์ ไฟล์ละไม่เกิน 10 MB",
                        help_en="e.g. a copy of the PO (JPG, PNG, PDF), up to 5 files, 10 MB each"),
        ],
    },
    "SERVICE": {
        "title_th": "แบบฟอร์มแจ้งซ่อม / บริการ", "title_en": "Service Request Form",
        "subject": "แจ้งซ่อม: {equipment_name} - {problem_type}",
        "fields": [
            _f("equipment_type", "request", "select", "ประเภทอุปกรณ์", "Equipment type", required=True,
               maps_to="ticket.category", options=_opt(
                   ("MEDICAL_DEVICE", "เครื่องมือแพทย์", "Medical device"),
                   ("SURGICAL_INSTRUMENT", "เครื่องมือผ่าตัด", "Surgical instrument"),
                   ("HOSPITAL_EQUIPMENT", "ครุภัณฑ์โรงพยาบาล", "Hospital equipment"),
                   ("LABORATORY", "อุปกรณ์ห้องปฏิบัติการ", "Laboratory equipment"),
                   ("OTHER", "อื่น ๆ", "Other"))),
            _f("equipment_name", "request", "text", "ชื่ออุปกรณ์", "Equipment name", required=True,
               validation={"max_length": 150}),
            _f("brand", "request", "text", "ยี่ห้อ", "Brand", validation={"max_length": 100}),
            _f("model", "request", "text", "รุ่น (Model)", "Model", validation={"max_length": 100}),
            _f("serial_number", "request", "text", "Serial Number", "Serial number", validation={"max_length": 100}),
            _f("install_location", "request", "text", "สถานที่ติดตั้ง", "Installation location",
               validation={"max_length": 200}, placeholder_th="เช่น อาคาร 2 ชั้น 3 ห้อง ICU",
               placeholder_en="e.g. Building 2, 3rd floor, ICU"),
            _f("problem_type", "request", "select", "ประเภทปัญหา", "Problem type", required=True, options=_opt(
                ("EQUIPMENT_FAILURE", "เครื่องเสีย / ใช้งานไม่ได้", "Equipment Failure"),
                ("ABNORMAL_OPERATION", "ทำงานผิดปกติ", "Abnormal Operation"),
                ("INSPECTION_REQUEST", "ขอตรวจเช็ค / สอบเทียบ", "Inspection Request"),
                ("PREVENTIVE_MAINTENANCE", "บำรุงรักษาเชิงป้องกัน (PM)", "Preventive Maintenance"),
                ("OTHER", "อื่น ๆ", "Other"))),
            _f("problem_description", "request", "textarea", "รายละเอียดอาการเสีย", "Problem description",
               required=True, maps_to="ticket.description"),
            _f("problem_date", "request", "date", "วันที่พบปัญหา", "Date problem found",
               validation={"not_future": True}),
            _f("urgency", "request", "select", "ระดับความเร่งด่วน", "Urgency", required=True,
               maps_to="ticket.priority", options=_opt(
                   ("LOW", "ต่ำ - ไม่กระทบการใช้งาน", "Low - no impact on use"),
                   ("NORMAL", "ปกติ", "Normal"),
                   ("HIGH", "สูง - กระทบการให้บริการ", "High - affects service"),
                   ("URGENT", "เร่งด่วนมาก - กระทบผู้ป่วย", "Urgent - affects patients"))),
            additional_details(),
            attachments("รูปภาพอุปกรณ์ที่ต้องการแจ้งซ่อม", "Photos of the equipment", images_only=True, max_files=10,
                        help_th="สามารถแนบรูปอุปกรณ์ อาการชำรุด ป้ายรุ่น หรือ Serial Number เพื่อประกอบการตรวจสอบ",
                        help_en="Attach photos of the equipment, the damage, the model label or serial number"),
        ],
    },
    "QUOTATION": {
        "title_th": "แบบฟอร์มขอใบเสนอราคา", "title_en": "Quotation Request Form",
        "subject": "ขอใบเสนอราคา: {product_name}",
        "fields": [
            _f("product_name", "request", "text", "ชื่อสินค้า", "Product name", required=True),
            _f("item_code", "request", "text", "รหัสสินค้า (ถ้ามี)", "Item code (if any)", validation={"max_length": 60}),
            _f("quantity", "request", "number", "จำนวนที่ต้องการ", "Quantity required", required=True, validation=QTY),
            _f("specifications", "request", "textarea", "รายละเอียดคุณลักษณะที่ต้องการ", "Required specifications",
               required=True, maps_to="ticket.description"),
            _f("required_date", "request", "date", "กำหนดวันที่ต้องการสินค้า", "Required delivery date",
               validation={"not_past": True}),
            additional_details(),
            attachments("เอกสารประกอบ", "Supporting documents", images_only=False, max_files=5,
                        help_th="เช่น TOR / Spec (JPG, PNG, PDF) สูงสุด 5 ไฟล์ ไฟล์ละไม่เกิน 10 MB",
                        help_en="e.g. TOR / specifications (JPG, PNG, PDF), up to 5 files, 10 MB each"),
        ],
    },
    "ACCOUNTING": {
        "title_th": "แบบฟอร์มติดต่อฝ่ายบัญชี", "title_en": "Accounting Inquiry Form",
        "subject": "บัญชี: {topic_type} {invoice_no}",
        "fields": [
            _f("topic_type", "request", "select", "ประเภทเรื่อง", "Topic", required=True, maps_to="ticket.category",
               options=_opt(
                   ("INVOICE", "สอบถามใบแจ้งหนี้", "Invoice inquiry"),
                   ("RECEIPT", "สอบถามใบเสร็จรับเงิน", "Receipt inquiry"),
                   ("PAYMENT", "สอบถามการชำระเงิน", "Payment inquiry"),
                   ("DOCUMENT", "สอบถามเอกสารบัญชี", "Accounting documents"),
                   ("OTHER", "อื่น ๆ", "Other"))),
            _f("invoice_no", "request", "text", "เลขที่ Invoice", "Invoice number", validation={"max_length": 60}),
            _f("reference_no", "request", "text", "เลขที่เอกสารอ้างอิง", "Reference document number",
               validation={"max_length": 60}),
            _f("question", "request", "textarea", "รายละเอียดคำถาม", "Question details", required=True,
               maps_to="ticket.description"),
            additional_details(),
            attachments("ไฟล์แนบ", "Attachments", images_only=False, max_files=5,
                        help_th="JPG, PNG, PDF สูงสุด 5 ไฟล์ ไฟล์ละไม่เกิน 10 MB",
                        help_en="JPG, PNG, PDF, up to 5 files, 10 MB each"),
        ],
    },
    "GENERAL": {
        "title_th": "แบบฟอร์มติดต่อเจ้าหน้าที่", "title_en": "General Contact Form",
        "subject": "{subject}",
        "fields": [
            _f("subject", "request", "text", "เรื่องที่ต้องการติดต่อ", "Subject", required=True,
               validation={"max_length": 200}),
            _f("question_type", "request", "select", "ประเภทคำถาม", "Question type", required=True,
               maps_to="ticket.category", options=_opt(
                   ("GENERAL_INQUIRY", "สอบถามทั่วไป", "General inquiry"),
                   ("COMPLAINT", "ร้องเรียน", "Complaint"),
                   ("SUGGESTION", "ข้อเสนอแนะ", "Suggestion"),
                   ("PARTNERSHIP", "ติดต่อธุรกิจ", "Business contact"),
                   ("OTHER", "อื่น ๆ", "Other"))),
            _f("details", "request", "textarea", "รายละเอียด", "Details", required=True, maps_to="ticket.description"),
            additional_details(),
            attachments("เอกสารแนบ", "Attachments", images_only=False, max_files=5,
                        help_th="JPG, PNG, PDF สูงสุด 5 ไฟล์ ไฟล์ละไม่เกิน 10 MB",
                        help_en="JPG, PNG, PDF, up to 5 files, 10 MB each"),
        ],
    },
}


def build_form_fields(form_id: int, field_defs: list[dict]) -> list[FormField]:
    return [FormField(form_definition_id=form_id, sort_order=(i + 1) * 10, **fd) for i, fd in enumerate(field_defs)]


def seed_reference_data(db: Session) -> dict[str, int]:
    created = {"departments": 0, "request_types": 0, "forms": 0, "statuses": 0, "transitions": 0}
    depts = {d.code: d for d in db.scalars(select(Department))}
    for code, th, en, sort in DEPARTMENTS:
        if code not in depts:
            depts[code] = Department(code=code, name_th=th, name_en=en, sort_order=sort)
            db.add(depts[code])
            created["departments"] += 1
    db.flush()

    for code, th, en, cat, terminal, sort, color in STATUSES:
        if db.get(TicketStatus, code) is None:
            db.add(TicketStatus(code=code, name_th=th, name_en=en, category=cat, is_terminal=terminal,
                                sort_order=sort, color=color))
            created["statuses"] += 1
    db.flush()

    existing_pairs = {(t.from_status, t.to_status) for t in db.scalars(select(WorkflowTransition))}
    if not existing_pairs:  # only seed the default workflow on an empty table
        for src, dst, roles, req in TRANSITIONS:
            db.add(WorkflowTransition(from_status=src, to_status=dst, allowed_roles=roles, requires_comment=req))
            created["transitions"] += 1
    db.flush()

    rts = {r.code: r for r in db.scalars(select(RequestType))}
    for code, slug, prefix, th, en, dth, den, icon, dept, sort in REQUEST_TYPES:
        if code not in rts:
            rts[code] = RequestType(code=code, slug=slug, ticket_prefix=prefix, name_th=th, name_en=en,
                                    description_th=dth, description_en=den, icon=icon,
                                    default_department_id=depts[dept].id, sort_order=sort)
            db.add(rts[code])
            created["request_types"] += 1
    db.flush()

    for code, spec in FORMS.items():
        rt = rts[code]
        has_form = db.scalar(select(FormDefinition.id).where(FormDefinition.request_type_id == rt.id).limit(1))
        if has_form:
            continue
        form = FormDefinition(request_type_id=rt.id, version=1, title_th=spec["title_th"], title_en=spec["title_en"],
                              subject_template=spec["subject"], is_active=True)
        db.add(form)
        db.flush()
        for ff in build_form_fields(form.id, common_customer_fields() + spec["fields"]):
            db.add(ff)
        created["forms"] += 1
    db.flush()
    return created
