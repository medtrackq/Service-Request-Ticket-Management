"""Optional LINE Messaging API push channel (future).

Used by the notification worker only when BOTH the system setting
`notifications.line_enabled` is true AND BUC_LINE_MESSAGING_CHANNEL_ACCESS_TOKEN
is configured, and only for tickets whose LINE identity was verified via LIFF.

Status: implemented against LINE's documented push endpoint; not tested with a
live LINE Official Account. Keep disabled until tested in a staging channel.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

from app.config import get_settings

PUSH_URL = "https://api.line.me/v2/bot/message/push"


class LineDeliveryError(Exception):
    def __init__(self, message: str, retryable: bool = True) -> None:
        super().__init__(message)
        self.retryable = retryable


def push_text(line_user_id: str, text: str, timeout: float = 10.0) -> None:
    token = get_settings().line_messaging_channel_access_token
    if not token:
        raise LineDeliveryError("LINE Messaging API is not configured", retryable=False)
    body = json.dumps({"to": line_user_id, "messages": [{"type": "text", "text": text[:5000]}]}).encode()
    req = urllib.request.Request(
        PUSH_URL, data=body, method="POST",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout):  # noqa: S310 (fixed https URL)
            return
    except urllib.error.HTTPError as exc:
        # 4xx (except 429) will not succeed on retry.
        raise LineDeliveryError(f"LINE push failed: HTTP {exc.code}",
                                retryable=exc.code == 429 or exc.code >= 500) from None
    except (urllib.error.URLError, TimeoutError) as exc:
        raise LineDeliveryError(f"LINE push failed: {exc}") from None
