"""Expense tool tests: request mapping, response normalization and typed failures."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import httpx
import pytest

from app.core.errors import (
    InvalidRequestError,
    NotFoundError,
    RateLimitedError,
    UnauthenticatedError,
    UpstreamUnavailableError,
)
from app.tools.expenses import (
    ExpenseSearchArguments,
    ExpenseSortField,
    SortDirection,
    SpendingSummaryArguments,
    get_spending_summary,
    search_expenses,
)
from tests.conftest import CORRELATION_ID, StubbedUpstream

SUMMARY_BODY: dict[str, object] = {
    "totalAmount": 120.5,
    "transactionCount": 3,
    "startDate": "2026-01-01",
    "endDate": "2026-01-31",
}

EXPENSE_BODY: dict[str, object] = {
    "id": 11,
    "categoryId": 2,
    "categoryName": "Food",
    "amount": "18.40",
    "expenseDate": "2026-02-03",
    "description": "Lunch",
    "paymentMethod": "CARD",
}


def page_body(*, last: bool, content: list[object] | None = None) -> dict[str, object]:
    return {
        "content": content if content is not None else [EXPENSE_BODY],
        "page": 0,
        "size": 1,
        "totalElements": 42,
        "totalPages": 42,
        "first": True,
        "last": last,
        "empty": False,
    }


async def test_spending_summary_sends_only_the_filters_it_was_given(upstream: StubbedUpstream) -> None:
    upstream.respond_with(200, SUMMARY_BODY)

    result = await get_spending_summary(
        upstream.client,
        upstream.context,
        SpendingSummaryArguments(
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
            category_id=4,
            min_amount=Decimal("10.50"),
            max_amount=Decimal("99"),
            search="coffee",
        ),
    )

    request = upstream.only_request()
    assert request.url.path == "/api/expenses/summary"
    assert dict(request.url.params) == {
        "startDate": "2026-01-01",
        "endDate": "2026-01-31",
        "categoryId": "4",
        "minAmount": "10.50",
        "maxAmount": "99",
        "search": "coffee",
    }
    assert result.total_amount == Decimal("120.5")
    assert result.transaction_count == 3
    assert result.start_date == date(2026, 1, 1)
    assert result.end_date == date(2026, 1, 31)


async def test_spending_summary_forwards_the_token_and_correlation_id(upstream: StubbedUpstream) -> None:
    upstream.respond_with(200, SUMMARY_BODY)

    await get_spending_summary(upstream.client, upstream.context, SpendingSummaryArguments())

    request = upstream.only_request()
    assert request.headers["authorization"] == "Bearer token-1"
    assert request.headers["x-correlation-id"] == CORRELATION_ID


async def test_spending_summary_without_filters_sends_no_query_parameters(upstream: StubbedUpstream) -> None:
    upstream.respond_with(200, SUMMARY_BODY)

    await get_spending_summary(upstream.client, upstream.context, SpendingSummaryArguments())

    assert dict(upstream.only_request().url.params) == {}


async def test_spending_summary_keeps_an_open_ended_period_open(upstream: StubbedUpstream) -> None:
    upstream.respond_with(200, SUMMARY_BODY)

    await get_spending_summary(
        upstream.client,
        upstream.context,
        SpendingSummaryArguments(start_date=date(2026, 1, 1)),
    )

    assert dict(upstream.only_request().url.params) == {"startDate": "2026-01-01"}


async def test_search_expenses_sends_pagination_and_default_ordering(upstream: StubbedUpstream) -> None:
    upstream.respond_with(200, page_body(last=False))

    result = await search_expenses(upstream.client, upstream.context, ExpenseSearchArguments())

    assert upstream.only_request().url.path == "/api/expenses"
    assert dict(upstream.only_request().url.params) == {
        "page": "0",
        "size": "10",
        "sortBy": "expenseDate",
        "sortDir": "desc",
    }
    assert result.page == 0
    assert result.total_elements == 42
    assert result.has_more is True


async def test_search_expenses_normalizes_items_and_reports_the_last_page(upstream: StubbedUpstream) -> None:
    upstream.respond_with(200, page_body(last=True))

    result = await search_expenses(
        upstream.client,
        upstream.context,
        ExpenseSearchArguments(size=1, sort_by=ExpenseSortField.AMOUNT, sort_dir=SortDirection.ASC),
    )

    assert dict(upstream.only_request().url.params)["sortBy"] == "amount"
    assert result.has_more is False
    assert result.items[0].id == 11
    assert result.items[0].category_name == "Food"
    assert result.items[0].amount == Decimal("18.40")
    assert result.items[0].expense_date == date(2026, 2, 3)
    assert result.items[0].payment_method == "CARD"


async def test_search_expenses_accepts_a_missing_optional_description(upstream: StubbedUpstream) -> None:
    upstream.respond_with(
        200,
        page_body(
            last=True,
            content=[{**EXPENSE_BODY, "description": None, "paymentMethod": None}],
        ),
    )

    result = await search_expenses(upstream.client, upstream.context, ExpenseSearchArguments())

    assert result.items[0].description is None
    assert result.items[0].payment_method is None


@pytest.mark.parametrize(
    ("status_code", "expected_error"),
    [
        (400, InvalidRequestError),
        (401, UnauthenticatedError),
        (403, UnauthenticatedError),
        (404, NotFoundError),
        (429, RateLimitedError),
        (500, UpstreamUnavailableError),
        (503, UpstreamUnavailableError),
    ],
)
async def test_spending_summary_surfaces_typed_upstream_failures(
    status_code: int,
    expected_error: type[Exception],
    upstream: StubbedUpstream,
) -> None:
    upstream.respond_with(status_code)

    with pytest.raises(expected_error):
        await get_spending_summary(upstream.client, upstream.context, SpendingSummaryArguments())


@pytest.mark.parametrize("body", [{"total": 1}, [], "not-an-object", {"totalAmount": "free"}])
async def test_spending_summary_treats_payload_drift_as_unavailable(
    body: object,
    upstream: StubbedUpstream,
) -> None:
    upstream.respond_with(200, body)

    with pytest.raises(UpstreamUnavailableError):
        await get_spending_summary(upstream.client, upstream.context, SpendingSummaryArguments())


async def test_search_expenses_treats_an_unpaged_payload_as_unavailable(upstream: StubbedUpstream) -> None:
    upstream.respond_with(200, [EXPENSE_BODY])

    with pytest.raises(UpstreamUnavailableError):
        await search_expenses(upstream.client, upstream.context, ExpenseSearchArguments())


async def test_a_transport_failure_becomes_an_unavailable_upstream(upstream: StubbedUpstream) -> None:
    def responder(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("spring is down")

    upstream.respond_from(responder)

    with pytest.raises(UpstreamUnavailableError):
        await get_spending_summary(upstream.client, upstream.context, SpendingSummaryArguments())
