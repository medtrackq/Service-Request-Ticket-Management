# Security & Personal Data Protection

## Controls implemented

| Area | Control | Where |
|------|---------|-------|
| Transport | HTTPS only (HTTP → 301), HSTS, TLS 1.2/1.3 | `deploy/nginx` |
| Headers | CSP (`script-src 'self'`), X-Frame-Options DENY, nosniff, Referrer-Policy no-referrer, Permissions-Policy | Nginx snippet + API middleware |
| Authentication | Argon2id password hashing; generic login errors; 5 failures → 15 min lockout; password policy; forced change of temporary passwords | `security/passwords.py`, `routes/auth.py` |
| Sessions | Random 256-bit token in httpOnly + Secure + SameSite=Lax cookie; only SHA-256 stored; idle (60 min) and absolute (12 h) expiry; revoked on logout, deactivation and password reset | `security/sessions.py` |
| CSRF | Per-session token required in `X-CSRF-Token` for all state-changing staff requests | `api/deps.py` |
| Authorisation | Server-side RBAC + department scoping on every endpoint; out-of-scope tickets return 404 | `security/permissions.py` |
| Customer access | Ticket number **and** 256-bit tracking token (hash stored, revocable, optional expiry, sent in URL fragment); customer view excludes internal notes, assignment data and staff identities | `services/tracking.py` |
| Injection | SQLAlchemy parameterised queries only; LIKE patterns escaped | services |
| XSS | React escapes output; no `dangerouslySetInnerHTML`; e-mails are plain text; CSP | frontend, notifications |
| Uploads | Size cap while streaming; type from magic bytes (not extension); full image decode with decompression-bomb guard; random stored names; private volume; download only through authorised endpoint with `nosniff` and sandbox CSP; PDFs always downloaded, never rendered inline | `services/files.py` |
| Abuse | Per-IP rate limits (Nginx + API), honeypot field, idempotency keys, request body limit | `security/rate_limit.py`, Nginx |
| CSV export | UTF-8 with BOM, formula-injection neutralisation | `api/csv_utils.py` |
| Audit | Logins (success/failure/lockout), ticket creation/changes, exports, downloads, all admin changes | `audit_logs` |
| Secrets | Environment variables only (`.env`, not committed); production start-up refuses insecure defaults | `config.py` |
| Errors | Uniform error body; stack traces only in server logs | `main.py` |

## PDPA (Thailand Personal Data Protection Act B.E. 2562)

The system provides technical support for compliance; legal review of texts and retention
periods is BUC's responsibility.

| Requirement | Support in the system |
|-------------|----------------------|
| Notice / transparency | Privacy notice page (`/privacy`), editable TH/EN text with version (`privacy.notice_*`). **The default text is a template and must be reviewed by BUC's DPO/legal team.** |
| Consent / acknowledgement record | Submission requires acknowledgement; notice version and timestamp stored per ticket |
| Data minimisation | Only contact fields needed to handle the request; e-mail, department and organisation type optional |
| Access control | RBAC, department scoping, audit trail of downloads/exports |
| Retention | `privacy.retention_days`: worker anonymises contact data, deletes attachments and revokes tracking links of tickets closed/cancelled longer than N days (0 = disabled until BUC defines the period). `audit.retention_days` for audit logs |
| Data subject requests | Admin can locate a customer's data (Customers page, ticket search by name/phone) and edit it; anonymisation is automated via retention — a per-person "erase now" action is a recommended follow-up |
| Security of processing | See controls above; encrypted backups recommended |

### Known limitations / recommendations

* Uploaded photos keep their original metadata (EXIF, may include GPS). Consider stripping EXIF
  if photos could contain location data that must not be kept.
* Rate limits in the API are per process; Nginx limits are the primary defence.
* No multi-factor authentication for staff yet — recommended next step for administrator accounts.
* No antivirus scan of PDFs; PDFs are never rendered inline by the application. Add ClamAV if
  required by policy.
