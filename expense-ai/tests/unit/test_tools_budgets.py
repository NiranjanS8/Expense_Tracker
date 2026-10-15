"""Budget tool tests, including the two different ways Spring Boot says "no budget"."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.core.errors import UpstreamUnavailableError
from app.tools.budgets import BudgetStatusArguments, get_budget_status
from app.tools.common import MAX_LIST_ITEMS
from tests.conftest import StubbedUpstream

BUDGET_BODY: dict[str, object] = {
    "id": 7,
    "budgetAmount": 500.0,
    "budgetMonth": "2026-03",
    "spentAmount": 320.0,
    "remainingAmount": 180.0,
    "overBudgetAmount": 0.0,
    "usagePercentage": 64.0,
    "exceeded": False,
    "hasRemainingBudget": True,
    "status": "ON_TRACK",
    "alertLevel": "NONE",
    "alertMessage": "Budget is within the safe spending range.",
    "triggeredThresholds": [],
}

NO_BUDGET_BODY: dict[str, object] = {
    **BUDGET_BODY,
    "id": None,
    "budgetAmount": 0.0,
    "spentAmount": 0.0,
    "remainingAmount": 0.0,
    "usagePercentage": 0.0,
    "hasRemainingBudget": False,
    "alertMessage": "No budget has been set for this month yet.",
}


def budgets(count: int) -> list[dict[str, object]]:
    return [{**BUDGET_BODY, "id": index} for index in range(count)]


async def test_a_named_month_reads_that_month(upstream: StubbedUpstream) -> None:
    upstream.respond_with(200, BUDGET_BODY)

    result = await get_budget_status(
        upstream.client, upstream.context, BudgetStatusArguments(month="2026-03")
    )

    assert upstream.only_request().url.path == "/api/budgets/2026-03"
    assert result.month == "2026-03"
    assert result.has_budget is True
    assert result.budgets[0].remaining_amount == Decimal("180.0")
    assert result.budgets[0].triggered_thresholds == []


async def test_a_month_without_a_budget_is_an_answer_not_a_failure(upstream: StubbedUpstream) -> None:
    upstream.respond_with(404)

    result = await get_budget_status(
        upstream.client, upstream.context, BudgetStatusArguments(month="2026-03")
    )

    assert result.month == "2026-03"
    assert result.has_budget is False
    assert result.budgets == []
    assert len(upstream.requests) == 1


async def test_the_current_month_is_read_from_its_own_endpoint(upstream: StubbedUpstream) -> None:
    upstream.respond_with(200, BUDGET_BODY)

    result = await get_budget_status(upstream.client, upstream.context, BudgetStatusArguments())

    assert upstream.only_request().url.path == "/api/budgets/current"
    assert result.has_budget is True
    assert result.month == "2026-03"


async def test_an_unset_current_month_normalizes_to_the_same_shape(upstream: StubbedUpstream) -> None:
    upstream.respond_with(200, NO_BUDGET_BODY)

    result = await get_budget_status(upstream.client, upstream.context, BudgetStatusArguments())

    assert result.has_budget is False
    assert result.budgets == []
    assert result.month == "2026-03"


async def test_a_year_reads_the_history_endpoint(upstream: StubbedUpstream) -> None:
    upstream.respond_with(200, budgets(3))

    result = await get_budget_status(upstream.client, upstream.context, BudgetStatusArguments(year=2026))

    assert upstream.only_request().url.path == "/api/budgets"
    assert dict(upstream.only_request().url.params) == {"year": "2026"}
    assert result.year == 2026
    assert result.has_budget is True
    assert len(result.budgets) == 3
    assert result.truncated is False


async def test_a_year_without_budgets_reports_no_budget(upstream: StubbedUpstream) -> None:
    upstream.respond_with(200, [])

    result = await get_budget_status(upstream.client, upstream.context, BudgetStatusArguments(year=2026))

    assert result.has_budget is False
    assert result.budgets == []


async def test_history_is_capped_and_flagged_as_truncated(upstream: StubbedUpstream) -> None:
    upstream.respond_with(200, budgets(MAX_LIST_ITEMS + 1))

    result = await get_budget_status(upstream.client, upstream.context, BudgetStatusArguments(year=2026))

    assert len(result.budgets) == MAX_LIST_ITEMS
    assert result.truncated is True


async def test_a_named_month_takes_precedence_over_a_year(upstream: StubbedUpstream) -> None:
    upstream.respond_with(200, BUDGET_BODY)

    await get_budget_status(
        upstream.client,
        upstream.context,
        BudgetStatusArguments(month="2026-03", year=2026),
    )

    assert upstream.only_request().url.path == "/api/budgets/2026-03"


async def test_an_unexpected_history_payload_is_unavailable(upstream: StubbedUpstream) -> None:
    upstream.respond_with(200, {"budgets": []})

    with pytest.raises(UpstreamUnavailableError):
        await get_budget_status(upstream.client, upstream.context, BudgetStatusArguments(year=2026))
