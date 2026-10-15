"""Shared fixtures.

Spring Boot is stubbed with an explicit ``httpx.MockTransport`` rather than a
global HTTP patch, so each test controls exactly how the upstream authority
responds and tests never touch the network.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from types import TracebackType

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import ProviderName, Settings
from app.identity.introspection import IdentityResolver
from app.integrations.expense_tracker_client import ExpenseTrackerClient
from app.main import create_app

SPRING_BASE_URL = "http://spring.test"
CURRENT_USER_PATH = "/api/users/me"

Responder = Callable[[httpx.Request], httpx.Response]


class Harness:
    """Wraps the running app plus a stubbed upstream Spring Boot API."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.requests: list[httpx.Request] = []
        self.responder: Responder = lambda _request: httpx.Response(404)
        self.app: FastAPI = create_app(settings)
        self._upstream = httpx.AsyncClient(transport=httpx.MockTransport(self._handle))
        self.resolver = IdentityResolver(
            ExpenseTrackerClient(
                base_url=SPRING_BASE_URL,
                context_path="/api",
                timeout_seconds=1.0,
                client=self._upstream,
            ),
            ttl_seconds=settings.identity_cache_ttl_seconds,
        )
        self.client = TestClient(self.app)

    def __enter__(self) -> Harness:
        self.client.__enter__()
        self.app.state.identity_resolver = self.resolver
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.client.__exit__(exc_type, exc_value, traceback)

    def _handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self.responder(request)

    def authenticate(self, user_id: int = 1, email: str = "demo@expensetracker.com") -> None:
        """Make the upstream authority accept any token as this user."""

        def responder(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "id": user_id,
                    "fullName": "Demo User",
                    "email": email,
                    "role": "USER",
                },
            )

        self.responder = responder

    def requests_to(self, path: str) -> list[httpx.Request]:
        return [request for request in self.requests if request.url.path == path]


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,
        llm_provider=ProviderName.FAKE,
        expense_tracker_base_url=SPRING_BASE_URL,
        identity_cache_ttl_seconds=0,
        max_request_bytes=1024,
        chat_rate_limit_per_minute=3,
    )


@pytest.fixture
def harness(settings: Settings) -> Iterator[Harness]:
    with Harness(settings) as instance:
        yield instance
