"""Random token helpers. Tokens are only ever stored as SHA-256 hashes."""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

from app.config import get_settings


def new_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def sha256_hex(value: str | bytes) -> str:
    if isinstance(value, str):
        value = value.encode()
    return hashlib.sha256(value).hexdigest()


def derive_tracking_token(idempotency_key: str) -> str:
    """Deterministic tracking token for a submission.

    Derived with HMAC from the server secret and the client's random idempotency key,
    so a retried submission (same key) can be answered with the same token without the
    server ever storing the plain token. Unpredictable without both values.
    """
    secret = get_settings().secret_key.encode()
    digest = hmac.new(secret, f"tracking:{idempotency_key}".encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def constant_time_equals(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())
