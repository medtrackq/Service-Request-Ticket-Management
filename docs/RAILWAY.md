# Deploying to Railway

Railway hosts the system as **one application service + one PostgreSQL database + one volume**.
The on-premise Docker Compose set-up ([DEPLOYMENT.md](DEPLOYMENT.md)) is unchanged; Railway uses
a separate single-service image:

| Piece | On-prem (Docker Compose) | Railway |
|-------|--------------------------|---------|
| HTTPS / TLS | Nginx + your certificate | Railway edge (automatic certificate) |
| SPA (React build) | Nginx | FastAPI serves `/app/static` (`BUC_STATIC_DIR`) with the same CSP/HSTS headers |
| Background worker | separate `worker` container | thread inside the API process (`BUC_RUN_WORKER_IN_PROCESS=true`) |
| Database | `db` container | Railway PostgreSQL (`DATABASE_URL`) |
| Attachments | `storage` Docker volume | Railway volume mounted at `/data/storage` |
| Client IP for rate limits/audit | Nginx-overwritten `X-Forwarded-For` | `X-Real-IP` set by Railway's edge (`BUC_CLIENT_IP_HEADER`) |
| First administrator | `python -m app.cli create-admin` | `BUC_BOOTSTRAP_ADMIN_*` variables (forced password change) |

Files: `railway.toml` (build + health check), `deploy/railway/Dockerfile`, `deploy/railway/start.sh`.

## 1. Create the services

Dashboard (or the CLI equivalents in brackets):

1. **New project** (`railway init`).
2. **+ New → Database → PostgreSQL** (`railway add --database postgres`).
3. **+ New → GitHub repo → `medtrackq/Service-Request-Ticket-Management`** — or an empty service
   deployed from a local checkout with `railway up`. Railway picks up `railway.toml` and builds
   `deploy/railway/Dockerfile`.
4. On the app service: **Settings → Volumes → Add volume**, mount path **`/data/storage`**
   (`railway volume add`).
5. **Settings → Networking → Generate domain** (`railway domain`), or add your custom domain.

## 2. Variables (app service)

| Variable | Value |
|----------|-------|
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` (reference to the database service) |
| `BUC_ENVIRONMENT` | `production` |
| `BUC_SECRET_KEY` | long random value, e.g. `python3 -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `BUC_COOKIE_SECURE` | `true` |
| `BUC_CLIENT_IP_HEADER` | `X-Real-IP` |
| `BUC_BOOTSTRAP_ADMIN_USERNAME` | e.g. `admin` (first start only) |
| `BUC_BOOTSTRAP_ADMIN_PASSWORD` | temporary password (≥ 10 chars, letters + digits/symbols); must be changed at first login |
| `BUC_PUBLIC_BASE_URL` | optional — defaults to `https://$RAILWAY_PUBLIC_DOMAIN`; set it when you use a custom domain |
| `BUC_SMTP_*` | optional, e-mail relay (see `.env.example`) |

After the first successful login, delete the two `BUC_BOOTSTRAP_ADMIN_*` variables. They never
overwrite or recreate users: the bootstrap only runs while no administrator exists.

## 3. Deploy and verify

* Every start runs migrations, the idempotent seed and the optional bootstrap, then starts the API
  on `$PORT` with the worker thread. Railway's health check calls `/api/health`.
* Open `https://<domain>/admin/login`, sign in with the bootstrap account, change the password.
* LINE Rich Menu URLs are listed under **Admin → Integrations** (built from the public URL).

## 4. Operations

| Task | How |
|------|-----|
| Logs | Railway dashboard → service → Deployments / Logs (`railway logs`) |
| Redeploy | push to the connected branch, or `railway up` |
| Database backup | Railway PostgreSQL backups (dashboard) and/or `pg_dump "$DATABASE_PUBLIC_URL" -Fc > buc.dump` from a trusted machine |
| Attachment backup | volume backups in the Railway dashboard (where available for the plan) |
| Sample data | not on production |

## Notes and limitations

* A service with a volume is redeployed with a short downtime (no overlap of old/new instances).
* The image starts as root only to take ownership of the root-mounted volume, then drops to the
  unprivileged `buc` user (`setpriv`) before running migrations and the server.
* Single API process: the in-process rate limiter and worker assume one replica. Do not scale the
  service to several replicas without moving the worker to its own service.
* Railway documents `X-Real-IP` as the client-IP header set by its edge (overwriting any value a
  client sends). Requests over Railway's private network bypass the edge, so do not expose the app
  to other untrusted services in the same project.
