"""Budget tool: one month's budget, the current month, or a year of history.

Binds to the verified ``GET /budgets`` endpoints. A month with no budget is a
normal answer rather than a failure, so the two shapes Spring Boot uses for it -
an empty summary for the current month, and a ``404`` for a named month - are
normalized to the same result.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import Field

from app.core.errors import NotFoundError
from app.identity.user_context import UserContext
from app.integrations.expense_tracker_client import ExpenseTrackerClient
from app.tools.common import (
    MAX_LIST_ITEMS,
    Month,
    ToolArguments,
    UpstreamModel,
    compact_params,
    parse_upstream,
    parse_upstream_list,
)

_HISTORY_PATH = "/budgets"
_CURRENT_PATH = "/budgets/current"

_NO_BUDGET_MESSAGE = "No budget has been set for that month."


class BudgetStatusArguments(ToolArguments):
    month: Month | None = Field(
        default=None,
        description="A single month as YYYY-MM. Omit together with year to get the current month.",
    )
    year: int | None = Field(
        default=None,
        ge=2000,
        le=2100,
        description="Return every budget of that year instead of a single month.",
    )


class BudgetSummary(UpstreamModel):
    """One month's budget with the backend's utilization and alert calculations."""

    id: int | None = None
    budget_amount: Decimal
    budget_month: Month
    spent_amount: Decimal
    remaining_amount: Decimal
    over_budget_amount: Decimal
    usage_percentage: Decimal
    exceeded: bool
    has_remaining_budget: bool
    status: str
    alert_level: str
    alert_message: str
    triggered_thresholds: list[int]


class BudgetStatusResult(UpstreamModel):
    """Whatever the requested scope resolved to, in one stable shape."""

    month: Month | None = None
    year: int | None = None
    has_budget: bool
    budgets: list[BudgetSummary]
    truncated: bool = False


async def get_budget_status(
    client: ExpenseTrackerClient,
    context: UserContext,
    arguments: BudgetStatusArguments,
) -> BudgetStatusResult:
    if arguments.month is not None:
        return await _single_month(client, context, arguments.month)

    if arguments.year is not None:
        return await _year_history(client, context, arguments.year)

    payload = await client.get_json(
        _CURRENT_PATH,
        token=context.token,
        correlation_id=context.correlation_id,
    )
    budget = parse_upstream(payload, BudgetSummary, tool="get_budget_status")
    # Spring Boot answers the current month with an id-less summary when the user
    # has no budget, so both no-budget cases produce the same shape.
    return BudgetStatusResult(
        month=budget.budget_month,
        has_budget=budget.id is not None,
        budgets=[] if budget.id is None else [budget],
    )


async def _single_month(
    client: ExpenseTrackerClient,
    context: UserContext,
    month: str,
) -> BudgetStatusResult:
    try:
        # ``month`` is pattern-validated by ``Month``, so it cannot escape the path.
        payload = await client.get_json(
            f"{_HISTORY_PATH}/{month}",
            token=context.token,
            correlation_id=context.correlation_id,
            missing_message=_NO_BUDGET_MESSAGE,
        )
    except NotFoundError:
        # Verified behaviour: this endpoint 404s only when the user has no budget
        # for that month, which is an answer rather than a failure.
        return BudgetStatusResult(month=month, has_budget=False, budgets=[])

    budget = parse_upstream(payload, BudgetSummary, tool="get_budget_status")
    return BudgetStatusResult(month=month, has_budget=True, budgets=[budget])


async def _year_history(
    client: ExpenseTrackerClient,
    context: UserContext,
    year: int,
) -> BudgetStatusResult:
    payload = await client.get_json(
        _HISTORY_PATH,
        token=context.token,
        params=compact_params({"year": year}),
        correlation_id=context.correlation_id,
    )
    budgets = parse_upstream_list(payload, BudgetSummary, tool="get_budget_status")

    return BudgetStatusResult(
        year=year,
        has_budget=bool(budgets),
        budgets=budgets[:MAX_LIST_ITEMS],
        truncated=len(budgets) > MAX_LIST_ITEMS,
    )
