"""Dashboard tool tests: month resolution, category totals and recent transactions."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.core.errors import UnauthenticatedError, UpstreamUnavailableError
from app.tools.dashboard import (
    CategoryBreakdownArguments,
    DashboardSummaryArguments,
    get_category_breakdown,
    get_dashboard_summary,
)
from tests.conftest import StubbedUpstream

CATEGORIES_BODY: list[dict[str, object]] = [
    {"categoryId": 2, "categoryName": "Food", "totalAmount": 210.25},
    {"categoryId": 3, "categoryName": "Transport", "totalAmount": 89.75},
]

DASHBOARD_BODY: dict[str, object] = {
    "month": "2026-02",
    "monthlyTotal": 300.0,
    "transactionCount": 12,
    "recentTransactions": [
        {
            "id": 5,
            "categoryId": 2,
            "categoryName": "Food",
            "amount": "18.40",
            "expenseDate": "2026-02-03",
            "description": "Lunch",
            "paymentMethod": "CARD",
        }
    ],
}


async def test_category_breakdown_sends_the_requested_month(upstream: StubbedUpstream) -> None:
    upstream.respond_with(200, CATEGORIES_BODY)

    result = await get_category_breakdown(
        upstream.client,
        upstream.context,
        CategoryBreakdownArguments(month="2026-02"),
    )

    assert upstream.only_request().url.path == "/api/dashboard/categories"
    assert dict(upstream.only_request().url.params) == {"month": "2026-02"}
    assert result.month == "2026-02"
    assert [category.category_name for category in result.categories] == ["Food", "Transport"]
    assert result.total_amount == Decimal("300.00")


async def test_category_breakdown_leaves_the_month_to_the_backend_when_omitted(
    upstream: StubbedUpstream,
) -> None:
    upstream.respond_with(200, CATEGORIES_BODY)

    result = await get_category_breakdown(upstream.client, upstream.context, CategoryBreakdownArguments())

    assert dict(upstream.only_request().url.params) == {}
    assert result.month is None


async def test_category_breakdown_of_an_empty_month_totals_zero(upstream: StubbedUpstream) -> None:
    upstream.respond_with(200, [])

    result = await get_category_breakdown(
        upstream.client,
        upstream.context,
        CategoryBreakdownArguments(month="2026-02"),
    )

    assert result.categories == []
    assert result.total_amount == Decimal("0")


async def test_dashboard_summary_reports_the_month_the_backend_resolved(upstream: StubbedUpstream) -> None:
    upstream.respond_with(200, DASHBOARD_BODY)

    result = await get_dashboard_summary(upstream.client, upstream.context, DashboardSummaryArguments())

    assert upstream.only_request().url.path == "/api/dashboard/summary"
    assert dict(upstream.only_request().url.params) == {"recentLimit": "5"}
    assert result.month == "2026-02"
    assert result.monthly_total == Decimal("300.0")
    assert result.transaction_count == 12
    assert result.recent_transactions[0].expense_date == date(2026, 2, 3)


async def test_dashboard_summary_sends_the_requested_month_and_limit(upstream: StubbedUpstream) -> None:
    upstream.respond_with(200, DASHBOARD_BODY)

    await get_dashboard_summary(
        upstream.client,
        upstream.context,
        DashboardSummaryArguments(month="2026-02", recent_limit=20),
    )

    assert dict(upstream.only_request().url.params) == {"month": "2026-02", "recentLimit": "20"}


async def test_dashboard_summary_rejects_an_unexpected_payload(upstream: StubbedUpstream) -> None:
    upstream.respond_with(200, {"month": "2026-02"})

    with pytest.raises(UpstreamUnavailableError):
        await get_dashboard_summary(upstream.client, upstream.context, DashboardSummaryArguments())


async def test_category_breakdown_surfaces_an_expired_token(upstream: StubbedUpstream) -> None:
    upstream.respond_with(403)

    with pytest.raises(UnauthenticatedError):
        await get_category_breakdown(
            upstream.client,
            upstream.context,
            CategoryBreakdownArguments(month="2026-02"),
        )
