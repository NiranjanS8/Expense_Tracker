"""Recurring-expense tool tests.

The endpoint is not paged and takes no filters, so the ``active`` filter is
applied here and the result is capped.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.core.errors import UpstreamUnavailableError
from app.tools.common import MAX_LIST_ITEMS
from app.tools.recurring import RecurringExpenseArguments, get_recurring_expenses
from tests.conftest import StubbedUpstream

RULE_BODY: dict[str, object] = {
    "id": 4,
    "categoryId": 2,
    "categoryName": "Subscriptions",
    "amount": "12.99",
    "startDate": "2025-01-01",
    "nextExecutionDate": "2026-11-01",
    "description": "Music streaming",
    "paymentMethod": "CARD",
    "frequency": "MONTHLY",
    "active": True,
}


def rules(count: int) -> list[dict[str, object]]:
    return [{**RULE_BODY, "id": index} for index in range(count)]


async def test_rules_are_read_without_query_parameters(upstream: StubbedUpstream) -> None:
    upstream.respond_with(200, [RULE_BODY])

    result = await get_recurring_expenses(upstream.client, upstream.context, RecurringExpenseArguments())

    assert upstream.only_request().url.path == "/api/recurring-expenses"
    assert dict(upstream.only_request().url.params) == {}
    assert result.items[0].frequency == "MONTHLY"
    assert result.items[0].amount == Decimal("12.99")
    assert result.items[0].next_execution_date == date(2026, 11, 1)
    assert result.items[0].active is True


async def test_the_active_filter_is_applied_without_changing_the_request(upstream: StubbedUpstream) -> None:
    upstream.respond_with(200, [{**RULE_BODY, "active": True}, {**RULE_BODY, "id": 5, "active": False}])

    result = await get_recurring_expenses(
        upstream.client,
        upstream.context,
        RecurringExpenseArguments(active=False),
    )

    assert dict(upstream.only_request().url.params) == {}
    assert [rule.id for rule in result.items] == [5]


async def test_rules_are_capped_and_flagged(upstream: StubbedUpstream) -> None:
    upstream.respond_with(200, rules(MAX_LIST_ITEMS + 1))

    result = await get_recurring_expenses(upstream.client, upstream.context, RecurringExpenseArguments())

    assert len(result.items) == MAX_LIST_ITEMS
    assert result.truncated is True


async def test_an_unexpected_payload_is_unavailable(upstream: StubbedUpstream) -> None:
    upstream.respond_with(200, {"rules": []})

    with pytest.raises(UpstreamUnavailableError):
        await get_recurring_expenses(upstream.client, upstream.context, RecurringExpenseArguments())
