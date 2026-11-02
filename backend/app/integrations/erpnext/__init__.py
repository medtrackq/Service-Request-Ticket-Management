"""Future ERPNext integration (interfaces and placeholders only — no live sync in the MVP).

See docs/ERPNEXT_INTEGRATION.md for the integration design.
"""
from app.integrations.erpnext.adapter import DisabledERPNextAdapter, get_erpnext_adapter
from app.integrations.erpnext.interfaces import ERPNextAdapter, IntegrationDisabled

__all__ = ["DisabledERPNextAdapter", "ERPNextAdapter", "IntegrationDisabled", "get_erpnext_adapter"]
