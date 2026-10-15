"""Trusted identity resolution with a short-lived token cache.

The authoritative source of user identity is Spring Boot (``GET /users/me``).
Caching is keyed by a SHA-256 fingerprint of the token, so the raw token is never
stored as a cache key, and the entry expires quickly to bound staleness.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from app.core.security import AccessToken
from app.integrations.expense_tracker_client import AuthenticatedUser, ExpenseTrackerClient


@dataclass
class _CacheEntry:
    user: AuthenticatedUser
    expires_at: float


class IdentityResolver:
    def __init__(self, client: ExpenseTrackerClient, *, ttl_seconds: int) -> None:
        self._client = client
        self._ttl_seconds = ttl_seconds
        self._cache: dict[str, _CacheEntry] = {}

    async def resolve(self, token: AccessToken, correlation_id: str | None = None) -> AuthenticatedUser:
        if self._ttl_seconds <= 0:
            return await self._client.get_current_user(token, correlation_id)

        now = time.monotonic()
        fingerprint = token.fingerprint()

        cached = self._cache.get(fingerprint)
        if cached is not None and cached.expires_at > now:
            return cached.user

        user = await self._client.get_current_user(token, correlation_id)
        self._cache[fingerprint] = _CacheEntry(user=user, expires_at=now + self._ttl_seconds)
        return user

    def evict(self, token: AccessToken) -> None:
        self._cache.pop(token.fingerprint(), None)

    def clear(self) -> None:
        self._cache.clear()
