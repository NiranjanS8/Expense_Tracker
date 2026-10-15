"""Asynchronous client for the existing Spring Boot Expense Tracker API.

Phase 1 implements only the identity introspection call required by the approved
authentication flow (Option A). It deliberately does not verify JWT signatures and
never holds the signing secret: Spring Boot remains the authority for tokens.
"""

from __future__ import annotations

import logging

import httpx
from pydantic import BaseModel, ValidationError

from app.core.correlation import CORRELATION_HEADER
from app.core.errors import (
    UnauthenticatedError,
    UpstreamTimeoutError,
    UpstreamUnavailableError,
)
from app.core.security import AccessToken

logger = logging.getLogger(__name__)

_CURRENT_USER_PATH = "/users/me"


class AuthenticatedUser(BaseModel):
    """Trusted user identity as reported by Spring Boot. Never built from chat text."""

    user_id: int
    email: str
    full_name: str | None = None
    role: str


class ExpenseTrackerClient:
    def __init__(
        self,
        *,
        base_url: str,
        context_path: str,
        timeout_seconds: float,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._context_path = "/" + context_path.strip("/")
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(
                timeout_seconds,
                connect=min(timeout_seconds, 2.0),
            )
        )

    def _url(self, path: str) -> str:
        return f"{self._base_url}{self._context_path}{path}"

    async def get_current_user(
        self,
        token: AccessToken,
        correlation_id: str | None = None,
    ) -> AuthenticatedUser:
        """Resolve the trusted identity for a bearer token via ``GET /users/me``.

        A ``401``/``403`` from Spring Boot means the token is missing, malformed,
        expired or invalid, so it is surfaced as a client-facing ``401``.
        """
        headers = {"Authorization": f"Bearer {token.reveal()}"}
        if correlation_id is not None:
            headers[CORRELATION_HEADER] = correlation_id

        try:
            response = await self._client.get(self._url(_CURRENT_USER_PATH), headers=headers)
        except httpx.TimeoutException as exception:
            raise UpstreamTimeoutError() from exception
        except httpx.HTTPError as exception:
            logger.warning("event=identity_introspection_transport_error error=%s", type(exception).__name__)
            raise UpstreamUnavailableError() from exception

        if response.status_code in (401, 403):
            raise UnauthenticatedError("The access token is not valid.")

        if response.status_code >= 500:
            logger.warning("event=identity_introspection_upstream_error status=%s", response.status_code)
            raise UpstreamUnavailableError()

        if response.status_code != 200:
            logger.warning("event=identity_introspection_unexpected_status status=%s", response.status_code)
            raise UpstreamUnavailableError()

        return _parse_current_user(response)

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()


def _parse_current_user(response: httpx.Response) -> AuthenticatedUser:
    try:
        body = response.json()
    except ValueError as exception:
        logger.warning("event=identity_introspection_invalid_json")
        raise UpstreamUnavailableError() from exception

    try:
        return AuthenticatedUser(
            user_id=body["id"],
            email=body["email"],
            full_name=body.get("fullName"),
            role=body.get("role", "USER"),
        )
    except (KeyError, TypeError, ValidationError) as exception:
        logger.warning("event=identity_introspection_invalid_payload")
        raise UpstreamUnavailableError() from exception
