"""Contract tests for the tool argument models.

These are the tests that hold the authorization line: a tool argument model that
started accepting an identity field, or stopped rejecting unknown ones, would let
model output choose whose data is fetched.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import BaseModel, ValidationError

from app.tools.budgets import BudgetStatusArguments
from app.tools.common import MAX_DATE_RANGE_DAYS, MAX_PAGE_INDEX, MAX_PAGE_SIZE, MAX_SEARCH_LENGTH
from app.tools.dashboard import CategoryBreakdownArguments, DashboardSummaryArguments
from app.tools.expenses import ExpenseSearchArguments, SpendingSummaryArguments
from app.tools.goals import GoalProgressArguments
from app.tools.insights import ExistingInsightsArguments
from app.tools.recurring import RecurringExpenseArguments

ARGUMENT_MODELS: tuple[type[BaseModel], ...] = (
    SpendingSummaryArguments,
    ExpenseSearchArguments,
    CategoryBreakdownArguments,
    DashboardSummaryArguments,
    BudgetStatusArguments,
    GoalProgressArguments,
    RecurringExpenseArguments,
    ExistingInsightsArguments,
)

IDENTITY_ARGUMENTS: tuple[dict[str, object], ...] = (
    {"user_id": 2},
    {"userId": 2},
    {"userId": "2"},
    {"email": "somebody.else@example.com"},
)


@pytest.mark.parametrize("model", ARGUMENT_MODELS)
@pytest.mark.parametrize("arguments", IDENTITY_ARGUMENTS)
def test_identity_arguments_are_rejected(model: type[BaseModel], arguments: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        model.model_validate(arguments)


@pytest.mark.parametrize("model", ARGUMENT_MODELS)
def test_unknown_arguments_are_rejected(model: type[BaseModel]) -> None:
    with pytest.raises(ValidationError):
        model.model_validate({"definitely_not_an_argument": 1})


@pytest.mark.parametrize("model", ARGUMENT_MODELS)
def test_schemas_forbid_additional_properties(model: type[BaseModel]) -> None:
    schema = model.model_json_schema()

    assert schema["additionalProperties"] is False
    assert not {"userId", "user_id", "email", "role"} & set(schema["properties"])


@pytest.mark.parametrize("model", ARGUMENT_MODELS)
def test_validated_arguments_are_immutable(model: type[BaseModel]) -> None:
    arguments = model.model_validate({})

    with pytest.raises(ValidationError):
        # Explicit ``__setattr__`` rather than assignment: mypy rejects an unknown
        # attribute statically, but the property under test is the runtime frozen check.
        arguments.__setattr__("definitely_not_an_argument", 1)


def test_inverted_date_range_is_rejected() -> None:
    with pytest.raises(ValidationError, match="start_date must not be after end_date"):
        SpendingSummaryArguments(start_date=date(2026, 3, 2), end_date=date(2026, 3, 1))


def test_over_long_date_range_is_rejected() -> None:
    start = date(2024, 1, 1)

    with pytest.raises(ValidationError, match="date range must not exceed"):
        SpendingSummaryArguments(start_date=start, end_date=start.replace(year=2027))


def test_date_range_may_span_exactly_the_allowed_window() -> None:
    start = date(2026, 1, 1)
    end = date.fromordinal(start.toordinal() + MAX_DATE_RANGE_DAYS)

    arguments = SpendingSummaryArguments(start_date=start, end_date=end)

    assert arguments.end_date == end


def test_open_ended_date_ranges_are_accepted() -> None:
    assert SpendingSummaryArguments(start_date=date(2026, 1, 1)).end_date is None
    assert SpendingSummaryArguments(end_date=date(2026, 1, 1)).start_date is None
    assert SpendingSummaryArguments().start_date is None


def test_inverted_amount_range_is_rejected() -> None:
    with pytest.raises(ValidationError, match="min_amount must not be greater than max_amount"):
        SpendingSummaryArguments(min_amount=Decimal("10"), max_amount=Decimal("9"))


def test_equal_amount_bounds_are_accepted() -> None:
    arguments = SpendingSummaryArguments(min_amount=Decimal("10.00"), max_amount=Decimal("10"))

    assert arguments.min_amount == arguments.max_amount


def test_negative_amounts_are_rejected() -> None:
    with pytest.raises(ValidationError):
        SpendingSummaryArguments(min_amount=Decimal("-0.01"))


@pytest.mark.parametrize("size", [0, MAX_PAGE_SIZE + 1])
def test_page_size_outside_the_upstream_limit_is_rejected(size: int) -> None:
    with pytest.raises(ValidationError):
        ExpenseSearchArguments(size=size)


def test_page_size_at_the_upstream_limit_is_accepted() -> None:
    assert ExpenseSearchArguments(size=MAX_PAGE_SIZE).size == MAX_PAGE_SIZE


@pytest.mark.parametrize("page", [-1, MAX_PAGE_INDEX + 1])
def test_page_index_outside_the_allowed_bound_is_rejected(page: int) -> None:
    with pytest.raises(ValidationError):
        ExpenseSearchArguments(page=page)


def test_search_text_is_length_bounded() -> None:
    with pytest.raises(ValidationError):
        SpendingSummaryArguments(search="x" * (MAX_SEARCH_LENGTH + 1))

    assert SpendingSummaryArguments(search="x" * MAX_SEARCH_LENGTH).search is not None


@pytest.mark.parametrize(
    "month", ["2026-13", "2026-00", "2026-1", "202610", "1999-12", "2101-01", "not-a-month"]
)
def test_invalid_months_are_rejected(month: str) -> None:
    with pytest.raises(ValidationError):
        ExistingInsightsArguments(month=month)


@pytest.mark.parametrize("month", ["2000-01", "2026-10", "2100-12"])
def test_supported_months_are_accepted(month: str) -> None:
    assert CategoryBreakdownArguments(month=month).month == month


def test_omitting_a_month_is_allowed() -> None:
    assert CategoryBreakdownArguments().month is None


@pytest.mark.parametrize("year", [1999, 2101])
def test_years_outside_the_supported_range_are_rejected(year: int) -> None:
    with pytest.raises(ValidationError):
        BudgetStatusArguments(year=year)


@pytest.mark.parametrize("sort_by", ["description", "paymentMethod", "id"])
def test_unverified_sort_properties_are_rejected(sort_by: str) -> None:
    with pytest.raises(ValidationError):
        ExpenseSearchArguments.model_validate({"sort_by": sort_by})


def test_unverified_sort_direction_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ExpenseSearchArguments.model_validate({"sort_dir": "sideways"})


def test_recent_limit_follows_the_upstream_bound() -> None:
    with pytest.raises(ValidationError):
        DashboardSummaryArguments(recent_limit=21)

    assert DashboardSummaryArguments(recent_limit=20).recent_limit == 20


def test_goal_id_must_be_a_positive_identifier() -> None:
    with pytest.raises(ValidationError):
        GoalProgressArguments(goal_id=0)


def test_active_filter_is_optional() -> None:
    assert RecurringExpenseArguments().active is None
    assert RecurringExpenseArguments(active=False).active is False
