"""In-process fixed-window rate limiting.

Deliberately simple for the first release: the plan defers Redis until shared
counters are genuinely required. This limiter is per-process and must be replaced
before horizontal scaling. Enforcement lives here rather than in Spring Boot
because the existing read endpoints are not rate limited upstream.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from app.core.errors import RateLimitedError


@dataclass
class _Window:
    count: int
    ends_at: float


class FixedWindowRateLimiter:
    def __init__(self, max_requests: int, window_seconds: float) -> None:
        if max_requests <= 0 or window_seconds <= 0:
            raise ValueError("max_requests and window_seconds must be positive")
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._buckets: dict[str, _Window] = {}

    def check(self, key: str) -> None:
        now = time.monotonic()
        window = self._buckets.get(key)

        if window is None or window.ends_at <= now:
            self._buckets[key] = _Window(count=1, ends_at=now + self._window_seconds)
            return

        if window.count >= self._max_requests:
            retry_after = max(1, int(window.ends_at - now) + 1)
            raise RateLimitedError(
                headers={"Retry-After": str(retry_after)},
            )

        window.count += 1

    def clear(self) -> None:
        self._buckets.clear()
