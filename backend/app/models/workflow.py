"""Configurable ticket statuses, allowed transitions and assignment rules."""
from __future__ import annotations

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

# Category drives reporting: what counts as "open", "waiting", "resolved", ...
STATUS_CATEGORIES = ("NEW", "OPEN", "WAITING", "RESOLVED", "CLOSED", "CANCELLED")
PRIORITIES = ("LOW", "NORMAL", "HIGH", "URGENT")


class TicketStatus(Base):
    __tablename__ = "ticket_statuses"
    __table_args__ = (
        CheckConstraint(
            "category IN ('NEW','OPEN','WAITING','RESOLVED','CLOSED','CANCELLED')", name="category_valid"
        ),
    )

    code: Mapped[str] = mapped_column(String(30), primary_key=True)
    name_th: Mapped[str] = mapped_column(String(100))
    name_en: Mapped[str] = mapped_column(String(100))
    category: Mapped[str] = mapped_column(String(20))
    is_terminal: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    color: Mapped[str] = mapped_column(String(20), default="gray")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class WorkflowTransition(TimestampMixin, Base):
    __tablename__ = "workflow_transitions"
    __table_args__ = (UniqueConstraint("from_status", "to_status", name="uq_workflow_transitions_pair"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    from_status: Mapped[str] = mapped_column(ForeignKey("ticket_statuses.code", ondelete="CASCADE"))
    to_status: Mapped[str] = mapped_column(ForeignKey("ticket_statuses.code", ondelete="CASCADE"))
    # Roles allowed to perform this transition, e.g. ["ADMIN","MANAGER","STAFF"]
    allowed_roles: Mapped[list[str]] = mapped_column(JSONB)
    requires_comment: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class AssignmentRule(TimestampMixin, Base):
    """Automatic assignment rule. Evaluated in sort_order; the first matching active rule wins.

    A NULL condition means "any". Automatic assignment only runs when the
    `assignment.auto_enabled` system setting is true.
    """

    __tablename__ = "assignment_rules"
    __table_args__ = (
        CheckConstraint("priority IS NULL OR priority IN ('LOW','NORMAL','HIGH','URGENT')", name="priority_valid"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(150))
    sort_order: Mapped[int] = mapped_column(Integer, default=100)
    request_type_id: Mapped[int | None] = mapped_column(ForeignKey("request_types.id", ondelete="CASCADE"))
    category: Mapped[str | None] = mapped_column(String(60))  # product/equipment category value
    customer_type: Mapped[str | None] = mapped_column(String(30))
    priority: Mapped[str | None] = mapped_column(String(10))
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id", ondelete="CASCADE"))
    assigned_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    department = relationship("Department", lazy="joined")
    assigned_user = relationship("User", lazy="joined")
    request_type = relationship("RequestType", lazy="joined")
