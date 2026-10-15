"""Recurring-expense tool: the rules that generate expenses on a schedule.

Binds to the verified ``GET /recurring-expenses`` endpoint, which is not paged,
so the optional ``active`` filter is applied here and the result is capped.
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
    parse_upstream_list,
)

_RECURRING_PATH = "/recurring-expenses"


class RecurringExpenseArguments(ToolArguments):
    active: bool | None = Field(
        default=None,
        description="Restrict to active or to inactive rules. Omit to get both.",
    )


class RecurringExpense(UpstreamModel):
    """One recurring-expense rule as the existing API exposes it."""

    id: int
    category_id: int
    category_name: str
    amount: Decimal
    start_date: date
    next_execution_date: date | None = None
    description: str | None = None
    payment_method: str
    frequency: str
    active: bool


class RecurringExpenseResult(UpstreamModel):
    items: list[RecurringExpense]
    truncated: bool = False


async def get_recurring_expenses(
    client: ExpenseTrackerClient,
    context: UserContext,
    arguments: RecurringExpenseArguments,
) -> RecurringExpenseResult:
    payload = await client.get_json(
        _RECURRING_PATH,
        token=context.token,
        correlation_id=context.correlation_id,
    )
    rules = parse_upstream_list(payload, RecurringExpense, tool="get_recurring_expenses")
    matching = [rule for rule in rules if arguments.active is None or rule.active is arguments.active]

    return RecurringExpenseResult(
        items=matching[:MAX_LIST_ITEMS],
        truncated=len(matching) > MAX_LIST_ITEMS,
    )
