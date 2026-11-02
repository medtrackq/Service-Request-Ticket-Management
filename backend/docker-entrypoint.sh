#!/bin/sh
# Waits for PostgreSQL, applies migrations and reference data, then starts the given command.
set -e
python - <<'PY'
import time, sys
from sqlalchemy import create_engine, text
from app.config import get_settings
engine = create_engine(get_settings().database_url)
for attempt in range(60):
    try:
        with engine.connect() as c:
            c.execute(text("SELECT 1"))
        break
    except Exception as exc:  # noqa: BLE001
        print(f"waiting for database ({exc.__class__.__name__})", flush=True)
        time.sleep(2)
else:
    sys.exit("database not reachable")
PY
if [ "${BUC_RUN_MIGRATIONS:-1}" = "1" ]; then
  alembic upgrade head
  python -m app.cli seed
fi
exec "$@"
