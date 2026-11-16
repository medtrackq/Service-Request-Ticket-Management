"""Small in-process sliding-window rate limiter.

This complements (does not replace) the Nginx `limit_req` zones configured in
deploy/nginx. Limits are per API process; with N backend workers the effective
limit is at most N times the configured value.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

from app.config import get_settings


class RateLimiter:
    def __init__(self) -> None:
        self._hits: dict[tuple[str, str], deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()
        self.enabled = True

    def check(self, bucket: str, key: str, limit: int, window_seconds: int) -> bool:
        if not self.enabled or limit <= 0:
            return True
        now = time.monotonic()
        with self._lock:
            hits = self._hits[(bucket, key)]
            while hits and hits[0] <= now - window_seconds:
                hits.popleft()
            if len(hits) >= limit:
                return False
            hits.append(now)
            # Opportunistic cleanup to keep memory bounded.
            if len(self._hits) > 50_000:
                for k in [k for k, v in self._hits.items() if not v]:
                    del self._hits[k]
            return True

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


limiter = RateLimiter()


def client_ip(request: Request) -> str:
    """Real client address.

    Behind Nginx (Docker Compose) uvicorn's --proxy-headers already resolves it from the
    X-Forwarded-For value that Nginx overwrites. Behind an edge proxy that overwrites a
    dedicated header (Railway: X-Real-IP), set BUC_CLIENT_IP_HEADER to read that header.
    """
    header = get_settings().client_ip_header
    if header:
        value = request.headers.get(header, "").split(",")[0].strip()
        if value:
            return value[:64]
    return request.client.host if request.client else "unknown"


def enforce(request: Request, bucket: str, limit: int, window_seconds: int) -> None:
    if not limiter.check(bucket, client_ip(request), limit, window_seconds):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"code": "RATE_LIMITED", "message": "มีการส่งคำขอบ่อยเกินไป กรุณารอสักครู่แล้วลองใหม่"},
            headers={"Retry-After": str(window_seconds)},
        )
