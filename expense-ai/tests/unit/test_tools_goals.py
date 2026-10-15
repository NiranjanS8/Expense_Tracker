"""Savings-goal tool tests."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.core.errors import NotFoundError, UpstreamUnavailableError
from app.tools.common import MAX_LIST_ITEMS
from app.tools.goals import GoalProgressArguments, get_goal_progress
from tests.conftest import StubbedUpstream

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


def goals(count: int) -> list[dict[str, object]]:
    return [{**GOAL_BODY, "id": index} for index in range(count)]


async def test_a_goal_id_reads_that_single_goal(upstream: StubbedUpstream) -> None:
    upstream.respond_with(200, GOAL_BODY)

    result = await get_goal_progress(upstream.client, upstream.context, GoalProgressArguments(goal_id=3))

    assert upstream.only_request().url.path == "/api/goals/3"
    assert len(result.goals) == 1
    assert result.goals[0].name == "Emergency fund"
    assert result.goals[0].remaining_amount == Decimal("4500.0")
    assert result.goals[0].target_date == date(2026, 12, 31)
    assert result.truncated is False


async def test_omitting_the_goal_id_lists_every_goal(upstream: StubbedUpstream) -> None:
    upstream.respond_with(200, goals(2))

    result = await get_goal_progress(upstream.client, upstream.context, GoalProgressArguments())

    assert upstream.only_request().url.path == "/api/goals"
    assert dict(upstream.only_request().url.params) == {}
    assert len(result.goals) == 2


async def test_a_goal_owned_by_somebody_else_is_indistinguishable_from_a_missing_one(
    upstream: StubbedUpstream,
) -> None:
    # Spring Boot scopes the lookup by token owner, so a foreign id is a 404.
    upstream.respond_with(404)

    with pytest.raises(NotFoundError):
        await get_goal_progress(upstream.client, upstream.context, GoalProgressArguments(goal_id=999))


async def test_goal_listing_is_capped_and_flagged(upstream: StubbedUpstream) -> None:
    upstream.respond_with(200, goals(MAX_LIST_ITEMS + 1))

    result = await get_goal_progress(upstream.client, upstream.context, GoalProgressArguments())

    assert len(result.goals) == MAX_LIST_ITEMS
    assert result.truncated is True


async def test_an_unexpected_goal_payload_is_unavailable(upstream: StubbedUpstream) -> None:
    upstream.respond_with(200, {"goals": []})

    with pytest.raises(UpstreamUnavailableError):
        await get_goal_progress(upstream.client, upstream.context, GoalProgressArguments())
