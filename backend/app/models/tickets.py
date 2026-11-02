"""Tickets and everything that hangs off a ticket."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CreatedAtMixin, TimestampMixin, utcnow


class TicketSequence(Base):
    """Per request type, per year counter. Incremented atomically with INSERT .. ON CONFLICT."""

    __tablename__ = "ticket_sequences"
    __table_args__ = (UniqueConstraint("request_type_id", "year", name="uq_ticket_sequences_type_year"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_type_id: Mapped[int] = mapped_column(ForeignKey("request_types.id", ondelete="RESTRICT"))
    year: Mapped[int] = mapped_column(Integer)
    last_value: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)


class Ticket(TimestampMixin, Base):
    __tablename__ = "tickets"
    __table_args__ = (
        CheckConstraint("priority IN ('LOW','NORMAL','HIGH','URGENT')", name="priority_valid"),
        CheckConstraint("source IN ('WEB','LINE','STAFF')", name="source_valid"),
        Index("ix_tickets_created_at", "created_at"),
        Index("ix_tickets_status_department", "status", "department_id"),
        Index("ix_tickets_due_at", "due_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ticket_number: Mapped[str] = mapped_column(String(30), unique=True)
    request_type_id: Mapped[int] = mapped_column(ForeignKey("request_types.id", ondelete="RESTRICT"), index=True)
    form_definition_id: Mapped[int] = mapped_column(ForeignKey("form_definitions.id", ondelete="RESTRICT"))
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id", ondelete="RESTRICT"), index=True)
    contact_id: Mapped[int] = mapped_column(ForeignKey("customer_contacts.id", ondelete="RESTRICT"), index=True)

    subject: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(60))
    priority: Mapped[str] = mapped_column(String(10), default="NORMAL")
    status: Mapped[str] = mapped_column(ForeignKey("ticket_statuses.code", ondelete="RESTRICT"), index=True)
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id", ondelete="RESTRICT"), index=True)
    assigned_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)

    due_at: Mapped[datetime | None]
    first_response_at: Mapped[datetime | None]
    resolved_at: Mapped[datetime | None]
    closed_at: Mapped[datetime | None]
    cancelled_at: Mapped[datetime | None]
    last_activity_at: Mapped[datetime] = mapped_column(default=utcnow)
    overdue_notified_at: Mapped[datetime | None]

    source: Mapped[str] = mapped_column(String(10), default="WEB")
    line_user_id: Mapped[str | None] = mapped_column(String(64), index=True)
    # Client generated key: replaying the same submission returns the same ticket.
    idempotency_key: Mapped[str | None] = mapped_column(String(64), unique=True)
    submission_hash: Mapped[str | None] = mapped_column(String(64))
    privacy_consent_version: Mapped[str | None] = mapped_column(String(20))
    privacy_consent_at: Mapped[datetime | None]
    submitter_ip: Mapped[str | None] = mapped_column(String(64))
    # Demo / sample data is always flagged so it can be excluded or purged.
    is_sample: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    anonymized_at: Mapped[datetime | None]

    request_type = relationship("RequestType", lazy="joined")
    customer = relationship("Customer", lazy="joined")
    contact = relationship("CustomerContact", lazy="joined")
    department = relationship("Department", lazy="joined")
    assigned_user = relationship("User", lazy="joined")
    status_ref = relationship("TicketStatus", lazy="joined")
    details: Mapped[list[TicketDetail]] = relationship(
        back_populates="ticket", order_by="TicketDetail.sort_order", cascade="all, delete-orphan"
    )
    attachments: Mapped[list[TicketAttachment]] = relationship(
        back_populates="ticket", order_by="TicketAttachment.created_at"
    )


class TicketDetail(Base):
    """Structured, form-specific request data (one row per form field)."""

    __tablename__ = "ticket_details"
    __table_args__ = (UniqueConstraint("ticket_id", "field_key", name="uq_ticket_details_ticket_field"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id", ondelete="CASCADE"), index=True)
    form_field_id: Mapped[int | None] = mapped_column(ForeignKey("form_fields.id", ondelete="SET NULL"))
    field_key: Mapped[str] = mapped_column(String(60))
    # Label snapshot at submission time so history stays readable after form changes.
    label_th: Mapped[str] = mapped_column(String(200))
    label_en: Mapped[str] = mapped_column(String(200))
    value_text: Mapped[str | None] = mapped_column(Text)
    # For select fields: the display labels, for structured values.
    value_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    ticket: Mapped[Ticket] = relationship(back_populates="details")


class TicketAttachment(CreatedAtMixin, Base):
    __tablename__ = "ticket_attachments"
    __table_args__ = (
        # Same file content cannot be attached twice to one ticket (repeated submissions).
        UniqueConstraint("ticket_id", "sha256", name="uq_ticket_attachments_ticket_sha"),
        CheckConstraint("kind IN ('IMAGE','DOCUMENT')", name="kind_valid"),
        CheckConstraint("source IN ('CUSTOMER','STAFF')", name="source_valid"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id", ondelete="CASCADE"), index=True)
    comment_id: Mapped[int | None] = mapped_column(ForeignKey("ticket_comments.id", ondelete="SET NULL"))
    original_filename: Mapped[str] = mapped_column(String(255))
    # Path relative to the private storage root; generated, never derived from user input.
    stored_path: Mapped[str] = mapped_column(String(255), unique=True)
    mime_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(10))
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(10))
    uploaded_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    deleted_at: Mapped[datetime | None]

    ticket: Mapped[Ticket] = relationship(back_populates="attachments")
    uploaded_by = relationship("User", lazy="joined")


class TicketStatusHistory(CreatedAtMixin, Base):
    __tablename__ = "ticket_status_history"
    __table_args__ = (Index("ix_ticket_status_history_ticket_created", "ticket_id", "created_at"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id", ondelete="CASCADE"))
    from_status: Mapped[str | None] = mapped_column(String(30))
    to_status: Mapped[str] = mapped_column(String(30))
    changed_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    actor_type: Mapped[str] = mapped_column(String(10), default="STAFF")  # STAFF | CUSTOMER | SYSTEM
    comment: Mapped[str | None] = mapped_column(Text)  # internal reason, never shown to customers

    changed_by = relationship("User", lazy="joined")


class TicketAssignment(CreatedAtMixin, Base):
    """Assignment / transfer history. The ticket row holds the current assignment."""

    __tablename__ = "ticket_assignments"
    __table_args__ = (Index("ix_ticket_assignments_ticket_created", "ticket_id", "created_at"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id", ondelete="CASCADE"))
    assignment_type: Mapped[str] = mapped_column(String(20))  # INITIAL | AUTO | MANUAL | TRANSFER | SELF
    from_department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id", ondelete="SET NULL"))
    to_department_id: Mapped[int] = mapped_column(ForeignKey("departments.id", ondelete="RESTRICT"))
    from_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    to_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    assigned_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    priority: Mapped[str | None] = mapped_column(String(10))
    due_at: Mapped[datetime | None]
    reason: Mapped[str | None] = mapped_column(Text)

    from_department = relationship("Department", foreign_keys=[from_department_id], lazy="joined")
    to_department = relationship("Department", foreign_keys=[to_department_id], lazy="joined")
    from_user = relationship("User", foreign_keys=[from_user_id], lazy="joined")
    to_user = relationship("User", foreign_keys=[to_user_id], lazy="joined")
    assigned_by = relationship("User", foreign_keys=[assigned_by_user_id], lazy="joined")


class TicketComment(CreatedAtMixin, Base):
    __tablename__ = "ticket_comments"
    __table_args__ = (
        CheckConstraint("visibility IN ('INTERNAL','PUBLIC')", name="visibility_valid"),
        CheckConstraint("author_type IN ('STAFF','CUSTOMER','SYSTEM')", name="author_type_valid"),
        Index("ix_ticket_comments_ticket_created", "ticket_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id", ondelete="CASCADE"))
    author_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    author_type: Mapped[str] = mapped_column(String(10))
    visibility: Mapped[str] = mapped_column(String(10))
    body: Mapped[str] = mapped_column(Text)

    author = relationship("User", lazy="joined")


class TicketTrackingToken(CreatedAtMixin, Base):
    """Customer tracking credential. Only the SHA-256 hash of the token is stored."""

    __tablename__ = "ticket_tracking_tokens"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    expires_at: Mapped[datetime | None]
    revoked_at: Mapped[datetime | None]
    last_used_at: Mapped[datetime | None]
