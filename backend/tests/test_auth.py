"""Authentication, sessions, CSRF, lockout and forced password change."""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select, update

from app.models import User, UserSession, utcnow
from tests.conftest import PASSWORD, login, make_user


def test_login_and_me(client):
    make_user("alice", "MANAGER", ("SERVICE",))
    r = client.post("/api/v1/auth/login", json={"username": "ALICE", "password": PASSWORD})
    assert r.status_code == 200
    body = r.json()
    assert body["user"]["role"] == "MANAGER" and body["csrf_token"]
    cookie = r.headers.get("set-cookie", "")
    assert "HttpOnly" in cookie and "SameSite=lax" in cookie
    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200 and me.json()["user"]["username"] == "alice"


def test_wrong_password_generic_error(client):
    make_user("bob")
    r1 = client.post("/api/v1/auth/login", json={"username": "bob", "password": "nope"})
    r2 = client.post("/api/v1/auth/login", json={"username": "nobody", "password": "nope"})
    assert r1.status_code == r2.status_code == 401
    assert r1.json() == r2.json()


def test_lockout_after_repeated_failures(client, db):
    make_user("carol")
    for _ in range(5):
        client.post("/api/v1/auth/login", json={"username": "carol", "password": "bad"})
    r = client.post("/api/v1/auth/login", json={"username": "carol", "password": PASSWORD})
    assert r.status_code == 423
    db.execute(update(User).where(User.username == "carol").values(locked_until=utcnow() - timedelta(seconds=1)))
    db.commit()
    assert client.post("/api/v1/auth/login", json={"username": "carol", "password": PASSWORD}).status_code == 200


def test_inactive_user_cannot_login(client):
    uid = make_user("dave")
    s = login("dave")
    admin_id = make_user("root", "ADMIN")
    assert admin_id
    admin = login("root")
    assert admin.patch(f"/api/v1/admin/users/{uid}", json={"is_active": False}).status_code == 200
    # existing session is revoked immediately
    assert s.get("/api/v1/tickets").status_code == 401
    assert client.post("/api/v1/auth/login", json={"username": "dave", "password": PASSWORD}).status_code == 401


def test_unauthenticated_requests_rejected(client):
    for url in ("/api/v1/tickets", "/api/v1/dashboard", "/api/v1/admin/users", "/api/v1/lookups"):
        assert client.get(url).status_code == 401


def test_csrf_required_for_state_changes():
    make_user("erin", "ADMIN")
    s = login("erin")
    r = s.c.post("/api/v1/admin/departments", json={"code": "QA", "name_th": "QA", "name_en": "QA"})
    assert r.status_code == 403 and r.json()["detail"]["code"] == "CSRF_FAILED"
    r = s.c.post("/api/v1/admin/departments", json={"code": "QA", "name_th": "QA", "name_en": "QA"},
                 headers={"X-CSRF-Token": "wrong"})
    assert r.status_code == 403
    assert s.post("/api/v1/admin/departments", json={"code": "QA", "name_th": "QA", "name_en": "QA"}).status_code == 201


def test_forced_password_change(client):
    make_user("frank", "STAFF", ("CS",), must_change=True)
    s = login("frank")
    r = s.get("/api/v1/tickets")
    assert r.status_code == 403 and r.json()["detail"]["code"] == "PASSWORD_CHANGE_REQUIRED"
    weak = s.post("/api/v1/auth/change-password", json={"current_password": PASSWORD, "new_password": "short"})
    assert weak.status_code == 422
    ok = s.post("/api/v1/auth/change-password",
                json={"current_password": PASSWORD, "new_password": "A-much-better-pass-99"})
    assert ok.status_code == 200
    assert s.get("/api/v1/tickets").status_code == 200


def test_logout_revokes_session():
    make_user("gina")
    s = login("gina")
    assert s.post("/api/v1/auth/logout").status_code == 200
    assert s.c.get("/api/v1/auth/me", cookies={"buc_session": "x"}).status_code == 401


def test_idle_session_expires(db):
    make_user("hank")
    s = login("hank")
    db.execute(update(UserSession).values(last_seen_at=utcnow() - timedelta(hours=5)))
    db.commit()
    assert s.get("/api/v1/auth/me").status_code == 401


def test_session_token_stored_hashed(db):
    make_user("ivy")
    s = login("ivy")
    token = s.c.cookies.get("buc_session")
    stored = db.scalar(select(UserSession.token_hash))
    assert token and stored and token != stored and len(stored) == 64


def test_password_hash_is_argon2(db):
    make_user("jack")
    assert db.scalar(select(User.password_hash).where(User.username == "jack")).startswith("$argon2id$")
