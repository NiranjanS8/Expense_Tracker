from __future__ import annotations

import httpx
import pytest

from app.core.errors import (
    InvalidRequestError,
    NotFoundError,
    RateLimitedError,
    UnauthenticatedError,
    UpstreamTimeoutError,
    UpstreamUnavailableError,
)
from app.core.security import AccessToken
from app.integrations.expense_tracker_client import ExpenseTrackerClient
from tests.conftest import SPRING_BASE_URL, Responder


def build_client(responder: Responder, *, max_retries: int = 0) -> ExpenseTrackerClient:
    return ExpenseTrackerClient(
        base_url=SPRING_BASE_URL,
        context_path="/api",
        timeout_seconds=1.0,
        client=httpx.AsyncClient(transport=httpx.MockTransport(responder)),
        max_retries=max_retries,
        retry_backoff_seconds=0.0,
    )


async def test_get_current_user_maps_upstream_profile() -> None:
    def responder(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/users/me"
        assert request.headers["authorization"] == "Bearer token-1"
        return httpx.Response(
            200,
            json={"id": 7, "fullName": "Ada Lovelace", "email": "ada@example.com", "role": "USER"},
        )

    user = await build_client(responder).get_current_user(AccessToken("token-1"))

    assert user.user_id == 7
    assert user.email == "ada@example.com"
    assert user.full_name == "Ada Lovelace"
    assert user.role == "USER"


async def test_correlation_id_is_forwarded_upstream() -> None:
    captured: dict[str, str] = {}

    def responder(request: httpx.Request) -> httpx.Response:
        captured["correlation"] = request.headers["x-correlation-id"]
        return httpx.Response(200, json={"id": 1, "email": "a@b.c", "role": "USER"})

    await build_client(responder).get_current_user(AccessToken("t"), "corr-42")

    assert captured["correlation"] == "corr-42"


@pytest.mark.parametrize("status_code", [401, 403])
async def test_missing_or_invalid_token_maps_to_unauthenticated(status_code: int) -> None:
    client = build_client(lambda _request: httpx.Response(status_code))

    with pytest.raises(UnauthenticatedError):
        await client.get_current_user(AccessToken("expired"))


async def test_upstream_server_error_maps_to_unavailable() -> None:
    client = build_client(lambda _request: httpx.Response(500))

    with pytest.raises(UpstreamUnavailableError):
        await client.get_current_user(AccessToken("t"))


async def test_malformed_upstream_payload_maps_to_unavailable() -> None:
    client = build_client(lambda _request: httpx.Response(200, json={"unexpected": True}))

    with pytest.raises(UpstreamUnavailableError):
        await client.get_current_user(AccessToken("t"))


async def test_transport_timeout_maps_to_upstream_timeout() -> None:
    def responder(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("upstream timed out")

    client = build_client(responder)

    with pytest.raises(UpstreamTimeoutError):
        await client.get_current_user(AccessToken("t"))


async def test_get_json_returns_the_decoded_body() -> None:
    client = build_client(lambda _request: httpx.Response(200, json={"totalAmount": 5}))

    assert await client.get_json("/expenses/summary", token=AccessToken("t")) == {"totalAmount": 5}


async def test_get_json_forwards_parameters_and_correlation_id() -> None:
    captured: dict[str, str] = {}

    def responder(request: httpx.Request) -> httpx.Response:
        captured["query"] = str(request.url.query, "utf-8")
        captured["correlation"] = request.headers["x-correlation-id"]
        return httpx.Response(200, json={})

    await build_client(responder).get_json(
        "/expenses/summary",
        token=AccessToken("t"),
        params={"search": "coffee"},
        correlation_id="corr-7",
    )

    assert captured["query"] == "search=coffee"
    assert captured["correlation"] == "corr-7"


@pytest.mark.parametrize(
    ("status_code", "expected_error"),
    [
        (400, InvalidRequestError),
        (401, UnauthenticatedError),
        (403, UnauthenticatedError),
        (404, NotFoundError),
        (429, RateLimitedError),
        (500, UpstreamUnavailableError),
    ],
)
async def test_get_json_maps_upstream_failures_to_typed_errors(
    status_code: int,
    expected_error: type[Exception],
) -> None:
    client = build_client(lambda _request: httpx.Response(status_code))

    with pytest.raises(expected_error):
        await client.get_json("/expenses/summary", token=AccessToken("t"))


async def test_get_json_uses_the_caller_supplied_missing_message() -> None:
    client = build_client(lambda _request: httpx.Response(404))

    with pytest.raises(NotFoundError, match="No budget has been set"):
        await client.get_json(
            "/budgets/2026-03",
            token=AccessToken("t"),
            missing_message="No budget has been set for that month.",
        )


async def test_rate_limiting_propagates_retry_after() -> None:
    client = build_client(lambda _request: httpx.Response(429, headers={"Retry-After": "30"}))

    with pytest.raises(RateLimitedError) as error:
        await client.get_json("/expenses", token=AccessToken("t"))

    assert error.value.headers == {"Retry-After": "30"}


async def test_get_json_treats_an_undecodable_body_as_unavailable() -> None:
    client = build_client(lambda _request: httpx.Response(200, content=b"not json"))

    with pytest.raises(UpstreamUnavailableError):
        await client.get_json("/expenses", token=AccessToken("t"))


async def test_transient_dependency_failures_are_retried_within_the_bound() -> None:
    attempts = 0

    def responder(_request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(503)

    with pytest.raises(UpstreamUnavailableError):
        await build_client(responder, max_retries=1).get_json("/expenses", token=AccessToken("t"))

    assert attempts == 2


async def test_a_retried_request_can_succeed() -> None:
    attempts = 0

    def responder(_request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(502)
        return httpx.Response(200, json={"ok": True})

    assert await build_client(responder, max_retries=1).get_json("/expenses", token=AccessToken("t")) == {
        "ok": True
    }
    assert attempts == 2


@pytest.mark.parametrize(
    ("status_code", "expected_error"),
    [
        (400, InvalidRequestError),
        (401, UnauthenticatedError),
        (403, UnauthenticatedError),
        (404, NotFoundError),
        (429, RateLimitedError),
    ],
)
async def test_client_errors_are_never_retried(status_code: int, expected_error: type[Exception]) -> None:
    attempts = 0

    def responder(_request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(status_code)

    with pytest.raises(expected_error):
        await build_client(responder, max_retries=3).get_json("/expenses", token=AccessToken("t"))

    assert attempts == 1


async def test_a_transport_error_is_retried_within_the_bound() -> None:
    attempts = 0

    def responder(_request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        raise httpx.ConnectError("spring is down")

    with pytest.raises(UpstreamUnavailableError):
        await build_client(responder, max_retries=2).get_json("/expenses", token=AccessToken("t"))

    assert attempts == 3
