"""Bearer-token handling.

The token is wrapped in :class:`AccessToken` so accidental ``repr``/log output
cannot leak the secret. Only ``reveal()`` returns the raw value, and the token is
never placed into prompts, graph state, or structured logs.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from fastapi import Header

from app.core.errors import UnauthenticatedError

_BEARER_PREFIX = "Bearer "


@dataclass(frozen=True)
class AccessToken:
    _value: str = field(repr=False)

    def reveal(self) -> str:
        return self._value

    def fingerprint(self) -> str:
        """Stable, non-reversible key for caches. Never the token itself."""
        return hashlib.sha256(self._value.encode("utf-8")).hexdigest()

    def __repr__(self) -> str:
        return "AccessToken(***)"

    def __str__(self) -> str:
        return "AccessToken(***)"


async def extract_access_token(authorization: str | None = Header(default=None)) -> AccessToken:
    """FastAPI dependency: read and validate an ``Authorization: Bearer`` header."""
    if authorization is None or not authorization.strip():
        raise UnauthenticatedError("The Authorization header is missing.")

    if not authorization.startswith(_BEARER_PREFIX):
        raise UnauthenticatedError("The Authorization header must use the Bearer scheme.")

    token = authorization[len(_BEARER_PREFIX) :].strip()
    if not token:
        raise UnauthenticatedError("The bearer token is empty.")

    return AccessToken(token)
