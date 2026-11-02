# Deployment Guide (Linux, Docker Compose, HTTPS)

## 1. Server requirements

* Linux x86-64 (Ubuntu 22.04/24.04 LTS, Debian 12, RHEL 9 or similar), 2 vCPU, 4 GB RAM,
  40 GB disk minimum (attachments grow ~ up to 100 MB per Service Request with 10 photos;
  size the `storage` volume accordingly).
* Docker Engine 24+ with the Compose plugin (`docker compose version`).
* A DNS name (e.g. `service.bangkokunitrade.example`) pointing to the server, ports 80/443 open.
* A **publicly trusted** TLS certificate (Let's Encrypt or corporate CA). LINE's in-app browser
  does not accept self-signed certificates.
* Outbound SMTP access if e-mail notifications are wanted.

## 2. First installation

```bash
sudo mkdir -p /opt/buc-service && sudo chown "$USER" /opt/buc-service
git clone https://github.com/medtrackq/service-request-ticket-management /opt/buc-service
cd /opt/buc-service
cp .env.example .env
chmod 600 .env
```

Edit `.env`:

| Variable | Value |
|----------|-------|
| `BUC_PUBLIC_BASE_URL` | `https://<your-domain>` — used in tracking links and LINE Rich Menu URLs |
| `SERVER_NAME` | `<your-domain>` |
| `BUC_SECRET_KEY` | output of `python3 -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `POSTGRES_PASSWORD` | a long random password |
| `BUC_SMTP_*` | your mail relay (leave `BUC_SMTP_HOST` empty to disable e-mail) |

The API refuses to start in `production` with the default secret, without `BUC_COOKIE_SECURE=true`
or with a non-HTTPS public URL.

### TLS certificate

Option A — existing certificate: copy `fullchain.pem` and `privkey.pem` to `deploy/certs/`.

Option B — Let's Encrypt (certbot on the host, standalone mode during installation):

```bash
sudo apt install certbot
sudo certbot certonly --standalone -d <your-domain>
sudo cp /etc/letsencrypt/live/<your-domain>/fullchain.pem deploy/certs/
sudo cp /etc/letsencrypt/live/<your-domain>/privkey.pem deploy/certs/
sudo chown "$USER" deploy/certs/*.pem && chmod 600 deploy/certs/privkey.pem
```

Renewal (webroot mode, while the stack runs — Nginx serves `/.well-known/acme-challenge/`
from the `certbot-webroot` volume):

```bash
sudo certbot renew --webroot -w "$(docker volume inspect -f '{{.Mountpoint}}' buc-service_certbot-webroot)" \
  --deploy-hook "cp /etc/letsencrypt/live/<your-domain>/*.pem /opt/buc-service/deploy/certs/ && \
                 docker compose -f /opt/buc-service/docker-compose.yml exec web nginx -s reload"
```

Option C — internal test only: `./scripts/gen-selfsigned-cert.sh <hostname>`.

### Start

```bash
docker compose up -d --build
docker compose ps                     # db, api, worker, web should be healthy/running
docker compose logs -f api            # migrations + seed run automatically on first start
```

Create the first administrator (prompted for a password; must be ≥ 10 characters, letters + digits/symbols):

```bash
docker compose exec api python -m app.cli create-admin \
  --username admin --full-name "System Administrator" --email it@bangkokunitrade.example
```

Open `https://<your-domain>/admin/login`, then follow the [Administrator Guide](ADMIN_GUIDE.md):
create departments' users, review the privacy notice and service targets, and configure the
LINE Rich Menu ([LINE_INTEGRATION.md](LINE_INTEGRATION.md)).

## 3. Operations

| Task | Command |
|------|---------|
| Status / logs | `docker compose ps`, `docker compose logs -f api worker web` |
| Restart | `docker compose restart api worker` |
| Upgrade | `git pull && docker compose up -d --build` (migrations run on api start) |
| Backup | `./scripts/backup.sh /srv/backups/buc` |
| Restore | `./scripts/restore.sh /srv/backups/buc/buc-<timestamp>` |
| DB shell | `docker compose exec db psql -U buc buc_service` |
| Test e-mail locally | `docker compose --profile mail up -d mailpit`, set `BUC_SMTP_HOST=mailpit`, `BUC_SMTP_PORT=1025`, `BUC_SMTP_STARTTLS=false`; UI on `http://127.0.0.1:8025` |
| Demo data (non-production!) | `docker compose exec api python -m app.cli load-sample-data --tickets 60 --with-users` / `purge-sample-data` |

### Backups

`scripts/backup.sh` writes a PostgreSQL custom-format dump plus a tarball of the attachment
volume and SHA-256 checksums, verifies that the dump is readable, and prunes backups older
than `BUC_BACKUP_KEEP_DAYS` (default 14). Schedule it with cron and **copy backups off the
server** (encrypted). Test a restore on a staging machine regularly — the restore procedure was
verified during development (see [TESTING.md](TESTING.md)).

```cron
30 1 * * * cd /opt/buc-service && ./scripts/backup.sh /srv/backups/buc >> /var/log/buc-backup.log 2>&1
```

### Monitoring

* `GET https://<your-domain>/api/health` → `{"status":"ok"}` (checks DB connectivity).
* Docker health checks on `db` and `api`.
* Admin → Notification logs: FAILED e-mails (SMTP problems).
* Admin → Audit logs: logins, failed logins, exports, administration changes.

## 4. Network & security notes

* Only `web` publishes ports. `api`, `worker` and `db` are reachable only on internal networks.
* Nginx overwrites `X-Forwarded-For` with the real client address; the API trusts proxy headers
  only because it is not reachable directly. If you put another load balancer in front of Nginx,
  configure `set_real_ip_from`/`real_ip_header` in Nginx accordingly.
* Uploads up to 110 MB per request are accepted by Nginx; per-file (10 MB) and per-ticket
  (10 images) limits are enforced by the API.
* Interactive API docs (`/api/docs`) are disabled when `BUC_ENVIRONMENT=production`.
* Keep the host patched; restrict SSH; enable a host firewall (allow 80/443 and SSH from admin
  networks only).

## 5. Running without Docker (development)

```bash
# PostgreSQL 16 running locally; create role/db buc / buc_service
cd backend
python3.12 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
export BUC_DATABASE_URL=postgresql+psycopg://buc:<pw>@localhost:5432/buc_service
alembic upgrade head && python -m app.cli seed
python -m app.cli create-admin --username admin --full-name "Admin"
uvicorn app.main:app --reload --port 8000        # API
python -m app.worker                              # worker (separate terminal)

cd ../frontend && npm ci && npm run dev           # http://localhost:5173 (proxies /api to :8000)
```
