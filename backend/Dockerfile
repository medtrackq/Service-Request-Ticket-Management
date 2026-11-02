# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
RUN groupadd --system --gid 10001 buc && useradd --system --uid 10001 --gid buc --home /app buc

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY alembic.ini docker-entrypoint.sh ./
COPY alembic ./alembic
COPY app ./app

RUN mkdir -p /data/storage && chown -R buc:buc /data/storage
ENV BUC_STORAGE_DIR=/data/storage
VOLUME ["/data/storage"]

USER buc
EXPOSE 8000
ENTRYPOINT ["./docker-entrypoint.sh"]
# --proxy-headers + --forwarded-allow-ips: trust X-Forwarded-For only from the Nginx container network.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", \
     "--proxy-headers", "--forwarded-allow-ips", "*", "--no-server-header"]
