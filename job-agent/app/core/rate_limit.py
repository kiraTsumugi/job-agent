"""In-memory IP rate limiter based on a sliding window.

Single-worker deployment (Railway/Fly.io default) is the assumed target,
so no Redis-backed distributed counter. Trade-off accepted for simplicity.
"""

from __future__ import annotations

import time
from collections import defaultdict


class SlidingWindowLimiter:
    """Keep recent request timestamps per key, reject when over limit within window."""

    def __init__(self, limit: int, window_sec: int) -> None:
        self.limit = limit
        self.window_sec = window_sec
        self._hits: dict[str, list[float]] = defaultdict(list)

    def check(self, key: str) -> tuple[bool, int]:
        """Return (allowed, retry_after_sec). retry_after_sec=0 when allowed."""
        now = time.monotonic()
        cutoff = now - self.window_sec
        bucket = [t for t in self._hits[key] if t > cutoff]
        if len(bucket) >= self.limit:
            oldest = bucket[0]
            retry_after = max(1, int(oldest + self.window_sec - now) + 1)
            self._hits[key] = bucket
            return False, retry_after
        bucket.append(now)
        self._hits[key] = bucket
        return True, 0


def client_ip(request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    return request.client.host if request.client else "unknown"
