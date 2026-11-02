"""Ticket numbering: format, per-type/per-year sequences and concurrency safety."""
from __future__ import annotations

import re
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from sqlalchemy import func, select

from app.db import SessionLocal
from app.models import RequestType, Ticket
from app.services.ticket_numbers import allocate_ticket_number, format_ticket_number
from app.services.ticket_service import submit_request
from tests.conftest import VALUES


def _rt(db, code: str) -> RequestType:
    return db.scalar(select(RequestType).where(RequestType.code == code))


def test_format():
    assert format_ticket_number("SRV", 2026, 1) == "BUC-SRV-2026-00001"
    assert format_ticket_number("PRD", 2026, 12345) == "BUC-PRD-2026-12345"


def test_sequences_are_per_type_and_reset_per_year(db):
    now = datetime(2026, 6, 1, tzinfo=timezone.utc)
    srv, prd = _rt(db, "SERVICE"), _rt(db, "PRODUCT")
    assert allocate_ticket_number(db, srv, now) == "BUC-SRV-2026-00001"
    assert allocate_ticket_number(db, srv, now) == "BUC-SRV-2026-00002"
    assert allocate_ticket_number(db, prd, now) == "BUC-PRD-2026-00001"
    # 31 Dec 2026 18:00 UTC is already 1 Jan 2027 in Bangkok (UTC+7) -> new yearly sequence.
    assert allocate_ticket_number(db, srv, datetime(2026, 12, 31, 18, 0, tzinfo=timezone.utc)) == "BUC-SRV-2027-00001"
    assert allocate_ticket_number(db, srv, now) == "BUC-SRV-2026-00003"
    db.commit()


def test_rolled_back_allocation_is_not_consumed_and_numbers_never_reused(db):
    now = datetime(2026, 3, 1, tzinfo=timezone.utc)
    srv = _rt(db, "SERVICE")
    assert allocate_ticket_number(db, srv, now).endswith("00001")
    db.commit()
    allocate_ticket_number(db, srv, now)  # 00002 in a transaction that fails
    db.rollback()
    assert allocate_ticket_number(db, srv, now).endswith("00002")
    db.commit()
    # Counters only go up; deleting/cancelling tickets never decrements them.
    assert allocate_ticket_number(db, srv, now).endswith("00003")
    db.commit()


def test_concurrent_allocation_produces_unique_contiguous_numbers():
    n = 40
    barrier = threading.Barrier(8)
    now = datetime(2026, 7, 1, tzinfo=timezone.utc)

    def work(_: int) -> str:
        with SessionLocal() as db:
            rt = _rt(db, "SERVICE")
            try:
                barrier.wait(timeout=5)
            except threading.BrokenBarrierError:
                pass
            number = allocate_ticket_number(db, rt, now)
            db.commit()
            return number

    with ThreadPoolExecutor(max_workers=8) as pool:
        numbers = list(pool.map(work, range(n)))
    assert len(set(numbers)) == n
    assert sorted(int(x[-5:]) for x in numbers) == list(range(1, n + 1))


def test_concurrent_full_submissions_create_unique_tickets():
    n = 16

    def work(i: int) -> str:
        with SessionLocal() as db:
            res = submit_request(db, slug="service", form_definition_id=None, values=VALUES["service"],
                                 privacy_consent=True, uploads=[], idempotency_key=f"concurrent-key-{i:08d}",
                                 client_ip="127.0.0.1")
            return res.ticket.ticket_number

    with ThreadPoolExecutor(max_workers=8) as pool:
        numbers = list(pool.map(work, range(n)))
    assert len(set(numbers)) == n
    assert all(re.fullmatch(r"BUC-SRV-\d{4}-\d{5}", x) for x in numbers)
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Ticket)) == n
        # One customer/contact despite concurrent first submissions with the same organisation.
        assert db.scalar(select(func.count(func.distinct(Ticket.customer_id)))) == 1


def test_concurrent_duplicate_submissions_with_same_key_create_one_ticket():
    def work(_: int) -> str:
        with SessionLocal() as db:
            res = submit_request(db, slug="service", form_definition_id=None, values=VALUES["service"],
                                 privacy_consent=True, uploads=[], idempotency_key="double-tap-key-000001",
                                 client_ip="127.0.0.1")
            return res.ticket.ticket_number

    with ThreadPoolExecutor(max_workers=6) as pool:
        numbers = list(pool.map(work, range(6)))
    assert len(set(numbers)) == 1
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Ticket)) == 1
