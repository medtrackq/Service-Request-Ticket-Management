"""Customer master data and contact persons."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

CUSTOMER_TYPES = ("GOV_HOSPITAL", "PRIVATE_HOSPITAL", "CLINIC", "COMPANY", "OTHER")


class Customer(TimestampMixin, Base):
    __tablename__ = "customers"
    __table_args__ = (
        CheckConstraint(
            "customer_type IN ('GOV_HOSPITAL','PRIVATE_HOSPITAL','CLINIC','COMPANY','OTHER')",
            name="customer_type_valid",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Optional internal customer code (e.g. the future ERPNext Customer ID is kept in integration_mappings).
    code: Mapped[str | None] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(255))
    # Lower-cased, whitespace-collapsed name used to match portal submissions to existing customers.
    normalized_name: Mapped[str] = mapped_column(String(255), unique=True)
    customer_type: Mapped[str] = mapped_column(String(30), default="OTHER", server_default="OTHER")
    tax_id: Mapped[str | None] = mapped_column(String(20))
    address: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    contacts: Mapped[list[CustomerContact]] = relationship(back_populates="customer")


class CustomerContact(TimestampMixin, Base):
    __tablename__ = "customer_contacts"
    __table_args__ = (UniqueConstraint("customer_id", "match_key", name="uq_customer_contacts_match"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id", ondelete="RESTRICT"), index=True)
    name: Mapped[str] = mapped_column(String(150))
    department: Mapped[str | None] = mapped_column(String(150))
    phone: Mapped[str | None] = mapped_column(String(30))
    email: Mapped[str | None] = mapped_column(String(254))
    # Verified LINE userId (only set after server-side LIFF ID token verification).
    line_user_id: Mapped[str | None] = mapped_column(String(64), index=True)
    # normalized-name|digits-only-phone; used to avoid duplicate contacts.
    match_key: Mapped[str] = mapped_column(String(300))
    anonymized_at: Mapped[datetime | None]

    customer: Mapped[Customer] = relationship(back_populates="contacts", lazy="joined")
