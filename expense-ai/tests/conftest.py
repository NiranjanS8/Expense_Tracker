"""Shared fixtures.

Spring Boot is stubbed with an explicit ``httpx.MockTransport`` rather than a
global HTTP patch, so each test controls exactly how the upstream authority
responds and tests never touch the network.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Callable, Iterator
from types import TracebackType
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.conversations.database import Database
from app.conversations.repository import ConversationRepository
from app.core.config import ProviderName, Settings
from app.core.security import AccessToken
from app.identity.introspection import IdentityResolver
from app.identity.user_context import UserContext
from app.integrations.expense_tracker_client import AuthenticatedUser, ExpenseTrackerClient
from app.integrations.model_provider import ChatResponse, FakeModelProvider, ModelProvider
from app.main import create_app

SPRING_BASE_URL = "http://spring.test"
CURRENT_USER_PATH = "/api/users/me"
CORRELATION_ID = "corr-test"
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

Responder = Callable[[httpx.Request], httpx.Response]


def parse_sse(body: str) -> list[tuple[str, dict[str, Any]]]:
    """Decode an SSE body into ``(event_name, data)`` pairs."""
    events: list[tuple[str, dict[str, Any]]] = []
    for block in body.split("\n\n"):
        if not block.strip():
            continue
        name: str | None = None
        data: dict[str, Any] = {}
        for line in block.splitlines():
            if line.startswith("event: "):
                name = line[len("event: ") :]
            elif line.startswith("data: "):
                data = json.loads(line[len("data: ") :])
        if name is not None:
            events.append((name, data))
    return events


def build_user_context(*, user_id: int = 1, token: str = "token-1") -> UserContext:
    """The trusted context that a chat request would hand to a tool call."""
    return UserContext(
        user=AuthenticatedUser(user_id=user_id, email="demo@expensetracker.com", role="USER"),
        token=AccessToken(token),
        correlation_id=CORRELATION_ID,
    )


class StubbedUpstream:
    """A stubbed Spring Boot plus the trusted context a tool call would receive.

    The client is the real one, configured exactly as the application configures
    it, with only the transport replaced. Tests therefore assert on the request
    that would actually be sent, not on a mocked-out method call.
    """

    def __init__(self, *, user_id: int = 1, token: str = "token-1") -> None:
        self.requests: list[httpx.Request] = []
        self.responder: Responder = lambda _request: httpx.Response(404)
        self.client = ExpenseTrackerClient(
            base_url=SPRING_BASE_URL,
            context_path="/api",
            timeout_seconds=1.0,
            client=httpx.AsyncClient(transport=httpx.MockTransport(self._handle)),
        )
        self.context = build_user_context(user_id=user_id, token=token)

    def respond_with(self, status_code: int, body: object | None = None) -> None:
        """Answer every request with one status, and JSON only when given a body."""
        self.responder = lambda _request: httpx.Response(status_code, json=body)

    def respond_from(self, responder: Responder) -> None:
        self.responder = responder

    def paths(self) -> list[str]:
        return [request.url.path for request in self.requests]

    def only_request(self) -> httpx.Request:
        assert len(self.requests) == 1, f"expected exactly one upstream call, got {len(self.requests)}"
        return self.requests[0]

    def _handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self.responder(request)


@pytest.fixture
def upstream() -> StubbedUpstream:
    return StubbedUpstream()


class Harness:
    """Wraps the running app plus a stubbed upstream Spring Boot API."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.requests: list[httpx.Request] = []
        self.responder: Responder = lambda _request: httpx.Response(404)
        self.app: FastAPI = create_app(settings)
        self._upstream = httpx.AsyncClient(transport=httpx.MockTransport(self._handle))
        self.expense_tracker_client = ExpenseTrackerClient(
            base_url=SPRING_BASE_URL,
            context_path="/api",
            timeout_seconds=1.0,
            client=self._upstream,
        )
        self.resolver = IdentityResolver(
            self.expense_tracker_client,
            ttl_seconds=settings.identity_cache_ttl_seconds,
        )
        self.client = TestClient(self.app)

    def __enter__(self) -> Harness:
        self.client.__enter__()
        self.app.state.identity_resolver = self.resolver
        self.app.state.expense_tracker_client = self.expense_tracker_client
        self.repository = self.app.state.conversation_repository
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

    def respond_from(self, responder: Responder) -> None:
        """Answer upstream requests with a routing function instead of one status."""
        self.responder = responder

    def paths(self) -> list[str]:
        return [request.url.path for request in self.requests]

    def tool_context(self, *, user_id: int = 1, token: str = "token-1") -> UserContext:
        """The trusted context the app would build for an authenticated caller."""
        return build_user_context(user_id=user_id, token=token)

    def use_model(self, provider: ModelProvider) -> None:
        """Replace the model provider the compiled graph resolves per request."""
        self.app.state.model_provider = provider

    def script_model(self, *responses: ChatResponse) -> FakeModelProvider:
        """Install a fake provider that returns scripted responses in order."""
        provider = FakeModelProvider(scripted_responses=list(responses))
        self.app.state.model_provider = provider
        return provider


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,
        llm_provider=ProviderName.FAKE,
        expense_tracker_base_url=SPRING_BASE_URL,
        identity_cache_ttl_seconds=0,
        max_request_bytes=1024,
        chat_rate_limit_per_minute=3,
        database_url=TEST_DATABASE_URL,
        auto_create_schema=True,
    )


@pytest.fixture
def harness(settings: Settings) -> Iterator[Harness]:
    with Harness(settings) as instance:
        yield instance


@pytest.fixture
async def database() -> AsyncIterator[Database]:
    """A fresh in-memory schema per test, no external service required."""
    instance = Database(TEST_DATABASE_URL, auto_create_schema=True)
    await instance.start()
    try:
        yield instance
    finally:
        await instance.dispose()


@pytest.fixture
async def repository(database: Database) -> ConversationRepository:
    return ConversationRepository(database)
