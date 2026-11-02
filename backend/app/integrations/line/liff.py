"""Optional LINE Login / LIFF identity verification.

Opening a Rich Menu URL does NOT tell us who the LINE user is. When a page is
opened as a LIFF app, the frontend can obtain an ID token (liff.getIDToken())
and send it with the form. This module verifies that token server-side with
LINE's verify endpoint before trusting the `sub` (LINE userId).

Disabled unless BUC_LINE_LOGIN_CHANNEL_ID is configured.
Status: implemented against LINE's documented API; not yet tested with a live
LINE channel (no channel credentials were available during development).
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

from app.config import get_settings

VERIFY_URL = "https://api.line.me/oauth2/v2.1/verify"


class LiffVerificationError(Exception):
    pass


def liff_enabled() -> bool:
    return bool(get_settings().line_login_channel_id)


def verify_liff_id_token(id_token: str, timeout: float = 5.0) -> str:
    """Return the verified LINE userId (`sub`) or raise LiffVerificationError."""
    channel_id = get_settings().line_login_channel_id
    if not channel_id:
        raise LiffVerificationError("LINE Login is not configured")
    if not id_token or len(id_token) > 4096:
        raise LiffVerificationError("invalid token")
    data = urllib.parse.urlencode({"id_token": id_token, "client_id": channel_id}).encode()
    req = urllib.request.Request(VERIFY_URL, data=data, method="POST",
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (fixed https URL)
            payload = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        raise LiffVerificationError(f"LINE rejected the token (HTTP {exc.code})") from None
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise LiffVerificationError(f"LINE verify failed: {exc}") from None
    sub = payload.get("sub")
    if payload.get("aud") != channel_id or not sub:
        raise LiffVerificationError("token audience mismatch")
    return str(sub)
