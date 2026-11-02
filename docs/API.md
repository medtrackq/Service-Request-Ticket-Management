# REST API Specification

* Base path: `/api/v1` (health check: `GET /api/health`)
* Machine-readable spec: [`openapi.json`](openapi.json) (regenerate with `python -m app.cli export-openapi ../docs/openapi.json`).
  In non-production environments interactive docs are served at `/api/docs`.
* Content type: JSON, except uploads (`multipart/form-data`) and CSV exports.
* Times: ISO-8601 UTC (`2026-11-02T09:28:43Z`); clients display Asia/Bangkok.

## Conventions

### Authentication (staff)

1. `POST /auth/login` → sets `buc_session` (httpOnly, Secure, SameSite=Lax, path `/api`) and returns `csrf_token`.
2. Every non-GET request must send header `X-CSRF-Token: <csrf_token>`; `GET /auth/me` returns it again after a page reload.
3. Sessions expire after `BUC_SESSION_IDLE_MINUTES` of inactivity or `BUC_SESSION_ABSOLUTE_HOURS`.
4. Five failed logins lock the account for `BUC_LOGIN_LOCKOUT_MINUTES` (HTTP 423).
5. Users flagged `must_change_password` receive `403 PASSWORD_CHANGE_REQUIRED` everywhere except `/auth/*`.

### Errors

```json
{ "detail": { "code": "VALIDATION_ERROR", "message": "กรุณาตรวจสอบข้อมูลในแบบฟอร์ม",
              "fields": { "phone": "รูปแบบเบอร์โทรศัพท์ไม่ถูกต้อง" } } }
```

