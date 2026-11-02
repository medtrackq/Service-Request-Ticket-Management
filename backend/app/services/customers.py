"""Customer and contact matching so portal submissions do not duplicate master data."""
from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import Customer, CustomerContact
from app.models.customers import CUSTOMER_TYPES


def normalize_name(name: str) -> str:
    return re.sub(r"\s+", " ", name).strip().lower()


def normalize_phone(phone: str | None) -> str:
    return re.sub(r"\D", "", phone or "")


def find_or_create_customer(db: Session, name: str, customer_type: str | None) -> Customer:
    norm = normalize_name(name)[:255]
    ctype = customer_type if customer_type in CUSTOMER_TYPES else "OTHER"
    # INSERT .. ON CONFLICT DO NOTHING keeps concurrent submissions from racing on the unique name.
    db.execute(
        insert(Customer)
        .values(name=name.strip()[:255], normalized_name=norm, customer_type=ctype)
        .on_conflict_do_nothing(index_elements=["normalized_name"])
    )
    customer = db.scalar(select(Customer).where(Customer.normalized_name == norm))
    assert customer is not None
    # Fill in the type for customers first created without one; never overwrite staff-curated data.
    if customer.customer_type == "OTHER" and ctype != "OTHER":
        customer.customer_type = ctype
    return customer


def find_or_create_contact(
    db: Session,
    customer: Customer,
    *,
    name: str,
    department: str | None,
    phone: str | None,
    email: str | None,
    line_user_id: str | None = None,
) -> CustomerContact:
    match_key = f"{normalize_name(name)}|{normalize_phone(phone)}"[:300]
    db.execute(
        insert(CustomerContact)
        .values(customer_id=customer.id, name=name.strip()[:150], department=department, phone=phone,
                email=email, line_user_id=line_user_id, match_key=match_key)
        .on_conflict_do_nothing(constraint="uq_customer_contacts_match")
    )
    contact = db.scalar(
        select(CustomerContact).where(CustomerContact.customer_id == customer.id, CustomerContact.match_key == match_key)
    )
    assert contact is not None
    # Keep the latest contact details supplied by the customer.
    if department:
        contact.department = department
    if email:
        contact.email = email
    if line_user_id:
        contact.line_user_id = line_user_id
    return contact
