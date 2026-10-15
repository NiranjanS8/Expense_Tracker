from __future__ import annotations

import pytest

from app.core.errors import RateLimitedError
from app.core.rate_limit import FixedWindowRateLimiter


def test_limiter_allows_up_to_the_limit_then_rejects() -> None:
    limiter = FixedWindowRateLimiter(max_requests=2, window_seconds=60)

    limiter.check("user:1")
    limiter.check("user:1")

    with pytest.raises(RateLimitedError) as captured:
        limiter.check("user:1")

    assert "Retry-After" in captured.value.headers


def test_limiter_is_scoped_per_key() -> None:
    limiter = FixedWindowRateLimiter(max_requests=1, window_seconds=60)

    limiter.check("user:1")
    limiter.check("user:2")


def test_limiter_rejects_invalid_configuration() -> None:
    with pytest.raises(ValueError):
        FixedWindowRateLimiter(max_requests=0, window_seconds=60)
