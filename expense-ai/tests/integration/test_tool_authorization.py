"""Cross-user authorization tests for the tool layer.

The property under test is that identity comes from the verified bearer token and
from nowhere else: not from tool arguments, not from chat text, and not from
anything the model can influence.
"""

from __future__ import annotations

import httpx
import pytest

from app.core.errors import InvalidRequestError, NotFoundError, UnauthenticatedError
from app.tools import build_tool_registry
from tests.conftest import Harness

GOAL_BODY: dict[str, object] = {
    "id": 3,
    "name": "Emergency fund",
    "targetAmount": 6000.0,
    "currentAmount": 1500.0,
    "remainingAmount": 4500.0,
    "progressPercentage": 25.0,
    "requiredMonthlyContribution": 500.0,
    "targetDate": "2026-12-31",
    "status": "ON_TRACK",
}

IDENTITY_PROPERTY_NAMES = frozenset({"userId", "user_id", "email", "role", "ownerId", "owner_id"})


def test_no_registered_tool_can_be_told_whose_data_to_read() -> None:
    for definition in build_tool_registry().definitions:
        assert not IDENTITY_PROPERTY_NAMES & set(definition.arguments_schema()["properties"])


async def test_the_token_alone_decides_whose_data_is_read(harness: Harness) -> None:
    presented_tokens: list[str] = []

    def responder(request: httpx.Request) -> httpx.Response:
        presented_tokens.append(request.headers["authorization"])
        return httpx.Response(200, json=GOAL_BODY)

    harness.responder = responder

    with harness:
        registry = harness.app.state.tool_registry
        client = harness.app.state.expense_tracker_client

        for token in ("alice-token", "bob-token"):
            await registry.execute(
                "get_goal_progress",
                client=client,
                context=harness.tool_context(token=token),
                arguments={"goal_id": 3},
            )

    assert presented_tokens == ["Bearer alice-token", "Bearer bob-token"]
    assert all(not request.url.params for request in harness.requests)
    assert all("userId" not in str(request.url) for request in harness.requests)


async def test_an_identity_argument_is_rejected_before_the_authority_is_called(harness: Harness) -> None:
    harness.responder = lambda _request: httpx.Response(200, json=GOAL_BODY)

    with harness:
        registry = harness.app.state.tool_registry
        with pytest.raises(InvalidRequestError):
            await registry.execute(
                "get_goal_progress",
                client=harness.app.state.expense_tracker_client,
                context=harness.tool_context(token="alice-token"),
                arguments={"goal_id": 3, "userId": 2},
            )

    assert harness.requests == []


async def test_another_users_resource_is_reported_as_missing_without_leaking_data(harness: Harness) -> None:
    harness.responder = lambda _request: httpx.Response(404)

    with harness:
        registry = harness.app.state.tool_registry
        with pytest.raises(NotFoundError) as error:
            await registry.execute(
                "get_goal_progress",
                client=harness.app.state.expense_tracker_client,
                context=harness.tool_context(token="alice-token"),
                arguments={"goal_id": 999},
            )

    assert error.value.status_code == 404
    assert error.value.details == []


async def test_an_invalid_token_is_reported_as_unauthenticated_not_forbidden(harness: Harness) -> None:
    # Spring Boot answers a bad token with 403 and an empty body; the AI service
    # normalizes that to 401 so the client sees one consistent signal.
    harness.responder = lambda _request: httpx.Response(403)

    with harness:
        registry = harness.app.state.tool_registry
        with pytest.raises(UnauthenticatedError):
            await registry.execute(
                "get_goal_progress",
                client=harness.app.state.expense_tracker_client,
                context=harness.tool_context(token="stale-token"),
                arguments={"goal_id": 3},
            )
