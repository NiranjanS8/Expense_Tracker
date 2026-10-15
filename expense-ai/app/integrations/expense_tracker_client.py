"""Asynchronous client for the existing Spring Boot Expense Tracker API.

The client owns transport policy for every downstream call. URLs are built from
fixed paths and validated query parameters, never from model output; timeouts are
explicit; retries are bounded and restricted to dependency failures that are safe
to repeat; and every non-success response is mapped onto the typed error
hierarchy before a tool can see it.

Spring Boot remains the only authority for financial data and for tokens: this
client forwards the caller's bearer token and never verifies JWT signatures.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping

import httpx
from pydantic import BaseModel, ValidationError

from app.core.correlation import CORRELATION_HEADER
from app.core.errors import (
    InvalidRequestError,
    NotFoundError,
    RateLimitedError,
    UnauthenticatedError,
    UpstreamTimeoutError,
    UpstreamUnavailableError,
)
from app.core.security import AccessToken

logger = logging.getLogger(__name__)

_CURRENT_USER_PATH = "/users/me"

# Retrying a 4xx would repeat a request Spring Boot has already, deliberately,
# rejected, so only dependency-side failures are repeated.
_RETRYABLE_STATUS_CODES = frozenset({502, 503, 504})

JsonParameters = Mapping[str, str | int | float]


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
        max_retries: int = 0,
        retry_backoff_seconds: float = 0.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._context_path = "/" + context_path.strip("/")
        self._max_retries = max(0, max_retries)
        self._retry_backoff_seconds = max(0.0, retry_backoff_seconds)
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(
                timeout_seconds,
                connect=min(timeout_seconds, 2.0),
            )
        )

    def _url(self, path: str) -> str:
        return f"{self._base_url}{self._context_path}{path}"

    async def get_json(
        self,
        path: str,
        *,
        token: AccessToken,
        params: JsonParameters | None = None,
        correlation_id: str | None = None,
        missing_message: str | None = None,
        invalid_message: str | None = None,
    ) -> object:
        """Perform an authenticated ``GET`` and return the decoded JSON body.

        Payload *shape* is deliberately not validated here: each tool owns the
        contract of the endpoint it calls and reports shape drift itself.
        """
        response = await self._request(path, token=token, params=params, correlation_id=correlation_id)
        status = response.status_code

        if status in (401, 403):
            raise UnauthenticatedError("The access token is not valid.")
        if status == 429:
            logger.warning("event=upstream_rate_limited path=%s", path)
            raise RateLimitedError(headers=_retry_after_headers(response))
        if status == 404:
            raise NotFoundError(missing_message)
        if status == 400:
            logger.warning("event=upstream_rejected_request path=%s", path)
            raise InvalidRequestError(invalid_message)
        if status >= 500:
            logger.warning("event=upstream_error path=%s status=%s", path, status)
            raise UpstreamUnavailableError()
        if status != 200:
            logger.warning("event=upstream_unexpected_status path=%s status=%s", path, status)
            raise UpstreamUnavailableError()

        try:
            return response.json()
        except ValueError as exception:
            logger.warning("event=upstream_invalid_json path=%s", path)
            raise UpstreamUnavailableError() from exception

    async def get_current_user(
        self,
        token: AccessToken,
        correlation_id: str | None = None,
    ) -> AuthenticatedUser:
        """Resolve the trusted identity for a bearer token via ``GET /users/me``.

        A ``401``/``403`` from Spring Boot means the token is missing, malformed,
        expired or invalid, so it is surfaced as a client-facing ``401``. Any
        other unexpected status is treated as the authority being unusable.
        """
        response = await self._request(_CURRENT_USER_PATH, token=token, correlation_id=correlation_id)

        if response.status_code in (401, 403):
            raise UnauthenticatedError("The access token is not valid.")

        if response.status_code >= 500:
            logger.warning("event=identity_introspection_upstream_error status=%s", response.status_code)
            raise UpstreamUnavailableError()

        if response.status_code != 200:
            logger.warning("event=identity_introspection_unexpected_status status=%s", response.status_code)
            raise UpstreamUnavailableError()

        return _parse_current_user(response)

    async def _request(
        self,
        path: str,
        *,
        token: AccessToken,
        params: JsonParameters | None = None,
        correlation_id: str | None = None,
    ) -> httpx.Response:
        headers = {"Authorization": f"Bearer {token.reveal()}"}
        if correlation_id is not None:
            headers[CORRELATION_HEADER] = correlation_id

        url = self._url(path)
        attempts = self._max_retries + 1

        for attempt in range(1, attempts + 1):
            is_last_attempt = attempt == attempts
            try:
                response = await self._client.get(url, headers=headers, params=params)
            except httpx.TimeoutException as exception:
                if is_last_attempt:
                    raise UpstreamTimeoutError() from exception
                await self._back_off(path, attempt, reason="timeout")
                continue
            except httpx.TransportError as exception:
                if is_last_attempt:
                    logger.warning(
                        "event=upstream_transport_error path=%s error=%s", path, type(exception).__name__
                    )
                    raise UpstreamUnavailableError() from exception
                await self._back_off(path, attempt, reason="transport_error")
                continue
            except httpx.HTTPError as exception:
                logger.warning(
                    "event=upstream_protocol_error path=%s error=%s", path, type(exception).__name__
                )
                raise UpstreamUnavailableError() from exception

            if is_last_attempt or response.status_code not in _RETRYABLE_STATUS_CODES:
                return response

            await self._back_off(path, attempt, reason=str(response.status_code))

        raise UpstreamUnavailableError()

    async def _back_off(self, path: str, attempt: int, *, reason: str) -> None:
        logger.warning("event=upstream_retry path=%s attempt=%s reason=%s", path, attempt, reason)
        if self._retry_backoff_seconds > 0:
            await asyncio.sleep(self._retry_backoff_seconds * attempt)

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()


def _retry_after_headers(response: httpx.Response) -> dict[str, str]:
    retry_after = response.headers.get("Retry-After")
    return {"Retry-After": retry_after} if retry_after else {}


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
