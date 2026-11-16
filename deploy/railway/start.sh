#!/bin/sh
# Railway mounts volumes owned by root. Take ownership of the storage directory once,
# then re-exec as the unprivileged "buc" user and continue with the normal entrypoint
# (wait for DB, migrations, seed, optional bootstrap admin, start the server).
set -e
STORAGE="${BUC_STORAGE_DIR:-/data/storage}"
if [ "$(id -u)" = "0" ]; then
  mkdir -p "$STORAGE"
  if [ "$(stat -c %u "$STORAGE")" != "10001" ]; then
    chown -R buc:buc "$STORAGE"
  fi
  exec setpriv --reuid=buc --regid=buc --init-groups --inh-caps=-all "$0" "$@"
fi
exec ./docker-entrypoint.sh "$@"
