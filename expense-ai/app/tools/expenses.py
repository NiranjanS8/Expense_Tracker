"""Expense tools: aggregated spending and paged expense search.

Both tools bind to verified ``GET /expenses`` endpoints, so every figure they
return is calculated by Spring Boot. No total is derived here.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum

from pydantic import Field, model_validator

from app.identity.user_context import UserContext
from app.integrations.expense_tracker_client import ExpenseTrackerClient
from app.tools.common import (
    MAX_PAGE_INDEX,
    MAX_PAGE_SIZE,
    MAX_SEARCH_LENGTH,
    ExpenseItem,
    ToolArguments,
    UpstreamModel,
    compact_params,
    decimal_param,
    parse_upstream,
    validate_amount_range,
    validate_date_range,
)

_SUMMARY_PATH = "/expenses/summary"
_EXPENSES_PATH = "/expenses"


class ExpenseSortField(StrEnum):
    """Sortable properties that exist on the expense entity."""

    EXPENSE_DATE = "expenseDate"
    AMOUNT = "amount"


class SortDirection(StrEnum):
    ASC = "asc"
    DESC = "desc"


class SpendingSummaryArguments(ToolArguments):
    """Filters for the spending summary. All of them are optional."""

    start_date: date | None = Field(
        default=None,
        description="Inclusive start of the period as YYYY-MM-DD. Omit for no lower bound.",
    )
    end_date: date | None = Field(
        default=None,
        description="Inclusive end of the period as YYYY-MM-DD. Omit for no upper bound.",
    )
    category_id: int | None = Field(default=None, ge=1, description="Restrict the totals to one category id.")
    min_amount: Decimal | None = Field(
        default=None, ge=0, description="Only expenses of at least this amount."
    )
    max_amount: Decimal | None = Field(
        default=None, ge=0, description="Only expenses of at most this amount."
    )
    search: str | None = Field(
        default=None,
        max_length=MAX_SEARCH_LENGTH,
        description="Case-insensitive substring matched against the expense description.",
    )

    @model_validator(mode="after")
    def _check_ranges(self) -> SpendingSummaryArguments:
        validate_date_range(self.start_date, self.end_date)
        validate_amount_range(self.min_amount, self.max_amount)
        return self


class ExpenseSearchArguments(SpendingSummaryArguments):
    """The same filters plus pagination and ordering for listing expenses."""

    page: int = Field(default=0, ge=0, le=MAX_PAGE_INDEX, description="Zero-based page index.")
    size: int = Field(default=10, ge=1, le=MAX_PAGE_SIZE, description="Page size, at most 100.")
    sort_by: ExpenseSortField = Field(
        default=ExpenseSortField.EXPENSE_DATE, description="Property to order by."
    )
    sort_dir: SortDirection = Field(default=SortDirection.DESC, description="Ascending or descending order.")


class SpendingSummary(UpstreamModel):
    """Totals for the expenses matching the applied filters."""

    total_amount: Decimal
    transaction_count: int
    start_date: date | None = None
    end_date: date | None = None


class ExpenseSearchResult(UpstreamModel):
    """One page of expenses plus enough metadata to ask for the next page."""

    items: list[ExpenseItem]
    page: int
    size: int
    total_elements: int
    total_pages: int
    has_more: bool


class _ExpensePage(UpstreamModel):
    """Shape of ``PagedResponse<ExpenseResponse>`` as Spring Boot serializes it."""

    content: list[ExpenseItem]
    page: int
    size: int
    total_elements: int
    total_pages: int
    last: bool


async def get_spending_summary(
    client: ExpenseTrackerClient,
    context: UserContext,
    arguments: SpendingSummaryArguments,
) -> SpendingSummary:
    payload = await client.get_json(
        _SUMMARY_PATH,
        token=context.token,
        params=_filter_params(arguments),
        correlation_id=context.correlation_id,
    )
    return parse_upstream(payload, SpendingSummary, tool="get_spending_summary")


async def search_expenses(
    client: ExpenseTrackerClient,
    context: UserContext,
    arguments: ExpenseSearchArguments,
) -> ExpenseSearchResult:
    params = _filter_params(arguments)
    params.update(
        {
            "page": arguments.page,
            "size": arguments.size,
            "sortBy": arguments.sort_by.value,
            "sortDir": arguments.sort_dir.value,
        }
    )

    payload = await client.get_json(
        _EXPENSES_PATH,
        token=context.token,
        params=params,
        correlation_id=context.correlation_id,
    )
    page = parse_upstream(payload, _ExpensePage, tool="search_expenses")

    return ExpenseSearchResult(
        items=page.content,
        page=page.page,
        size=page.size,
        total_elements=page.total_elements,
        total_pages=page.total_pages,
        has_more=not page.last,
    )


def _filter_params(arguments: SpendingSummaryArguments) -> dict[str, str | int | float]:
    return compact_params(
        {
            "startDate": arguments.start_date.isoformat() if arguments.start_date else None,
            "endDate": arguments.end_date.isoformat() if arguments.end_date else None,
            "categoryId": arguments.category_id,
            "minAmount": decimal_param(arguments.min_amount),
            "maxAmount": decimal_param(arguments.max_amount),
            "search": arguments.search,
        }
    )
