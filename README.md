# BUC Customer Service & Ticket Management System

ระบบบริการลูกค้าและจัดการ Ticket — **The Bangkok Unitrade Co., Ltd.**

A standalone full-stack web application. Customers submit requests from the
**LINE Official Account Rich Menu** (six URL buttons) or any browser. Every request becomes a
ticket with a unique number (`BUC-SRV-2026-00001`), is routed to the responsible department,
handled through a configurable workflow, and can be tracked by the customer with a secure
tracking link. ERPNext is **not** required; the architecture is prepared for a later
API-based ERPNext integration.

| | |
|---|---|
| Frontend | React + TypeScript + Tailwind CSS (mobile-first customer portal, desktop admin portal), Thai default / English |
| Backend | Python FastAPI + SQLAlchemy + Pydantic, REST API |
| Database | PostgreSQL 16 with Alembic migrations |
| Background jobs | PostgreSQL-backed outbox worker (e-mail, overdue alerts, retention) |
| Deployment | Docker Compose on Linux, Nginx reverse proxy with HTTPS |

## Features

* **Customer portal** — six request categories matching the LINE Rich Menu, dynamic 3-step forms,
  mobile camera / multi-image upload with previews (Service Request: up to 10 JPG/PNG, 10 MB each),
  privacy notice + consent, confirmation page with ticket number and tracking link.
* **Customer tracking** — ticket number + secret token; public timeline and staff updates only;
  customers can reply with more information/files when asked.
* **Ticket engine** — atomic, per-type, per-year numbering; idempotent submissions (no duplicates on
  double-tap/retry); all-or-nothing creation of ticket + attachments.
* **Ticket management** — search, filters, sorting, pagination, bulk assignment, CSV export; detail
  page with timeline, internal notes vs customer-visible updates, image gallery with full-screen viewer,
  assign / take / transfer / status actions driven by a configurable workflow.
* **Dashboard & reports** — KPI cards, charts, ticket summary, staff workload, performance (first
  response, resolution time, aging, overdue) against configurable internal targets.
* **Notifications** — in-app inbox, e-mail via SMTP with retries and failure logs; LINE Messaging API
  hook (disabled).
* **Administration** — users/roles/departments, request types, versioned form definitions, workflow
  transitions, assignment rules, settings, customers, audit logs, notification logs, integrations.
* **Security / PDPA** — Argon2id, server-side sessions + CSRF, RBAC on every endpoint, rate limiting,
  content-validated private uploads, audit logging, privacy notice versioning, retention/anonymisation.

## Repository layout

```
backend/            FastAPI application, Alembic migrations, tests (pytest)
frontend/           React SPA (customer portal + admin portal), Playwright E2E script
deploy/             Nginx config + web image Dockerfile, TLS certificate location
scripts/            backup.sh, restore.sh, gen-selfsigned-cert.sh
docs/               architecture, ERD, API spec, deployment, admin guide, reports, security, integrations
docker-compose.yml  db, api, worker, web (+ optional mailpit)
```

## Quick start (Docker)

```bash
cp .env.example .env                                   # set domain, secrets, SMTP
./scripts/gen-selfsigned-cert.sh localhost             # testing only; use a real certificate in production
docker compose up -d --build
docker compose exec api python -m app.cli create-admin --username admin --full-name "System Administrator"
```

Open `https://<domain>/` (customer portal) and `https://<domain>/admin` (staff).
Full instructions: **[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)**. Railway (PaaS): **[docs/RAILWAY.md](docs/RAILWAY.md)**.

## Development

```bash
# backend (PostgreSQL running locally)
cd backend && python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements-dev.txt
export BUC_DATABASE_URL=postgresql+psycopg://buc:<pw>@localhost:5432/buc_service
alembic upgrade head && python -m app.cli seed && python -m app.cli create-admin --username admin --full-name Admin
uvicorn app.main:app --reload --port 8000
python -m app.worker                                   # second terminal

# frontend
cd frontend && npm ci && npm run dev                   # http://localhost:5173

# tests
cd backend && BUC_TEST_DATABASE_URL=postgresql+psycopg://buc:<pw>@localhost:5432/buc_service_test pytest
cd frontend && npm run build && node e2e/portal-mobile.e2e.mjs    # with API + vite dev running
```

Sample/demo data (clearly flagged as sample): `python -m app.cli load-sample-data --tickets 60 --with-users`,
remove with `python -m app.cli purge-sample-data`.

## Documentation

| Document | Content |
|----------|---------|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System architecture, flows, RBAC, design decisions, versions |
| [docs/DATABASE.md](docs/DATABASE.md) | ERD, tables, constraints, ticket numbering, migrations |
| [docs/API.md](docs/API.md) + [docs/openapi.json](docs/openapi.json) | REST API specification |
| [docs/UI_STRUCTURE.md](docs/UI_STRUCTURE.md) | Screens and navigation of both portals |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | Linux/Docker/HTTPS deployment, backups, operations |
| [docs/RAILWAY.md](docs/RAILWAY.md) | Deploying to Railway (single service + PostgreSQL + volume) |
| [docs/ADMIN_GUIDE.md](docs/ADMIN_GUIDE.md) | Administrator user guide (Thai) |
| [docs/REPORTS.md](docs/REPORTS.md) | Dashboard/report calculation logic |
| [docs/SECURITY.md](docs/SECURITY.md) | Security controls and PDPA support |
| [docs/LINE_INTEGRATION.md](docs/LINE_INTEGRATION.md) | Rich Menu setup, optional LIFF, future Messaging API |
| [docs/ERPNEXT_INTEGRATION.md](docs/ERPNEXT_INTEGRATION.md) | Future ERPNext integration design |
| [docs/TESTING.md](docs/TESTING.md) | Automated tests and verification results |

## Status of optional / future items

| Item | Status |
|------|--------|
| LINE Rich Menu via URL actions | Ready (configure URLs from Admin → Integrations) |
| LINE Login / LIFF identity verification | Server-side verification implemented, disabled; not tested with a live channel; frontend LIFF SDK not included |
| LINE Messaging API push | Adapter implemented, disabled; not tested with a live Official Account |
| ERPNext integration | Interfaces, mapping tables and manual customer mapping only — no live synchronisation |
| Testing on physical iOS/Android devices inside the LINE app | Not performed — see docs/TESTING.md |
