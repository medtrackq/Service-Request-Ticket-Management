"""Staff authentication: login, logout, current user, password change."""
from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import current_session
from app.config import get_settings
from app.db import get_db
from app.models import User, UserSession, utcnow
from app.security import permissions as perm
from app.security.passwords import hash_password, needs_rehash, password_policy_errors, verify_password
from app.security.rate_limit import client_ip, enforce
from app.security.sessions import create_session, revoke_all_sessions, revoke_session
from app.services.audit import audit

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=254)
    password: str = Field(min_length=1, max_length=256)


class ChangePasswordIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=1, max_length=256)


def user_payload(user: User, csrf_token: str) -> dict:
    return {
        "user": {
            "id": user.id,
            "username": user.username,
            "full_name": user.full_name,
            "email": user.email,
            "role": user.role,
            "preferred_language": user.preferred_language,
            "must_change_password": user.must_change_password,
            "departments": [{"id": d.id, "code": d.code, "name_th": d.name_th, "name_en": d.name_en}
                            for d in user.departments],
        },
        "permissions": {
            "is_admin": perm.is_admin(user),
            "can_export": perm.can_export(user),
            "can_view_reports": perm.can_view_reports(user),
            "can_bulk_assign": user.role in ("ADMIN", "MANAGER"),
        },
        "csrf_token": csrf_token,
    }


def _set_cookies(response: Response, token: str, csrf: str) -> None:
    s = get_settings()
    max_age = s.session_absolute_hours * 3600
    response.set_cookie(s.session_cookie_name, token, max_age=max_age, httponly=True, secure=s.cookie_secure,
                        samesite="lax", path="/api")
    response.set_cookie(s.csrf_cookie_name, csrf, max_age=max_age, httponly=False, secure=s.cookie_secure,
                        samesite="lax", path="/")


@router.post("/login")
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)) -> dict:
    s = get_settings()
    enforce(request, "login", s.rate_limit_login_per_minute, 60)
    ident = body.username.strip().lower()
    user = db.scalar(select(User).where((func.lower(User.username) == ident) | (func.lower(User.email) == ident)))
    now = utcnow()
    generic = HTTPException(status.HTTP_401_UNAUTHORIZED,
                            detail={"code": "INVALID_CREDENTIALS", "message": "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง"})
    if user is not None and user.locked_until and user.locked_until > now:
        verify_password(None, body.password)  # keep timing similar
        audit(db, "auth.login_locked", actor=user, entity_type="user", entity_id=user.id, request=request)
        db.commit()
        raise HTTPException(status.HTTP_423_LOCKED, detail={
            "code": "ACCOUNT_LOCKED",
            "message": f"บัญชีถูกล็อกชั่วคราวเนื่องจากเข้าสู่ระบบผิดหลายครั้ง กรุณาลองใหม่ใน {s.login_lockout_minutes} นาที"})
    ok = verify_password(user.password_hash if user else None, body.password)
    if not ok or user is None or not user.is_active:
        if user is not None:
            user.failed_login_count += 1
            if user.failed_login_count >= s.login_max_failures:
                user.locked_until = now + timedelta(minutes=s.login_lockout_minutes)
                user.failed_login_count = 0
        audit(db, "auth.login_failed", actor=user, entity_type="user", entity_id=user.id if user else None,
              request=request, details={"username": ident[:60]})
        db.commit()
        raise generic
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(body.password)
    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = now
    new = create_session(db, user, client_ip(request), request.headers.get("user-agent"))
    audit(db, "auth.login", actor=user, entity_type="user", entity_id=user.id, request=request)
    db.commit()
    _set_cookies(response, new.token, new.csrf_token)
    return user_payload(user, new.csrf_token)


@router.post("/logout")
def logout(request: Request, response: Response, sess: UserSession = Depends(current_session),
           db: Session = Depends(get_db)) -> dict:
    sess = db.merge(sess)
    revoke_session(db, sess)
    audit(db, "auth.logout", actor=sess.user, entity_type="user", entity_id=sess.user_id, request=request)
    db.commit()
    s = get_settings()
    response.delete_cookie(s.session_cookie_name, path="/api")
    response.delete_cookie(s.csrf_cookie_name, path="/")
    return {"message": "ออกจากระบบแล้ว"}


@router.get("/me")
def me(sess: UserSession = Depends(current_session)) -> dict:
    return user_payload(sess.user, sess.csrf_token)


@router.post("/change-password")
def change_password(body: ChangePasswordIn, request: Request, sess: UserSession = Depends(current_session),
                    db: Session = Depends(get_db)) -> dict:
    user = db.get(User, sess.user_id)
    assert user is not None
    if not verify_password(user.password_hash, body.current_password):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail={
            "code": "INVALID_PASSWORD", "message": "รหัสผ่านปัจจุบันไม่ถูกต้อง",
            "fields": {"current_password": "รหัสผ่านปัจจุบันไม่ถูกต้อง"}})
    errors = password_policy_errors(body.new_password, get_settings().password_min_length)
    if body.new_password == body.current_password:
        errors.append("รหัสผ่านใหม่ต้องไม่ซ้ำกับรหัสผ่านเดิม")
    if errors:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail={
            "code": "WEAK_PASSWORD", "message": errors[0], "fields": {"new_password": " / ".join(errors)}})
    user.password_hash = hash_password(body.new_password)
    user.must_change_password = False
    user.password_changed_at = utcnow()
    revoke_all_sessions(db, user.id, except_session_id=sess.id)
    audit(db, "auth.password_changed", actor=user, entity_type="user", entity_id=user.id, request=request)
    db.commit()
    return {"message": "เปลี่ยนรหัสผ่านเรียบร้อยแล้ว"}
