from __future__ import annotations

import httpx
import pytest

from app.core.errors import UnauthenticatedError, UpstreamTimeoutError, UpstreamUnavailableError
from app.core.security import AccessToken
from app.integrations.expense_tracker_client import ExpenseTrackerClient


def build_client(responder) -> ExpenseTrackerClient:  # type: ignore[no-untyped-def]
    return ExpenseTrackerClient(
        base_url="http://spring.test",
        context_path="/api",
        timeout_seconds=1.0,
        client=httpx.AsyncClient(transport=httpx.MockTransport(responder)),
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
