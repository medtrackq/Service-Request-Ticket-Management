#!/usr/bin/env bash
# Restore a backup produced by scripts/backup.sh into the Docker Compose stack.
#
#   ./scripts/restore.sh ./backups/buc-20261102T013000Z
#
# DESTRUCTIVE: replaces the current database contents and attachment storage.
set -euo pipefail
cd "$(dirname "$0")/.."

SRC="${1:?usage: restore.sh <backup-dir>}"
COMPOSE="${COMPOSE:-docker compose}"

[ -f "${SRC}/database.dump" ] || { echo "missing ${SRC}/database.dump"; exit 1; }
[ -f "${SRC}/storage.tar.gz" ] || { echo "missing ${SRC}/storage.tar.gz"; exit 1; }
( cd "$SRC" && sha256sum -c SHA256SUMS )

if [ "${BUC_RESTORE_CONFIRM:-}" != "yes" ]; then
  read -r -p "This will OVERWRITE the database and attachments. Type 'yes' to continue: " answer
  [ "$answer" = "yes" ] || { echo "aborted"; exit 1; }
fi

echo "[restore] stopping api, worker and web"
$COMPOSE stop web worker api

echo "[restore] database"
$COMPOSE exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner --single-transaction' < "${SRC}/database.dump"

echo "[restore] attachments"
$COMPOSE run --rm --no-deps --no-build -T --entrypoint sh api -c 'find /data/storage -mindepth 1 -delete && tar -C /data -xzf -' < "${SRC}/storage.tar.gz"

echo "[restore] starting services (migrations run automatically on api start)"
$COMPOSE up -d --no-build api worker web
echo "[restore] done"
