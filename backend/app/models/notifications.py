"""Notification outbox / log. The worker delivers PENDING rows asynchronously."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin, utcnow


class TicketNotification(CreatedAtMixin, Base):
    __tablename__ = "ticket_notifications"
    __table_args__ = (
        CheckConstraint("channel IN ('IN_APP','EMAIL','LINE')", name="channel_valid"),
        CheckConstraint("status IN ('PENDING','SENDING','SENT','FAILED','SKIPPED')", name="status_valid"),
        Index("ix_ticket_notifications_queue", "status", "next_attempt_at"),
        Index("ix_ticket_notifications_inbox", "recipient_user_id", "channel", "read_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ticket_id: Mapped[int | None] = mapped_column(ForeignKey("tickets.id", ondelete="CASCADE"), index=True)
    event_type: Mapped[str] = mapped_column(String(40))
    channel: Mapped[str] = mapped_column(String(10))
    recipient_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    recipient_address: Mapped[str | None] = mapped_column(String(254))  # email / LINE userId
    subject: Mapped[str] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(Text)
    link_url: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(10), default="PENDING")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=5)
    next_attempt_at: Mapped[datetime] = mapped_column(default=utcnow)
    last_error: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime | None]
    read_at: Mapped[datetime | None]
