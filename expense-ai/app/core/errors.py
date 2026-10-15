"""Typed application errors and a stable public error envelope.

Every failure surfaced to a client is a small, documented JSON object. Internal
exception details, stack traces, tokens and upstream payloads are never returned.
"""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    """Base class for expected, client-safe failures."""

    status_code: int = 500
    code: str = "internal_error"

    def __init__(
        self,
        message: str | None = None,
        *,
        details: list[str] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message or self.default_message())
        self.message = message or self.default_message()
        self.details = details or []
        self.headers = headers or {}

    @classmethod
    def default_message(cls) -> str:
        return "An unexpected error occurred."


class InvalidRequestError(AppError):
    status_code = 400
    code = "invalid_request"

    @classmethod
    def default_message(cls) -> str:
        return "The request was invalid."


class PayloadTooLargeError(AppError):
    status_code = 413
    code = "payload_too_large"

    @classmethod
    def default_message(cls) -> str:
        return "The request body is too large."


class UnauthenticatedError(AppError):
    status_code = 401
    code = "unauthenticated"

    @classmethod
    def default_message(cls) -> str:
        return "A valid access token is required."


class ForbiddenError(AppError):
    status_code = 403
    code = "forbidden"

    @classmethod
    def default_message(cls) -> str:
        return "You are not allowed to access this resource."


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"

    @classmethod
    def default_message(cls) -> str:
        return "The requested resource was not found."


class RateLimitedError(AppError):
    status_code = 429
    code = "rate_limited"

    @classmethod
    def default_message(cls) -> str:
        return "Too many requests. Please try again later."


class NotImplementedYetError(AppError):
    status_code = 501
    code = "not_implemented"

    @classmethod
    def default_message(cls) -> str:
        return "This capability is not implemented yet."


class UpstreamUnavailableError(AppError):
    status_code = 503
    code = "upstream_unavailable"

    @classmethod
    def default_message(cls) -> str:
        return "A required downstream service is unavailable."


class UpstreamTimeoutError(AppError):
    status_code = 504
    code = "upstream_timeout"

    @classmethod
    def default_message(cls) -> str:
        return "A required downstream service timed out."


def error_payload(
    *,
    status: int,
    code: str,
    message: str,
    correlation_id: str | None,
    details: list[str] | None = None,
) -> dict[str, Any]:
    """Build the public error envelope. Deliberately free of internal detail."""
    return {
        "status": status,
        "code": code,
        "message": message,
        "correlationId": correlation_id,
        "details": details or [],
    }
