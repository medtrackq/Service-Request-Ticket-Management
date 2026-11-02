"""Interface definitions for a future ERPNext/Frappe adapter.

Design rules (see docs/ERPNEXT_INTEGRATION.md):
* Only the Frappe REST API is used (`/api/resource/<DocType>`, `/api/method/...`);
  never direct writes to ERPNext database tables.
* External document names are stored in `integration_mappings`; every call is
  recorded in `integration_logs`.
* Custom fields are NEVER assumed: an implementation must read DocType metadata
  (`/api/method/frappe.desk.form.load.getdoctype`) and the ERPNext version first.
* Least-privilege API key/secret dedicated to this integration.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Protocol


class IntegrationDisabled(Exception):
    """Raised when an ERPNext operation is requested while the integration is disabled."""


@dataclass
class ExternalRef:
    doctype: str
    name: str


@dataclass
class CustomerPayload:
    local_customer_id: int
    customer_name: str
    customer_type: str
    tax_id: str | None = None


@dataclass
class ItemInfo:
    item_code: str
    item_name: str
    brand: str | None = None
    item_group: str | None = None


@dataclass
class SerialNoInfo:
    serial_no: str
    item_code: str | None
    customer: str | None
    warranty_expiry_date: date | None = None
    amc_expiry_date: date | None = None


@dataclass
class DeliveryStatus:
    delivery_note: str
    status: str
    posting_date: date | None
    customer_po: str | None = None
    items: list[dict] = field(default_factory=list)


@dataclass
class QuotationRequest:
    local_ticket_id: int
    ticket_number: str
    customer: ExternalRef | None
    items: list[dict]
    required_by: date | None = None


@dataclass
class VersionInfo:
    frappe_version: str
    erpnext_version: str


class ERPNextAdapter(Protocol):
    """Operations the ticket system may need from ERPNext in later phases."""

    enabled: bool

    def get_versions(self) -> VersionInfo: ...

    def doctype_has_field(self, doctype: str, fieldname: str) -> bool: ...

    # Customer integration
    def find_customer(self, customer_name: str, tax_id: str | None = None) -> ExternalRef | None: ...

    def upsert_customer(self, payload: CustomerPayload) -> ExternalRef: ...

    # Item / Serial No integration
    def get_item(self, item_code: str) -> ItemInfo | None: ...

    def get_serial_no(self, serial_no: str) -> SerialNoInfo | None: ...

    # Delivery tracking
    def find_delivery_notes(self, customer: ExternalRef, customer_po: str) -> list[DeliveryStatus]: ...

    # Sales integration (authorised staff action, never automatic in MVP)
    def create_draft_quotation(self, request: QuotationRequest) -> ExternalRef: ...
