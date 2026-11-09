"""Write parsing is deterministic: every value comes from the caller's words."""

from __future__ import annotations

from datetime import date

import pytest

from app.agent.writes import CategoryOption, extract_write
from app.approvals.service import CREATE_EXPENSE, SET_BUDGET

_TODAY = date(2026, 11, 9)
_CATEGORIES = (
    CategoryOption(id=1, name="Food"),
    CategoryOption(id=2, name="Coffee & Snacks"),
    CategoryOption(id=3, name="Transport"),
)


def test_an_expense_request_is_parsed_from_the_message() -> None:
    intent = extract_write("Add a 12.50 coffee expense yesterday by card", today=_TODAY)

    assert intent is not None
    assert intent.action == CREATE_EXPENSE
    assert intent.resource_id is None
    assert intent.arguments == {
        "amount": "12.50",
        "expenseDate": "2026-11-08",
        "description": "coffee",
        "categoryId": None,
        "paymentMethod": "CARD",
    }


def test_an_unspecified_payment_method_is_visible_in_the_details() -> None:
    intent = extract_write("Add a 5 coffee expense", today=_TODAY)

    assert intent is not None
    assert intent.arguments["paymentMethod"] == "OTHER"
    details = {detail["label"]: detail["value"] for detail in intent.details}
    assert details["Payment method"] == "Other (not specified)"


def test_a_named_category_is_matched_only_when_the_user_said_it() -> None:
    intent = extract_write("add a 20 food expense", today=_TODAY, categories=_CATEGORIES)
    assert intent is not None
    assert intent.arguments["categoryId"] == 1


def test_a_multi_word_category_must_be_named_in_full() -> None:
    intent = extract_write("add a 20 coffee and snacks expense", today=_TODAY, categories=_CATEGORIES)
    assert intent is not None
    assert intent.arguments["categoryId"] == 2


def test_an_unsaid_category_is_left_to_the_backend_rules() -> None:
    intent = extract_write("add a 20 lunch expense", today=_TODAY, categories=_CATEGORIES)
    assert intent is not None
    assert intent.arguments["categoryId"] is None


def test_a_budget_request_carries_its_month_and_amount() -> None:
    intent = extract_write("Set my budget for next month to 5,000", today=_TODAY)

    assert intent is not None
    assert intent.action == SET_BUDGET
    assert intent.resource_id == "2026-12"
    assert intent.arguments == {"amount": "5000.00", "budgetMonth": "2026-12"}


@pytest.mark.parametrize("message", ["add a coffee expense", "add a 0 expense"])
def test_a_request_without_a_positive_amount_yields_no_write(message: str) -> None:
    assert extract_write(message, today=_TODAY) is None
