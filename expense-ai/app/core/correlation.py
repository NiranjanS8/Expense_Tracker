"""Correlation ID propagation.

The AI service accepts an inbound ``X-Correlation-Id`` header, generates one when
absent, echoes it on the response, and forwards it to the Spring Boot API. The
value is stored in a context variable so log records and outbound calls share it
without threading it through every function signature.
"""

from __future__ import annotations

import contextvars
import uuid

CORRELATION_HEADER = "X-Correlation-Id"

_correlation_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("correlation_id", default=None)


def get_correlation_id() -> str | None:
    return _correlation_id.get()


def resolve_correlation_id(inbound: str | None) -> str:
    """Return a trimmed inbound correlation ID, or a new UUID when missing."""
    if inbound is not None and inbound.strip():
        return inbound.strip()
    return str(uuid.uuid4())


def set_correlation_id(value: str) -> contextvars.Token[str | None]:
    return _correlation_id.set(value)


def reset_correlation_id(token: contextvars.Token[str | None]) -> None:
    _correlation_id.reset(token)
