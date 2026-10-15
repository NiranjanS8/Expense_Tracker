"""Insights tool tests, including the nullable parts of a month with no spending."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.core.errors import InvalidRequestError, UpstreamUnavailableError
from app.tools.insights import ExistingInsightsArguments, get_existing_insights
from tests.conftest import StubbedUpstream

INSIGHTS_BODY: dict[str, object] = {
    "month": "2026-02",
    "currentMonthTotal": 300.0,
    "previousMonthTotal": 250.0,
    "absoluteChange": 50.0,
    "percentageChange": 20.0,
    "averageDailySpend": 10.71,
    "topCategory": {"categoryId": 2, "categoryName": "Food", "totalAmount": 210.25},
    "topCategorySharePercentage": 70.08,
    "largestExpense": {
        "id": 5,
        "categoryId": 2,
        "categoryName": "Food",
        "amount": "80.00",
        "expenseDate": "2026-02-03",
        "description": "Dinner",
        "paymentMethod": "CARD",
    },
    "insights": [
        {"type": "comparison", "title": "Spending increased", "message": "Spending is up by 50.00."},
    ],
}

EMPTY_MONTH_BODY: dict[str, object] = {
    **INSIGHTS_BODY,
    "currentMonthTotal": 0.0,
    "previousMonthTotal": 0.0,
    "absoluteChange": 0.0,
    "percentageChange": 0.0,
    "averageDailySpend": 0.0,
    "topCategory": None,
    "topCategorySharePercentage": 0.0,
    "largestExpense": None,
    "insights": [{"type": "summary", "title": "No spending recorded", "message": "No expenses."}],
}


async def test_insights_are_read_for_the_requested_month(upstream: StubbedUpstream) -> None:
    upstream.respond_with(200, INSIGHTS_BODY)

    result = await get_existing_insights(
        upstream.client,
        upstream.context,
        ExistingInsightsArguments(month="2026-02"),
    )

    assert upstream.only_request().url.path == "/api/insights/summary"
    assert dict(upstream.only_request().url.params) == {"month": "2026-02"}
    assert result.month == "2026-02"
    assert result.percentage_change == Decimal("20.0")
    assert result.top_category is not None
    assert result.top_category.category_name == "Food"
    assert result.largest_expense is not None
    assert result.insights[0].title == "Spending increased"


async def test_insights_for_a_month_without_spending_are_accepted(upstream: StubbedUpstream) -> None:
    upstream.respond_with(200, EMPTY_MONTH_BODY)

    result = await get_existing_insights(upstream.client, upstream.context, ExistingInsightsArguments())

    assert dict(upstream.only_request().url.params) == {}
    assert result.top_category is None
    assert result.largest_expense is None
    assert result.current_month_total == Decimal("0.0")


async def test_a_future_month_is_surfaced_as_an_invalid_request(upstream: StubbedUpstream) -> None:
    upstream.respond_with(400)

    with pytest.raises(InvalidRequestError, match="future month"):
        await get_existing_insights(
            upstream.client,
            upstream.context,
            ExistingInsightsArguments(month="2100-12"),
        )


async def test_an_unexpected_payload_is_unavailable(upstream: StubbedUpstream) -> None:
    upstream.respond_with(200, {"month": "2026-02"})

    with pytest.raises(UpstreamUnavailableError):
        await get_existing_insights(upstream.client, upstream.context, ExistingInsightsArguments())
