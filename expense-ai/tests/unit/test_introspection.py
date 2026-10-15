from __future__ import annotations

from collections.abc import Callable

import httpx

from app.core.security import AccessToken
from app.identity.introspection import IdentityResolver
from app.integrations.expense_tracker_client import ExpenseTrackerClient

Responder = Callable[[httpx.Request], httpx.Response]


def build_resolver(responder: Responder, *, ttl_seconds: int) -> tuple[IdentityResolver, list[httpx.Request]]:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return responder(request)

    client = ExpenseTrackerClient(
        base_url="http://spring.test",
        context_path="/api",
        timeout_seconds=1.0,
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    return IdentityResolver(client, ttl_seconds=ttl_seconds), calls


def ok_responder(_request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"id": 5, "email": "cached@example.com", "role": "USER"})


async def test_resolver_caches_identity_within_ttl() -> None:
    resolver, calls = build_resolver(ok_responder, ttl_seconds=60)
    token = AccessToken("same-token")

    first = await resolver.resolve(token)
    second = await resolver.resolve(token)

    assert first == second
    assert len(calls) == 1


async def test_resolver_skips_cache_when_ttl_disabled() -> None:
    resolver, calls = build_resolver(ok_responder, ttl_seconds=0)
    token = AccessToken("same-token")

    await resolver.resolve(token)
    await resolver.resolve(token)

    assert len(calls) == 2


async def test_distinct_tokens_are_cached_separately() -> None:
    resolver, calls = build_resolver(ok_responder, ttl_seconds=60)

    await resolver.resolve(AccessToken("token-a"))
    await resolver.resolve(AccessToken("token-b"))

    assert len(calls) == 2


async def test_evict_removes_a_cached_identity() -> None:
    resolver, calls = build_resolver(ok_responder, ttl_seconds=60)
    token = AccessToken("same-token")

    await resolver.resolve(token)
    resolver.evict(token)
    await resolver.resolve(token)

    assert len(calls) == 2
