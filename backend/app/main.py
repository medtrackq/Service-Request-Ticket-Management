"""FastAPI application entry point."""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.routes import admin, auth, lookups, notifications, public, reports, tickets
from app.config import get_settings
from app.db import SessionLocal
from app.services.errors import DomainError
from app.services.files import storage_root

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("buc")

settings = get_settings()
settings.validate_for_production()

API_PREFIX = "/api/v1"
MAX_BODY_BYTES = 120 * 1024 * 1024  # 10 images x 10 MB + form data; Nginx enforces the same



@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    storage_root()
    log.info("BUC API started (environment=%s, base_url=%s)", settings.environment, settings.public_base_url)
    yield


app = FastAPI(
    lifespan=lifespan,
    title="BUC Customer Service & Ticket Management API",
    version="1.0.0",
    description="REST API of the Bangkok Unitrade Customer Service Center. "
                "Public endpoints live under /api/v1/public; everything else requires a staff session.",
    docs_url="/api/docs" if not settings.is_production else None,
    redoc_url=None,
    openapi_url="/api/openapi.json" if not settings.is_production else None,
)

if settings.cors_origin_list:
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list, allow_credentials=True,
                       allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
                       allow_headers=["Content-Type", "X-CSRF-Token", "Idempotency-Key"])


@app.middleware("http")
async def security_headers(request: Request, call_next):
    length = request.headers.get("content-length")
    if length and length.isdigit() and int(length) > MAX_BODY_BYTES:
        return JSONResponse(status_code=413, content={"detail": {"code": "PAYLOAD_TOO_LARGE",
                                                                 "message": "ขนาดข้อมูลรวมใหญ่เกินกำหนด"}})
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    if request.url.path.startswith("/api/"):
        response.headers.setdefault("Cache-Control", "no-store")
    return response


def _error(status_code: int, code: str, message: str, fields: dict | None = None, extra: dict | None = None):
    detail = {"code": code, "message": message}
    if fields:
        detail["fields"] = fields
    if extra:
        detail.update(extra)
    return JSONResponse(status_code=status_code, content={"detail": detail})


@app.exception_handler(DomainError)
async def domain_error_handler(_: Request, exc: DomainError):
    return _error(exc.status_code, exc.code, exc.message, exc.fields, exc.extra)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_: Request, exc: RequestValidationError):
    fields = {}
    for err in exc.errors():
        loc = [str(p) for p in err.get("loc", []) if p not in ("body", "query", "path", "form")]
        fields[".".join(loc) or "request"] = err.get("msg", "invalid")
    return _error(422, "VALIDATION_ERROR", "ข้อมูลไม่ถูกต้อง", fields)


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(_: Request, exc: StarletteHTTPException):
    if isinstance(exc.detail, dict):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail},
                            headers=getattr(exc, "headers", None))
    return _error(exc.status_code, "HTTP_ERROR", str(exc.detail))


@app.exception_handler(Exception)
async def unhandled_error_handler(_: Request, exc: Exception):
    log.exception("Unhandled error: %s", exc)
    return _error(500, "INTERNAL_ERROR", "เกิดข้อผิดพลาดในระบบ กรุณาลองใหม่อีกครั้ง")


for r in (public.router, auth.router, tickets.router, reports.router, notifications.router, lookups.router,
          admin.router):
    app.include_router(r, prefix=API_PREFIX)


@app.get("/api/health", tags=["health"])
def health() -> dict:
    with SessionLocal() as db:
        db.execute(text("SELECT 1"))
    return {"status": "ok"}
