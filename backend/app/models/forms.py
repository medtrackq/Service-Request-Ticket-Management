"""Request types and the configurable (versioned) form engine."""
from __future__ import annotations

from typing import Any

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CreatedAtMixin, TimestampMixin

FIELD_TYPES = ("text", "textarea", "number", "date", "select", "email", "tel", "file")

# Where a form field's value is stored. Fields without a mapping are stored in ticket_details.
FIELD_MAPPINGS = (
    "customer.name",
    "customer.customer_type",
    "contact.name",
    "contact.department",
    "contact.phone",
    "contact.email",
    "ticket.priority",
    "ticket.description",
    "ticket.category",
    "ticket.attachments",
)


class RequestType(TimestampMixin, Base):
    __tablename__ = "request_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True)  # PRODUCT, SERVICE, ...
    slug: Mapped[str] = mapped_column(String(30), unique=True)  # URL path: /request/<slug>
    ticket_prefix: Mapped[str] = mapped_column(String(5), unique=True)  # PRD, SRV, ...
    name_th: Mapped[str] = mapped_column(String(150))
    name_en: Mapped[str] = mapped_column(String(150))
    description_th: Mapped[str | None] = mapped_column(Text)
    description_en: Mapped[str | None] = mapped_column(Text)
    icon: Mapped[str] = mapped_column(String(30), default="help")
    default_department_id: Mapped[int] = mapped_column(ForeignKey("departments.id", ondelete="RESTRICT"))
    default_priority: Mapped[str] = mapped_column(String(10), default="NORMAL", server_default="NORMAL")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    default_department = relationship("Department", lazy="joined")


class FormDefinition(CreatedAtMixin, Base):
    """A versioned form. Tickets reference the exact version they were submitted with."""

    __tablename__ = "form_definitions"
    __table_args__ = (
        UniqueConstraint("request_type_id", "version", name="uq_form_definitions_type_version"),
        Index(
            "uq_form_definitions_one_active",
            "request_type_id",
            unique=True,
            postgresql_where=text("is_active"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_type_id: Mapped[int] = mapped_column(ForeignKey("request_types.id", ondelete="RESTRICT"))
    version: Mapped[int] = mapped_column(Integer)
    title_th: Mapped[str] = mapped_column(String(200))
    title_en: Mapped[str] = mapped_column(String(200))
    # e.g. "{equipment_name} - {problem_type}" — placeholders are field keys (select fields use labels).
    subject_template: Mapped[str] = mapped_column(String(300))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    request_type: Mapped[RequestType] = relationship(lazy="joined")
    fields: Mapped[list[FormField]] = relationship(
        back_populates="form", order_by="FormField.sort_order", lazy="selectin", cascade="all, delete-orphan"
    )


class FormField(Base):
    __tablename__ = "form_fields"
    __table_args__ = (UniqueConstraint("form_definition_id", "key", name="uq_form_fields_form_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    form_definition_id: Mapped[int] = mapped_column(ForeignKey("form_definitions.id", ondelete="CASCADE"))
    key: Mapped[str] = mapped_column(String(60))
    section: Mapped[str] = mapped_column(String(20))  # customer | request | attachments
    field_type: Mapped[str] = mapped_column(String(20))
    label_th: Mapped[str] = mapped_column(String(200))
    label_en: Mapped[str] = mapped_column(String(200))
    placeholder_th: Mapped[str | None] = mapped_column(String(200))
    placeholder_en: Mapped[str | None] = mapped_column(String(200))
    help_th: Mapped[str | None] = mapped_column(Text)
    help_en: Mapped[str | None] = mapped_column(Text)
    required: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    # select: [{"value": "...", "label_th": "...", "label_en": "..."}]
    options: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    # text: max_length/pattern; number: min/max/integer; file: max_files/max_size_mb/accept
    validation: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    maps_to: Mapped[str | None] = mapped_column(String(40))

    form: Mapped[FormDefinition] = relationship(back_populates="fields")

    def option_label(self, value: str | None, lang: str = "th") -> str | None:
        if value is None or not self.options:
            return value
        for opt in self.options:
            if opt.get("value") == value:
                return opt.get(f"label_{lang}") or opt.get("label_th") or value
        return value

