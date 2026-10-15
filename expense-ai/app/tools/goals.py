"""Savings-goal tool: progress for one goal or for every goal.

Binds to the verified ``GET /goals`` endpoints. A goal that belongs to somebody
else is indistinguishable from a goal that does not exist: Spring Boot scopes the
lookup by the token owner and answers ``404`` either way.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import Field

from app.identity.user_context import UserContext
from app.integrations.expense_tracker_client import ExpenseTrackerClient
from app.tools.common import (
    MAX_LIST_ITEMS,
    ToolArguments,
    UpstreamModel,
    parse_upstream,
    parse_upstream_list,
)

_GOALS_PATH = "/goals"


class GoalProgressArguments(ToolArguments):
    goal_id: int | None = Field(
        default=None,
        ge=1,
        description="A single goal by id. Omit to list every goal of the current user.",
    )


class GoalSummary(UpstreamModel):
    """One goal with the backend's progress and contribution calculations."""

    id: int
    name: str
    target_amount: Decimal
    current_amount: Decimal
    remaining_amount: Decimal
    progress_percentage: Decimal
    required_monthly_contribution: Decimal
    target_date: date
    status: str


class GoalProgressResult(UpstreamModel):
    goals: list[GoalSummary]
    truncated: bool = False


async def get_goal_progress(
    client: ExpenseTrackerClient,
    context: UserContext,
    arguments: GoalProgressArguments,
) -> GoalProgressResult:
    if arguments.goal_id is not None:
        payload = await client.get_json(
            f"{_GOALS_PATH}/{arguments.goal_id}",
            token=context.token,
            correlation_id=context.correlation_id,
            missing_message="No goal with that id exists for the current user.",
        )
        return GoalProgressResult(goals=[parse_upstream(payload, GoalSummary, tool="get_goal_progress")])

    payload = await client.get_json(
        _GOALS_PATH,
        token=context.token,
        correlation_id=context.correlation_id,
    )
    goals = parse_upstream_list(payload, GoalSummary, tool="get_goal_progress")

    return GoalProgressResult(goals=goals[:MAX_LIST_ITEMS], truncated=len(goals) > MAX_LIST_ITEMS)