| HTTP | Typical codes |
|------|---------------|
| 401 | `UNAUTHENTICATED`, `INVALID_CREDENTIALS` |
| 403 | `CSRF_FAILED`, `FORBIDDEN`, `PASSWORD_CHANGE_REQUIRED`, `TRANSITION_ROLE_FORBIDDEN` |
| 404 | `NOT_FOUND`, `TICKET_NOT_FOUND` (also returned for tickets outside the caller's scope), `TRACKING_NOT_FOUND` |
| 409 | `FORM_VERSION_CHANGED`, `IDEMPOTENCY_KEY_REUSED`, `TICKET_CLOSED`, `CONFLICT` |
| 413 | `PAYLOAD_TOO_LARGE` |
| 422 | `VALIDATION_ERROR`, `TOO_MANY_FILES`, `TRANSITION_NOT_ALLOWED`, `SPAM_DETECTED`, `WEAK_PASSWORD` |
| 423 | `ACCOUNT_LOCKED` |
| 429 | `RATE_LIMITED` (with `Retry-After`) |

## Public (customer) endpoints — no login

| Method | Path | Description |
|--------|------|-------------|
| GET | `/public/portal` | Portal texts (company, welcome, contact), active request types, LIFF flag |
| GET | `/public/privacy-notice` | Privacy notice (TH/EN) and version |
| GET | `/public/forms/{slug}` | Active form definition: fields, validation, options, `file_rules` |
| POST | `/public/requests/{slug}` | Submit a request → creates a ticket |
| POST | `/public/track` | Customer-safe ticket view (ticket number + token) |
| POST | `/public/track/reply` | Customer adds information/files to an open ticket |

`slug` ∈ `product`, `delivery`, `service`, `quotation`, `accounting`, `general`.

### Submit a request

```
POST /api/v1/public/requests/service
Idempotency-Key: 6f1c0f0e2c3b4a8d9e7f6a5b4c3d2e1f      (16–64 chars [A-Za-z0-9_-], one per form session)
Content-Type: multipart/form-data

payload = {"form_definition_id": 3, "privacy_consent": true,
           "values": {"organization": "โรงพยาบาลตัวอย่าง", "contact_name": "สมชาย", "phone": "081-234-5678",
                      "equipment_type": "MEDICAL_DEVICE", "equipment_name": "Infusion Pump",
                      "problem_type": "EQUIPMENT_FAILURE", "problem_description": "…", "urgency": "HIGH"}}
files   = photo1.jpg, photo2.png, …   (Service: JPG/PNG only, ≤ 10 files, ≤ 10 MB each)
```

`201 Created` (first submission) / `200 OK` (replay of the same Idempotency-Key):

```json
{ "ticket_number": "BUC-SRV-2026-00001", "request_type_code": "SERVICE",
  "subject": "แจ้งซ่อม: Infusion Pump - เครื่องเสีย / ใช้งานไม่ได้",
  "created_at": "2026-11-02T09:28:43Z", "attachments": 4, "replayed": false,
  "tracking_token": "YTMzw9wDEi5g…",
  "tracking_url": "https://service.example.com/track/BUC-SRV-2026-00001#t=YTMzw9wDEi5g…" }
```

A hidden honeypot value `payload.website` must be empty. The optional `payload.line_id_token`
(LIFF ID token) is verified server-side when LINE Login is configured.

### Track

```
POST /api/v1/public/track   {"ticket_number": "BUC-SRV-2026-00001", "token": "YTMzw9wDEi5g…"}
```

Returns ticket number, request type, subject, created date, current status and a public
timeline (`STATUS` entries and `MESSAGE` entries authored by `STAFF` or `CUSTOMER`).
Internal notes, assignment data and staff names are never included. Wrong/missing token → 404.

## Staff endpoints (login required)

| Method | Path | Notes |
|--------|------|-------|
| POST | `/auth/login` · `/auth/logout` · `/auth/change-password` | |
| GET | `/auth/me` | user, permissions, `csrf_token` |
| GET | `/lookups` | departments, request types, statuses, priorities, staff directory (no contact data) |
| GET | `/tickets` | filters: `q`, `status` (comma list), `status_category` (`ACTIVE`/NEW/OPEN/WAITING/RESOLVED/CLOSED/CANCELLED), `request_type`, `department_id`, `assigned` (`me`/`none`/id), `priority`, `date_from`, `date_to`, `overdue`, `include_sample`; `sort` (`created_at`, `last_activity_at`, `ticket_number`, `priority`, `status`, `due_at`), `direction`, `page`, `page_size` ≤ 100 |
| GET | `/tickets/export.csv` | same filters; ADMIN/MANAGER; UTF-8 BOM; formula-injection safe |
| POST | `/tickets/bulk-assign` | `{ticket_ids[], department_id?, assigned_user_id?, priority?, due_at?, reason?}`; ADMIN/MANAGER; per-ticket result |
| GET | `/tickets/{id}` | full detail + `allowed_transitions` + `permissions` |
| POST | `/tickets/{id}/status` | `{to_status, comment?, public_message?}` — `public_message` becomes a customer-visible update; required for `WAITING_CUSTOMER` |
| POST | `/tickets/{id}/assign` | `{department_id?, assigned_user_id?, unassign?, priority?, due_at?, reason?}` — transfer when department changes |
| POST | `/tickets/{id}/comments` | `{body, visibility: INTERNAL\|PUBLIC}` |
| POST | `/tickets/{id}/attachments` | multipart `files` (JPG/PNG/PDF, ≤ 10 per upload) |
| POST | `/tickets/{id}/tracking-token` | revoke old links, return a new tracking link (shown once) |
| GET | `/attachments/{uuid}` | authorised file stream; images inline, `?download=true` forces download (audited) |
| GET | `/dashboard` | KPIs + chart series (same filters as `/tickets`) |
| GET | `/reports/summary` · `/reports/workload` · `/reports/performance` | `?format=csv` for download; ADMIN/MANAGER |
| GET | `/notifications` · `/notifications/unread-count` | in-app inbox |
| POST | `/notifications/{id}/read` · `/notifications/read-all` | |

## Administration (ADMIN only)

| Method | Path |
|--------|------|
| GET/POST | `/admin/users` · PATCH `/admin/users/{id}` · POST `/admin/users/{id}/reset-password` |
| GET/POST | `/admin/departments` · PATCH `/admin/departments/{id}` |
| GET | `/admin/request-types` · PATCH `/admin/request-types/{id}` |
| GET/POST | `/admin/request-types/{id}/forms` (POST publishes a new form version) |
| GET | `/admin/workflow` · PATCH `/admin/workflow/statuses/{code}` · PUT `/admin/workflow/transitions` |
| GET/POST | `/admin/assignment-rules` · PUT/DELETE `/admin/assignment-rules/{id}` |
| GET | `/admin/settings` · PUT `/admin/settings/{key}` `{value}` |
| GET | `/admin/audit-logs` |
| GET | `/admin/notification-logs` · POST `/admin/notification-logs/{id}/retry` |
| GET | `/admin/integrations` · `/admin/integrations/mappings` · `/admin/integrations/logs`; POST `/admin/integrations/mappings` |
| GET | `/admin/customers` · `/admin/customers/{id}/contacts`; PATCH `/admin/customers/{id}` |

### Form version payload (`POST /admin/request-types/{id}/forms`)

```json
{ "title_th": "แบบฟอร์มติดต่อเจ้าหน้าที่", "title_en": "General Contact Form",
  "subject_template": "{subject}",
  "fields": [
    {"key": "organization", "section": "customer", "field_type": "text", "label_th": "…", "label_en": "…",
     "required": true, "maps_to": "customer.name", "validation": {"max_length": 255}},
    {"key": "attachments", "section": "attachments", "field_type": "file", "label_th": "…", "label_en": "…",
     "maps_to": "ticket.attachments",
     "validation": {"max_files": 5, "max_size_mb": 10, "accept": ["image/jpeg", "image/png", "application/pdf"]}}
  ] }
```

Field types: `text`, `textarea`, `number`, `date`, `select`, `email`, `tel`, `file` (max one).
Validation keys: `max_length`, `min_length`, `pattern`, `min`, `max`, `integer`, `not_future`,
`not_past`, `max_files` (1–10), `max_size_mb`, `accept`. Required mappings: `customer.name`,
`contact.name`, `contact.phone`, `ticket.description`.
