#!/usr/bin/env bash
# Backup the PostgreSQL database and the private attachment storage of the Docker Compose stack.
#
#   ./scripts/backup.sh [backup-dir]          (default: ./backups)
#
# Produces <dir>/buc-<timestamp>/{database.dump,storage.tar.gz,SHA256SUMS}.
# Schedule with cron, e.g. daily at 01:30:
#   30 1 * * * cd /opt/buc-service && ./scripts/backup.sh /srv/backups/buc >> /var/log/buc-backup.log 2>&1
# Copy backups off the server (encrypted) — a backup on the same disk is not a backup.
set -euo pipefail
cd "$(dirname "$0")/.."

DEST_ROOT="${1:-./backups}"
KEEP_DAYS="${BUC_BACKUP_KEEP_DAYS:-14}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DEST="${DEST_ROOT}/buc-${STAMP}"
COMPOSE="${COMPOSE:-docker compose}"

mkdir -p "$DEST"
umask 077

echo "[backup] database -> ${DEST}/database.dump"
$COMPOSE exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom --no-owner' > "${DEST}/database.dump"

echo "[backup] attachments -> ${DEST}/storage.tar.gz"
$COMPOSE exec -T api tar -C /data -czf - storage > "${DEST}/storage.tar.gz"

( cd "$DEST" && sha256sum database.dump storage.tar.gz > SHA256SUMS )

# Basic integrity check: the dump must be readable by pg_restore.
$COMPOSE exec -T db pg_restore --list < "${DEST}/database.dump" > /dev/null

echo "[backup] removing backups older than ${KEEP_DAYS} days in ${DEST_ROOT}"
find "$DEST_ROOT" -maxdepth 1 -type d -name 'buc-*' -mtime "+${KEEP_DAYS}" -exec rm -rf {} +

echo "[backup] done: ${DEST}"
