#!/bin/sh
# Waits for PostgreSQL, applies migrations and reference data, then starts the given command.
set -e
python - <<'PY'
import os, sys, time
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from app.config import get_settings
url = make_url(get_settings().database_url)
# Never print the password: host/port/database only.
print(f"database target: {url.host}:{url.port or 5432}/{url.database}", flush=True)
if url.host in ("localhost", "127.0.0.1") and os.environ.get("RAILWAY_ENVIRONMENT"):
    print("HINT: DATABASE_URL is not set for this service. On Railway add the variable "
          "DATABASE_URL = ${{Postgres.DATABASE_URL}} (Variables > Add Variable Reference).", flush=True)
engine = create_engine(url)
for attempt in range(60):
    try:
        with engine.connect() as c:
            c.execute(text("SELECT 1"))
        print("database reachable", flush=True)
        break
    except Exception as exc:  # noqa: BLE001
        detail = (str(getattr(exc, "orig", None) or exc).strip().splitlines() or [""])[0][:300]
        print(f"waiting for database ({exc.__class__.__name__}: {detail})", flush=True)
        time.sleep(2)
else:
    sys.exit("database not reachable")
PY
if [ "${BUC_RUN_MIGRATIONS:-1}" = "1" ]; then
  alembic upgrade head
  python -m app.cli seed
  python -m app.cli bootstrap-admin   # no-op unless BUC_BOOTSTRAP_ADMIN_* are set
fi
exec "$@"
