from __future__ import annotations

import pytest

from app.core.errors import (
    AppError,
    ForbiddenError,
    NotFoundError,
    NotImplementedYetError,
    PayloadTooLargeError,
    RateLimitedError,
    UnauthenticatedError,
    UpstreamTimeoutError,
    UpstreamUnavailableError,
    error_payload,
)


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (UnauthenticatedError(), 401, "unauthenticated"),
        (ForbiddenError(), 403, "forbidden"),
        (NotFoundError(), 404, "not_found"),
        (PayloadTooLargeError(), 413, "payload_too_large"),
        (RateLimitedError(), 429, "rate_limited"),
        (NotImplementedYetError(), 501, "not_implemented"),
        (UpstreamUnavailableError(), 503, "upstream_unavailable"),
        (UpstreamTimeoutError(), 504, "upstream_timeout"),
    ],
)
def test_errors_carry_stable_status_and_code(error: AppError, status: int, code: str) -> None:
    assert error.status_code == status
    assert error.code == code
    assert error.message


def test_error_payload_contains_only_public_fields() -> None:
    payload = error_payload(
        status=401,
        code="unauthenticated",
        message="A valid access token is required.",
        correlation_id="abc-123",
    )

    assert payload == {
        "status": 401,
        "code": "unauthenticated",
        "message": "A valid access token is required.",
        "correlationId": "abc-123",
        "details": [],
    }


def test_rate_limited_error_carries_retry_after_header() -> None:
    error = RateLimitedError(headers={"Retry-After": "30"})

    assert error.headers["Retry-After"] == "30"
