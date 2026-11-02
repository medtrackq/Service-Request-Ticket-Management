# Future ERPNext Integration Design

**Status in this version:** not implemented. The ticket system is fully functional without
ERPNext. What exists today:

* `integration_mappings` and `integration_logs` tables (+ admin screens).
* Manual mapping of a customer to an ERPNext Customer name (no remote call).
* `backend/app/integrations/erpnext/interfaces.py` — the `ERPNextAdapter` protocol and DTOs.
* `backend/app/integrations/erpnext/adapter.py` — `DisabledERPNextAdapter`, which raises
  `IntegrationDisabled` for every operation (covered by a unit test).

## Principles

1. **REST API only** — Frappe `/api/resource/<DocType>` and whitelisted `/api/method/...`; never
   write to ERPNext database tables.
2. **Least privilege** — a dedicated ERPNext user + API key/secret with only the roles needed
   (read Customer/Item/Serial No/Delivery Note; create draft Quotation if approved).
3. **Verify before building** — at start-up the adapter must read the ERPNext/Frappe version
   (`/api/method/frappe.utils.change_log.get_versions`) and DocType metadata
   (`/api/method/frappe.desk.form.load.getdoctype?doctype=...`). Custom fields are never assumed;
   if a required field is missing the operation is disabled and logged.
4. **Idempotent sync** — `integration_mappings` holds `(local entity, external doctype) →
   external name` with `payload_hash`; unchanged payloads are skipped, so a retry never
   creates duplicates.
5. **Asynchronous with retries** — outbound sync runs in the worker (same pattern as the
   notification outbox) with exponential backoff; every attempt is written to `integration_logs`.
6. **Ticket system stays the system of record for tickets**; ERPNext is the system of record
   for customers, items, serial numbers, delivery notes and quotations.

## Planned integrations

| Area | Direction | ERPNext DocType | Use in ticket system |
|------|-----------|-----------------|----------------------|
| Customer | read / optional create | Customer | Link `customers` ↔ Customer (`integration_mappings`, doctype `Customer`) |
| Item | read | Item | Validate / enrich item codes in Product & Quotation forms |
| Serial number | read | Serial No | Pre-fill equipment, warranty/AMC expiry for Service Requests |
| Delivery tracking | read | Delivery Note (+ Sales Order PO no.) | Show authorised delivery status for Delivery tickets (staff first, customer view only after authorisation design) |
| Sales | create (staff action) | Quotation (draft) | "Create draft quotation" button on Quotation tickets — never automatic |
| Service | TBD | (Maintenance Visit / Warranty Claim / custom) | Decide once BUC's ERPNext service process is defined |

## Activation checklist (future phase)

1. ERPNext production URL, version and DocTypes confirmed; API user created with least privilege.
2. Implement `FrappeRestERPNextAdapter` (HTTP client with timeouts, retries, error mapping) and
   select it in `get_erpnext_adapter()` when `BUC_ERPNEXT_BASE_URL` + credentials are set and
   a new setting `integrations.erpnext_enabled` is true.
3. Add worker job `sync_erpnext()` processing an outbox of sync requests.
4. Contract tests against an ERPNext staging site.
5. Field mapping configuration (local field → ERPNext field) stored per DocType.
