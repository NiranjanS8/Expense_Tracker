"""Structured JSON logging with correlation IDs and secret redaction."""

from __future__ import annotations

import json
import logging
import sys
from typing import Any

from app.core.correlation import get_correlation_id

_REDACTED = "***redacted***"
_SENSITIVE_KEYS = frozenset(
    {"authorization", "api_key", "apikey", "access_token", "token", "password", "secret"}
)


class JsonFormatter(logging.Formatter):
    """Minimal structured formatter: no prompts, tokens, or financial payloads."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        correlation_id = get_correlation_id()
        if correlation_id is not None:
            payload["correlationId"] = correlation_id

        for key, value in getattr(record, "extra_fields", {}).items():
            payload[key] = _REDACTED if key.lower() in _SENSITIVE_KEYS else value

        if record.exc_info and record.exc_info[0] is not None:
            payload["exception"] = record.exc_info[0].__name__

        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())

    # Uvicorn installs its own handlers; keep them but let them use our level.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logging.getLogger(name).setLevel(level.upper())

    # The HTTP client logs every request URL at INFO, including query parameters
    # such as a search term. The client's own structured events already cover the
    # diagnostics worth keeping, so quiet these to warnings to avoid leaking
    # financial filters into logs.
    for name in ("httpx", "httpcore"):
        logging.getLogger(name).setLevel(logging.WARNING)
