"""Test fixtures. Tests run against a real PostgreSQL database (BUC_TEST_DATABASE_URL).

The schema is created with the Alembic migrations (so migrations are tested too),
reference data is seeded once, and transactional tables are truncated per test.
"""
from __future__ import annotations

import io
import os
import tempfile
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest

TEST_DB = os.environ.get(
    "BUC_TEST_DATABASE_URL", "postgresql+psycopg://buc:buc_dev_password@localhost:5432/buc_service_test"
)
os.environ["BUC_DATABASE_URL"] = TEST_DB
os.environ["BUC_ENVIRONMENT"] = "test"
os.environ["BUC_SECRET_KEY"] = "test-secret-key-test-secret-key-0123456789"
os.environ["BUC_PUBLIC_BASE_URL"] = "https://service.example.test"
os.environ["BUC_SMTP_HOST"] = ""
os.environ["BUC_STORAGE_DIR"] = tempfile.mkdtemp(prefix="buc-test-storage-")

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.models import Department, User  # noqa: E402
from app.security.passwords import hash_password  # noqa: E402
from app.security.rate_limit import limiter  # noqa: E402
from app.seed import seed_reference_data  # noqa: E402

BACKEND_DIR = Path(__file__).resolve().parent.parent
PASSWORD = "Test-Password-123"

ALL_TABLES_SQL = (
    "SELECT string_agg(quote_ident(tablename), ', ') FROM pg_tables "
    "WHERE schemaname = 'public' AND tablename <> 'alembic_version'"
)


@pytest.fixture(scope="session", autouse=True)
def database() -> Iterator[None]:
    engine = create_engine(TEST_DB)
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    engine.dispose()
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    command.upgrade(cfg, "head")
    with SessionLocal() as db:
        seed_reference_data(db)
        db.commit()
    yield


@pytest.fixture(autouse=True)
def clean_tables() -> Iterator[None]:
    """Every test starts from freshly seeded reference data and empty transactional tables."""
    with SessionLocal() as db:
        tables = db.execute(text(ALL_TABLES_SQL)).scalar_one()
        db.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
        seed_reference_data(db)
        db.commit()
    limiter.reset()
    limiter.enabled = False
    yield


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session


@pytest.fixture
def client() -> Iterator[TestClient]:
    from app.main import app

    with TestClient(app, base_url="https://testserver") as c:
        yield c


def dept_id(code: str) -> int:
    with SessionLocal() as db:
        return db.query(Department).filter_by(code=code).one().id


def make_user(username: str, role: str = "STAFF", depts: tuple[str, ...] = (), *, must_change: bool = False,
              email: str | None = None) -> int:
    with SessionLocal() as db:
        u = User(username=username, full_name=f"{username.title()} Tester", role=role, email=email,
                 password_hash=hash_password(PASSWORD), must_change_password=must_change)
        u.departments = [db.query(Department).filter_by(code=c).one() for c in depts]
        db.add(u)
        db.commit()
        return u.id


class StaffClient:
    """TestClient wrapper that keeps the session cookie and sends the CSRF header."""

    def __init__(self, client: TestClient, csrf: str) -> None:
        self.c = client
        self.csrf = csrf

    def get(self, url: str, **kw):
        return self.c.get(url, **kw)

    def post(self, url: str, **kw):
        return self.c.post(url, headers={"X-CSRF-Token": self.csrf, **kw.pop("headers", {})}, **kw)

    def put(self, url: str, **kw):
        return self.c.put(url, headers={"X-CSRF-Token": self.csrf, **kw.pop("headers", {})}, **kw)

    def patch(self, url: str, **kw):
        return self.c.patch(url, headers={"X-CSRF-Token": self.csrf, **kw.pop("headers", {})}, **kw)

    def delete(self, url: str, **kw):
        return self.c.delete(url, headers={"X-CSRF-Token": self.csrf, **kw.pop("headers", {})}, **kw)


def login(username: str, password: str = PASSWORD) -> StaffClient:
    from app.main import app

    c = TestClient(app, base_url="https://testserver")
    r = c.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return StaffClient(c, r.json()["csrf_token"])


# ----------------------------------------------------------------------------- payload helpers


def image_bytes(fmt: str = "JPEG", color: str | tuple = "red", size: tuple[int, int] = (64, 48)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, fmt)
    return buf.getvalue()


def distinct_images(n: int, fmt: str = "JPEG") -> list[tuple[str, bytes, str]]:
    mime = "image/jpeg" if fmt == "JPEG" else "image/png"
    ext = "jpg" if fmt == "JPEG" else "png"
    return [(f"photo{i}.{ext}", image_bytes(fmt, (i * 20 % 256, i * 7 % 256, 100)), mime) for i in range(n)]


COMMON = {
    "organization": "โรงพยาบาลทดสอบ", "organization_type": "GOV_HOSPITAL", "department": "ICU",
    "contact_name": "สมชาย ทดสอบ", "phone": "081-234-5678", "email": "customer@example.com",
}

VALUES = {
    "service": {**COMMON, "equipment_type": "MEDICAL_DEVICE", "equipment_name": "Infusion Pump", "brand": "BrandX",
                "model": "IP-100", "serial_number": "SN-TEST-001", "install_location": "ICU",
                "problem_type": "EQUIPMENT_FAILURE", "problem_description": "เครื่องไม่ทำงาน",
                "problem_date": "2026-01-15", "urgency": "HIGH"},
    "product": {**COMMON, "product_name": "ถุงมือผ่าตัด", "quantity": 10, "question": "ขอสเปก"},
    "delivery": {**COMMON, "po_number": "PO-123", "inquiry_details": "สินค้าถึงเมื่อไร"},
    "quotation": {**COMMON, "product_name": "เตียงผู้ป่วย", "quantity": 2, "specifications": "ไฟฟ้า 3 ไกร์"},
    "accounting": {**COMMON, "topic_type": "INVOICE", "invoice_no": "IV001", "question": "ขอสำเนาใบแจ้งหนี้"},
    "general": {**COMMON, "subject": "ติดต่อฝ่ายขาย", "question_type": "GENERAL_INQUIRY", "details": "รายละเอียด"},
}


def submit(client: TestClient, slug: str = "service", values: dict | None = None,
           files: list[tuple[str, bytes, str]] | None = None, key: str | None = None, consent: bool = True,
           extra: dict | None = None):
    import json

    payload = {"values": values if values is not None else VALUES[slug], "privacy_consent": consent, **(extra or {})}
    multipart = [("files", f) for f in (files or [])]
    headers = {"Idempotency-Key": key or uuid.uuid4().hex}
    return client.post(f"/api/v1/public/requests/{slug}", data={"payload": json.dumps(payload)},
                       files=multipart or None, headers=headers)
