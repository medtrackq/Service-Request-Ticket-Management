# Testing & Verification

## 1. Backend automated tests (pytest, real PostgreSQL)

```bash
cd backend
pip install -r requirements-dev.txt
# a dedicated, disposable database — the test run DROPS and recreates its schema
export BUC_TEST_DATABASE_URL=postgresql+psycopg://buc:<pw>@localhost:5432/buc_service_test
pytest
```

The schema is built with the Alembic migrations (so migrations are exercised on every run),
reference data is re-seeded before every test.

| File | Covers |
|------|--------|
| `test_ticket_numbers.py` | Format, per-type and per-year sequences (Bangkok year boundary), no reuse, **40 concurrent number allocations**, **16 concurrent full submissions**, **6 concurrent double-submits with the same idempotency key → 1 ticket** |
| `test_submission.py` | All six forms → correct prefix + default department; field mapping/normalisation; 0 and 10 images; >10 images rejected with nothing persisted; fake/truncated/oversized images; PNG disguised as JPG; PDF rules per form; duplicate files de-duplicated; idempotent replay; key reuse conflict; validation messages; consent; honeypot; outdated form version; customer de-duplication; notification outbox; rate limiting |
| `test_auth.py` | Login, generic errors, lockout, inactive users & session revocation, unauthenticated access, CSRF, forced password change, logout, idle timeout, hashed session tokens, Argon2id |
| `test_permissions.py` | Department scoping, staff queue setting, staff vs manager actions, self-assign, transfer with history, attachment access (staff/other department/anonymous), admin-only APIs, export/report restrictions, bulk-assign partial failures, staff uploads |
| `test_workflow.py` | Full lifecycle history (from/to/by/when/reason), skipping statuses, disallowed and role-restricted transitions, required comments, "request customer information", reopen, configurable workflow, internal vs public comments |
| `test_tracking.py` | Token required and bound to its ticket, no internal data leakage (notes, reasons, staff names, contact data), token regeneration revokes old link, customer reply with image limit, closed tickets |
| `test_notifications.py` | In-app inbox per department/assignee, worker SKIPPED without SMTP, successful send + token redaction, retry with backoff then FAILED without touching the ticket, admin retry, lease recovery, overdue notified once, PDPA retention anonymisation |
| `test_reports.py` | KPI counts, sample-data filter, resolution averages/medians, target-met %, aging buckets, overdue list, workload, summary, list filters/search/sort, CSV formula-injection guard |
| `test_admin.py` | User lifecycle with temporary passwords, settings validation, automatic assignment rules, form versioning, request type/department administration, integrations overview + manual ERPNext mapping, disabled ERPNext adapter, staff directory privacy |

**Result (development run):** `92 passed`.

## 2. Container / deployment verification (performed)

| Check | Result |
|-------|--------|
| `docker build` of the API image | OK (python:3.12-slim, non-root user) |
| `docker compose up` db + api + worker with `BUC_ENVIRONMENT=production` | Healthy; migrations + seed applied automatically |
| Service Request with 3 images inside the container | Ticket created, files in the private `storage` volume |
| E-mail via worker → SMTP (Mailpit) | Customer confirmation delivered (Thai subject/body); stored copy has the tracking token redacted |
| `scripts/backup.sh` | DB dump + storage tarball + checksums; dump verified with `pg_restore --list` |
| Restore after simulated data loss (`DELETE FROM tickets`, storage wiped) | `scripts/restore.sh` restored ticket and all attachments; numbering continued at the next number |

## 3. Frontend & end-to-end tests

See section 4 (filled in from the E2E run).

## 4. Mobile / browser verification

FRONTEND_E2E_RESULTS

## 5. Not verified (requires real devices / accounts)

* Upload from the **LINE in-app browser** on physical iOS and Android phones (camera capture,
  photo library, HEIC conversion). The implementation follows standard `<input type="file">`
  behaviour supported by LINE's in-app browser, and was tested only with Playwright device
  emulation. **Run the manual checklist below before go-live.**
* LINE Login/LIFF verification and Messaging API push against live LINE channels.
* Load/performance testing at production volume.

### Manual go-live checklist (each on iPhone + Android, inside LINE)

1. Open each of the six Rich Menu buttons → correct form opens over HTTPS without certificate warnings.
2. Service Request: take a photo with the camera, add photos from the gallery (select several at once),
   remove one, replace one, see the counter `n/10`, try to exceed 10 → warning.
3. Submit on a slow mobile connection; tap submit twice → only one ticket number.
4. Copy the tracking link, open it later from LINE chat → status visible.
5. Staff opens the ticket on desktop → all photos visible full-screen and downloadable.
