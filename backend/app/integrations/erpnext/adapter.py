"""ERPNext adapter placeholder.

The MVP ships with `DisabledERPNextAdapter`, which refuses every call. A real
`FrappeRestERPNextAdapter` will be implemented once ERPNext is live, its version
and DocType metadata have been verified, and least-privilege API credentials exist.
"""
from __future__ import annotations

from typing import NoReturn

from sqlalchemy.orm import Session

from app.integrations.erpnext.interfaces import (
    CustomerPayload,
    DeliveryStatus,
    ExternalRef,
    IntegrationDisabled,
    ItemInfo,
    QuotationRequest,
    SerialNoInfo,
    VersionInfo,
)
from app.models import IntegrationLog, IntegrationMapping, utcnow

SYSTEM = "ERPNEXT"


class DisabledERPNextAdapter:
    enabled = False

    def _refuse(self, *_: object, **__: object) -> NoReturn:
        raise IntegrationDisabled("ERPNext integration is not enabled in this version")

    def get_versions(self) -> VersionInfo:
        self._refuse()

    def doctype_has_field(self, doctype: str, fieldname: str) -> bool:
        self._refuse()

    def find_customer(self, customer_name: str, tax_id: str | None = None) -> ExternalRef | None:
        self._refuse()

    def upsert_customer(self, payload: CustomerPayload) -> ExternalRef:
        self._refuse()

    def get_item(self, item_code: str) -> ItemInfo | None:
        self._refuse()

    def get_serial_no(self, serial_no: str) -> SerialNoInfo | None:
        self._refuse()

    def find_delivery_notes(self, customer: ExternalRef, customer_po: str) -> list[DeliveryStatus]:
        self._refuse()

    def create_draft_quotation(self, request: QuotationRequest) -> ExternalRef:
        self._refuse()


def get_erpnext_adapter() -> DisabledERPNextAdapter:
    return DisabledERPNextAdapter()


# ---------------------------------------------------------------- mapping helpers (usable today)


def upsert_mapping(db: Session, *, local_entity_type: str, local_id: str, external_doctype: str,
                   external_name: str | None, user_id: int | None) -> IntegrationMapping:
    """Record a manual mapping (e.g. customer -> ERPNext Customer name). No remote call is made."""
    row = db.query(IntegrationMapping).filter_by(
        system=SYSTEM, local_entity_type=local_entity_type, local_id=local_id, external_doctype=external_doctype
    ).one_or_none()
    if row is None:
        row = IntegrationMapping(system=SYSTEM, local_entity_type=local_entity_type, local_id=local_id,
                                 external_doctype=external_doctype, created_by_user_id=user_id)
        db.add(row)
    row.external_name = external_name
    row.sync_status = "MAPPED_MANUALLY" if external_name else "NOT_SYNCED"
    row.updated_at = utcnow()
    db.add(IntegrationLog(system=SYSTEM, direction="INTERNAL", operation="mapping.upsert",
                          local_entity_type=local_entity_type, local_id=local_id, external_doctype=external_doctype,
                          external_name=external_name, status="SUCCESS"))
    return row
