"""Single-service hosting (Railway): SPA serving, client IP header, bootstrap admin, env handling."""
from __future__ import annotations

import os
import time

from sqlalchemy import select

from app.config import Settings, get_settings
from app.models import AuditLog, User
from tests.conftest import login, make_user


def test_spa_routes_and_assets(client):
    for path in ("/", "/request/service", "/track/BUC-SRV-2026-00001", "/admin/tickets/5"):
        r = client.get(path)
        assert r.status_code == 200 and "BUC SPA" in r.text, path
        assert r.headers["cache-control"] == "no-cache"
        assert "frame-ancestors 'none'" in r.headers["content-security-policy"]
    a = client.get("/assets/app-123.js")
    assert a.status_code == 200 and "immutable" in a.headers["cache-control"]
    assert client.get("/favicon.svg").headers["content-type"].startswith("image/svg")
    assert client.get("/assets/missing.js").status_code == 404


def test_spa_does_not_shadow_or_leak(client):
    r = client.get("/api/v1/does-not-exist")
    assert r.status_code == 404 and r.json()["detail"]["code"] == "HTTP_ERROR"
    assert client.get("/api/health").json() == {"status": "ok"}
    # path traversal outside the static root falls back to index.html, never a file outside it
    r = client.get("/..%2F..%2Fetc%2Fpasswd")
    assert "root:" not in r.text
    assert "content-security-policy" not in client.get("/api/health").headers  # SPA headers only on pages


def test_client_ip_header(client, db, monkeypatch):
    make_user("ipuser")
    monkeypatch.setattr(get_settings(), "client_ip_header", "X-Real-IP")
    client.post("/api/v1/auth/login", json={"username": "ipuser", "password": "wrong"},
                headers={"X-Real-IP": "203.0.113.7"})
    ip = db.scalar(select(AuditLog.ip_address).where(AuditLog.action == "auth.login_failed"))
    assert ip == "203.0.113.7"
    monkeypatch.setattr(get_settings(), "client_ip_header", "")
    client.post("/api/v1/auth/login", json={"username": "ipuser", "password": "wrong"},
                headers={"X-Real-IP": "198.51.100.9"})
    ips = db.scalars(select(AuditLog.ip_address).where(AuditLog.action == "auth.login_failed")).all()
    assert "198.51.100.9" not in ips  # header ignored unless explicitly trusted


def test_bootstrap_admin(db, monkeypatch, capsys):
    from app.cli import cmd_bootstrap_admin

    cmd_bootstrap_admin(None)  # no variables -> no-op
    assert db.scalar(select(User.id)) is None
    monkeypatch.setenv("BUC_BOOTSTRAP_ADMIN_USERNAME", "weak")
    monkeypatch.setenv("BUC_BOOTSTRAP_ADMIN_PASSWORD", "short")
    cmd_bootstrap_admin(None)  # weak password -> warning, no exit, no user
    assert "NOT created" in capsys.readouterr().out
    assert db.scalar(select(User.id)) is None
    monkeypatch.setenv("BUC_BOOTSTRAP_ADMIN_USERNAME", "Railway.Admin")
    monkeypatch.setenv("BUC_BOOTSTRAP_ADMIN_PASSWORD", "Temp-Admin-Pass-99")
    cmd_bootstrap_admin(None)
    user = db.scalar(select(User).where(User.username == "railway.admin"))
    assert user.role == "ADMIN" and user.must_change_password is True
    s = login("railway.admin", "Temp-Admin-Pass-99")
    assert s.get("/api/v1/tickets").json()["detail"]["code"] == "PASSWORD_CHANGE_REQUIRED"
    monkeypatch.setenv("BUC_BOOTSTRAP_ADMIN_USERNAME", "second")
    cmd_bootstrap_admin(None)  # an admin exists -> never creates another
    assert "already exists" in capsys.readouterr().out
    assert db.scalar(select(User).where(User.username == "second")) is None


def test_paas_environment_variables(monkeypatch):
    for k in ("BUC_DATABASE_URL", "BUC_PUBLIC_BASE_URL"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgres://u:p@db.internal:5432/railway")
    monkeypatch.setenv("RAILWAY_PUBLIC_DOMAIN", "buc.up.railway.app")
    s = Settings(_env_file=None)
    assert s.database_url == "postgresql+psycopg://u:p@db.internal:5432/railway"
    assert s.public_base_url == "https://buc.up.railway.app"
    monkeypatch.setenv("BUC_PUBLIC_BASE_URL", "https://service.example.com/")
    assert Settings(_env_file=None).public_base_url == "https://service.example.com"


def test_worker_thread_starts_and_stops():
    from app.worker import start_background_thread

    thread, stop = start_background_thread()
    time.sleep(0.3)
    assert thread.is_alive()
    stop.set()
    thread.join(timeout=10)
    assert not thread.is_alive()
    assert os.environ.get("BUC_RUN_WORKER_IN_PROCESS") in (None, "", "0", "false")


def test_public_url_normalisation_and_production_hint(monkeypatch):
    import pytest

    monkeypatch.delenv("RAILWAY_PUBLIC_DOMAIN", raising=False)
    monkeypatch.setenv("BUC_PUBLIC_BASE_URL", "service.example.com/")
    assert Settings(_env_file=None).public_base_url == "https://service.example.com"
    monkeypatch.delenv("BUC_PUBLIC_BASE_URL")
    monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
    s = Settings(_env_file=None, environment="production", cookie_secure=True, secret_key="x" * 40)
    with pytest.raises(RuntimeError) as exc:
        s.validate_for_production()
    msg = str(exc.value)
    assert "current value: 'http://localhost:5173'" in msg and "Generate Domain" in msg
