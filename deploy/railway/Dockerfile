# syntax=docker/dockerfile:1
# Single-service image for PaaS hosting (Railway): FastAPI serves the API *and* the built SPA,
# and runs the background worker in-process. Docker Compose (on-prem) keeps using
# backend/Dockerfile + deploy/web/Dockerfile (Nginx) instead.
# Build context: repository root.

FROM node:22-alpine AS web
WORKDIR /src
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    BUC_STORAGE_DIR=/data/storage \
    BUC_STATIC_DIR=/app/static \
    BUC_RUN_WORKER_IN_PROCESS=true

WORKDIR /app
RUN groupadd --system --gid 10001 buc && useradd --system --uid 10001 --gid buc --home /app buc

COPY backend/requirements.txt .
RUN pip install -r requirements.txt

COPY backend/alembic.ini backend/docker-entrypoint.sh ./
COPY backend/alembic ./alembic
COPY backend/app ./app
COPY deploy/railway/start.sh ./start.sh
COPY --from=web /src/dist ./static
RUN chmod 0755 start.sh docker-entrypoint.sh && mkdir -p /data/storage && chown buc:buc /data/storage

# Starts as root only to take ownership of the (root-mounted) volume, then drops to user "buc".
ENTRYPOINT ["./start.sh"]
# One process: the in-process rate limiter and worker thread assume a single API process.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port \"${PORT:-8000}\" --workers 1 --proxy-headers --forwarded-allow-ips '*' --no-server-header"]
