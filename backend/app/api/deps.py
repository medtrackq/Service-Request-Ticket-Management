"""Shared FastAPI dependencies: authentication, CSRF and role checks."""
from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import User, UserSession
from app.security.sessions import load_session
from app.security.tokens import constant_time_equals
from app.services.settings_service import get_setting

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def _unauthenticated() -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED,
                         detail={"code": "UNAUTHENTICATED", "message": "กรุณาเข้าสู่ระบบ"})


def _load(request: Request, db: Session) -> UserSession:
    token = request.cookies.get(get_settings().session_cookie_name)
    sess = load_session(db, token)
    if sess is None:
        raise _unauthenticated()
    if request.method not in SAFE_METHODS:
        header = request.headers.get("x-csrf-token") or ""
        if not header or not constant_time_equals(header, sess.csrf_token):
            raise HTTPException(status.HTTP_403_FORBIDDEN,
                                detail={"code": "CSRF_FAILED", "message": "คำขอไม่ถูกต้อง กรุณาโหลดหน้าใหม่"})
    request.state.session = sess
    request.state.user = sess.user
    return sess


def current_session(request: Request, db: Session = Depends(get_db)) -> UserSession:
    """Authenticated session; allowed even when a password change is pending."""
    return _load(request, db)


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    sess = _load(request, db)
    if sess.user.must_change_password:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail={
            "code": "PASSWORD_CHANGE_REQUIRED", "message": "กรุณาเปลี่ยนรหัสผ่านก่อนใช้งาน"})
    return sess.user


def require_roles(*roles: str) -> Callable[..., User]:
    def dep(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN,
                                detail={"code": "FORBIDDEN", "message": "ท่านไม่มีสิทธิ์ใช้งานส่วนนี้"})
        return user

    return dep


require_admin = require_roles("ADMIN")
require_manager = require_roles("ADMIN", "MANAGER")


def staff_queue_enabled(db: Session) -> bool:
    return bool(get_setting(db, "access.staff_see_department_queue"))
