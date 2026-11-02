"""Atomic ticket numbering: BUC-{TYPE}-{YYYY}-{NNNNN}.

The counter row for (request type, year) is incremented with a single
`INSERT .. ON CONFLICT DO UPDATE .. RETURNING` statement. PostgreSQL row locking
serialises concurrent transactions on the same row, so two transactions can never
receive the same value. Counters only ever increase, so numbers are never reused
after cancellation or deletion. The tickets.ticket_number UNIQUE constraint is a
second line of defence.

The year is the calendar year (Gregorian, Asia/Bangkok) of ticket creation, so
sequences reset every 1 January Bangkok time and are separate per ticket type.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import RequestType, TicketSequence


def format_ticket_number(prefix: str, year: int, value: int) -> str:
    return f"BUC-{prefix}-{year}-{value:05d}"


def allocate_ticket_number(db: Session, request_type: RequestType, now: datetime) -> str:
    year = now.astimezone(ZoneInfo(get_settings().timezone)).year
    stmt = (
        insert(TicketSequence)
        .values(request_type_id=request_type.id, year=year, last_value=1)
        .on_conflict_do_update(
            constraint="uq_ticket_sequences_type_year",
            set_={"last_value": TicketSequence.last_value + 1, "updated_at": func.now()},
        )
        .returning(TicketSequence.last_value)
    )
    value = db.execute(stmt).scalar_one()
    return format_ticket_number(request_type.ticket_prefix, year, value)
