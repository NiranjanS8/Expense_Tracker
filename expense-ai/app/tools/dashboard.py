"""Dashboard tools: month totals and per-category breakdowns.

Both bind to verified ``GET /dashboard`` endpoints. The only value computed in
Python is the sum of the category rows Spring Boot already returned, which makes
the breakdown self-describing without a second call.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import Field

from app.identity.user_context import UserContext
from app.integrations.expense_tracker_client import ExpenseTrackerClient
from app.tools.common import (
    CategorySpending,
    ExpenseItem,
    Month,
    ToolArguments,
    UpstreamModel,
    compact_params,
    parse_upstream,
    parse_upstream_list,
)

_CATEGORY_PATH = "/dashboard/categories"
_SUMMARY_PATH = "/dashboard/summary"

_BACKEND_MONTH_NOTE = "Month as YYYY-MM. Omit to let the backend use its own current month."


class CategoryBreakdownArguments(ToolArguments):
    month: Month | None = Field(default=None, description=_BACKEND_MONTH_NOTE)


class DashboardSummaryArguments(ToolArguments):
    month: Month | None = Field(default=None, description=_BACKEND_MONTH_NOTE)
    recent_limit: int = Field(
        default=5,
        ge=1,
        le=20,
        description="How many of the most recent transactions of that month to include.",
    )


class CategoryBreakdown(UpstreamModel):
    """Spend per category for one month, largest first as the backend orders it."""

    month: Month | None = None
    categories: list[CategorySpending]
    total_amount: Decimal


class DashboardSummary(UpstreamModel):
    """The figures the application's own dashboard shows for a month."""

    month: Month
    monthly_total: Decimal
    transaction_count: int
    recent_transactions: list[ExpenseItem]


async def get_category_breakdown(
    client: ExpenseTrackerClient,
    context: UserContext,
    arguments: CategoryBreakdownArguments,
) -> CategoryBreakdown:
    payload = await client.get_json(
        _CATEGORY_PATH,
        token=context.token,
        params=compact_params({"month": arguments.month}),
        correlation_id=context.correlation_id,
    )
    categories = parse_upstream_list(payload, CategorySpending, tool="get_category_breakdown")

    return CategoryBreakdown(
        month=arguments.month,
        categories=categories,
        total_amount=sum((category.total_amount for category in categories), Decimal("0")),
    )


async def get_dashboard_summary(
    client: ExpenseTrackerClient,
    context: UserContext,
    arguments: DashboardSummaryArguments,
) -> DashboardSummary:
    params = compact_params({"month": arguments.month, "recentLimit": arguments.recent_limit})
    payload = await client.get_json(
        _SUMMARY_PATH,
        token=context.token,
        params=params,
        correlation_id=context.correlation_id,
    )
    return parse_upstream(payload, DashboardSummary, tool="get_dashboard_summary")
