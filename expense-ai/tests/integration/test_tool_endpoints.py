"""Acceptance tests: every registered tool maps to exactly one verified endpoint.

The tools are driven through the registry and the application's own HTTP client,
so a tool that reached outside the verified Spring Boot API - a database, another
service, a raw URL - would fail here.
"""

from __future__ import annotations

import httpx

from tests.conftest import Harness

TOOL_NAMES: tuple[str, ...] = (
    "get_spending_summary",
    "search_expenses",
    "get_category_breakdown",
    "get_budget_status",
    "get_goal_progress",
    "get_recurring_expenses",
    "get_dashboard_summary",
    "get_existing_insights",
)

VERIFIED_RESPONSES: dict[str, object] = {
    "/api/expenses/summary": {
        "totalAmount": 0.0,
        "transactionCount": 0,
        "startDate": None,
        "endDate": None,
    },
    "/api/expenses": {
        "content": [],
        "page": 0,
        "size": 10,
        "totalElements": 0,
        "totalPages": 0,
        "first": True,
        "last": True,
        "empty": True,
    },
    "/api/dashboard/categories": [],
    "/api/dashboard/summary": {
        "month": "2026-02",
        "monthlyTotal": 0.0,
        "transactionCount": 0,
        "recentTransactions": [],
    },
    "/api/budgets/current": {
        "id": None,
        "budgetAmount": 0.0,
        "budgetMonth": "2026-02",
        "spentAmount": 0.0,
        "remainingAmount": 0.0,
        "overBudgetAmount": 0.0,
        "usagePercentage": 0.0,
        "exceeded": False,
        "hasRemainingBudget": False,
        "status": "ON_TRACK",
        "alertLevel": "NONE",
        "alertMessage": "No budget has been set for this month yet.",
        "triggeredThresholds": [],
    },
    "/api/goals": [],
    "/api/recurring-expenses": [],
    "/api/insights/summary": {
        "month": "2026-02",
        "currentMonthTotal": 0.0,
        "previousMonthTotal": 0.0,
        "absoluteChange": 0.0,
        "percentageChange": 0.0,
        "averageDailySpend": 0.0,
        "topCategory": None,
        "topCategorySharePercentage": 0.0,
        "largestExpense": None,
        "insights": [],
    },
}


async def test_every_tool_reads_exactly_one_verified_endpoint(harness: Harness) -> None:
    def responder(request: httpx.Request) -> httpx.Response:
        assert request.url.path in VERIFIED_RESPONSES, f"unverified endpoint: {request.url.path}"
        return httpx.Response(200, json=VERIFIED_RESPONSES[request.url.path])

    harness.responder = responder

    with harness:
        registry = harness.app.state.tool_registry
        client = harness.app.state.expense_tracker_client
        for name in TOOL_NAMES:
            await registry.execute(name, client=client, context=harness.tool_context())

    assert sorted(harness.paths()) == sorted(VERIFIED_RESPONSES)
    assert {request.method for request in harness.requests} == {"GET"}


async def test_the_tool_allowlist_is_the_one_the_application_serves(harness: Harness) -> None:
    with harness:
        registry = harness.app.state.tool_registry

    assert tuple(definition.name for definition in registry.definitions) == TOOL_NAMES
