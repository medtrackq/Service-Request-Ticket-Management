"""Domain errors translated to HTTP responses by the API layer."""
from __future__ import annotations

from typing import Any


class DomainError(Exception):
    status_code = 400
    code = "BAD_REQUEST"

    def __init__(self, message: str, *, code: str | None = None, fields: dict[str, str] | None = None,
                 extra: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        self.fields = fields or {}
        self.extra = extra or {}


class ValidationFailed(DomainError):
    status_code = 422
    code = "VALIDATION_ERROR"


class NotFound(DomainError):
    status_code = 404
    code = "NOT_FOUND"


class Forbidden(DomainError):
    status_code = 403
    code = "FORBIDDEN"


class Conflict(DomainError):
    status_code = 409
    code = "CONFLICT"
