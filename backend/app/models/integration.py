"""Future ERPNext (and other system) integration bookkeeping.

These tables exist from day one so that connecting ERPNext later does not
require reshaping ticket/customer tables. No live synchronisation runs in the MVP.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin, TimestampMixin


class IntegrationMapping(TimestampMixin, Base):
    """Link between a local record and an external document (e.g. Customer -> ERPNext Customer)."""

    __tablename__ = "integration_mappings"
    __table_args__ = (
        UniqueConstraint(
            "system", "local_entity_type", "local_id", "external_doctype", name="uq_integration_mappings_local"
        ),
        Index("ix_integration_mappings_external", "system", "external_doctype", "external_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    system: Mapped[str] = mapped_column(String(30))  # ERPNEXT
    local_entity_type: Mapped[str] = mapped_column(String(50))  # customer | ticket | ...
    local_id: Mapped[str] = mapped_column(String(64))
    external_doctype: Mapped[str] = mapped_column(String(80))  # Customer | Item | Serial No | ...
    external_name: Mapped[str | None] = mapped_column(String(140))  # ERPNext document name
    sync_status: Mapped[str] = mapped_column(String(20), default="NOT_SYNCED")
    last_synced_at: Mapped[datetime | None]
    last_error: Mapped[str | None] = mapped_column(Text)
    payload_hash: Mapped[str | None] = mapped_column(String(64))  # detect unchanged payloads
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class IntegrationLog(CreatedAtMixin, Base):
    __tablename__ = "integration_logs"
    __table_args__ = (Index("ix_integration_logs_created_at", "created_at"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    system: Mapped[str] = mapped_column(String(30))
    direction: Mapped[str] = mapped_column(String(10))  # OUTBOUND | INBOUND
    operation: Mapped[str] = mapped_column(String(80))
    local_entity_type: Mapped[str | None] = mapped_column(String(50))
    local_id: Mapped[str | None] = mapped_column(String(64))
    external_doctype: Mapped[str | None] = mapped_column(String(80))
    external_name: Mapped[str | None] = mapped_column(String(140))
    status: Mapped[str] = mapped_column(String(20))  # SUCCESS | FAILED | SKIPPED
    attempts: Mapped[int] = mapped_column(Integer, default=1)
    request_summary: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    response_summary: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(Text)
