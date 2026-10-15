"""Insights tool: the comparison and habit insights the application already shows.

Binds to the verified ``GET /insights/summary`` endpoint, which rejects months in
the future, so the tool surfaces that rejection rather than recomputing it from a
clock that may disagree with the backend's.
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
)

_INSIGHTS_PATH = "/insights/summary"


class ExistingInsightsArguments(ToolArguments):
    month: Month | None = Field(
        default=None,
        description=(
            "Month as YYYY-MM, at or before the current month. "
            "Omit to let the backend use its own current month."
        ),
    )


class InsightItem(UpstreamModel):
    """One pre-computed insight exactly as the backend phrased it."""

    type: str
    title: str
    message: str


class ExistingInsights(UpstreamModel):
    """A month measured against the month before it."""

    month: Month
    current_month_total: Decimal
    previous_month_total: Decimal
    absolute_change: Decimal
    percentage_change: Decimal
    average_daily_spend: Decimal
    top_category: CategorySpending | None = None
    top_category_share_percentage: Decimal
    largest_expense: ExpenseItem | None = None
    insights: list[InsightItem]


async def get_existing_insights(
    client: ExpenseTrackerClient,
    context: UserContext,
    arguments: ExistingInsightsArguments,
) -> ExistingInsights:
    payload = await client.get_json(
        _INSIGHTS_PATH,
        token=context.token,
        params=compact_params({"month": arguments.month}),
        correlation_id=context.correlation_id,
        invalid_message="Insights cannot be generated for a future month.",
    )
    return parse_upstream(payload, ExistingInsights, tool="get_existing_insights")
