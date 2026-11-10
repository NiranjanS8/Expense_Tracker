"""Write parsing is deterministic: every value comes from the caller's words."""

from __future__ import annotations

from datetime import date

import pytest

from app.agent.writes import (
    CategoryOption,
    RecurringRule,
    category_intent,
    extract_category_name,
    extract_recurring_status,
    extract_write,
    is_category_creation,
    match_recurring_rule,
    recurring_intent,
)
from app.approvals.service import CREATE_CATEGORY, CREATE_EXPENSE, SET_BUDGET, SET_RECURRING_STATUS

_TODAY = date(2026, 11, 9)
_CATEGORIES = (
    CategoryOption(id=1, name="Food"),
    CategoryOption(id=2, name="Coffee & Snacks"),
    CategoryOption(id=3, name="Transport"),
)
_GYM = RecurringRule(
    id=11,
    description="Gym membership",
    amount=1500.0,
    frequency="MONTHLY",
    active=True,
    next_execution_date="2026-12-01",
    category_name="Health",
)
_RENT = RecurringRule(
    id=12,
    description="Rent",
    amount=20000.0,
    frequency="MONTHLY",
    active=True,
    next_execution_date="2026-12-01",
    category_name="Housing",
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


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("Pause my gym subscription", False),
        ("Stop the Netflix autopay", False),
        ("Turn off my rent subscription", False),
        ("Pause my gym membership", False),
        ("Resume my gym subscription", True),
        ("Reactivate my rent subscription", True),
        ("Turn on my rent subscription", True),
        ("What subscriptions do I have?", None),
        ("Add a 20 gym subscription expense", None),
        ("Stop spending so much", None),
        ("Pause my budget", None),
    ],
)
def test_a_recurring_status_request_is_read_from_its_own_words(message: str, expected: bool | None) -> None:
    assert extract_recurring_status(message) == expected


def test_the_named_rule_matches_on_its_description() -> None:
    rule = match_recurring_rule("Pause my gym membership subscription", (_GYM, _RENT))

    assert rule is not None
    assert rule.id == 11


def test_two_rules_with_the_same_name_are_ambiguous() -> None:
    duplicate = RecurringRule(
        id=13,
        description="Gym membership",
        amount=900.0,
        frequency="MONTHLY",
        active=True,
        next_execution_date=None,
        category_name="Health",
    )

    assert match_recurring_rule("Pause my gym membership", (duplicate, _GYM)) is None


def test_the_only_rule_is_used_when_the_caller_does_not_name_it() -> None:
    rule = match_recurring_rule("Pause my subscription", (_GYM,))

    assert rule is not None
    assert rule.id == 11


def test_several_unnamed_rules_are_never_guessed_between() -> None:
    assert match_recurring_rule("Pause my subscription", (_GYM, _RENT)) is None


def test_a_pause_intent_shows_the_state_change_and_keeps_generated_expenses() -> None:
    intent = recurring_intent(_GYM, active=False)

    assert intent.action == SET_RECURRING_STATUS
    assert intent.resource_id == "11"
    assert intent.arguments == {"active": False}
    details = {detail["label"]: detail["value"] for detail in intent.details}
    assert details["Change"] == "Active -> Paused"
    assert "No future expenses will be generated from this rule." in intent.consequences


def test_a_resume_intent_does_not_promise_backfill() -> None:
    intent = recurring_intent(_GYM, active=True)

    assert intent.arguments == {"active": True}
    assert "Future occurrences will be generated again from the next scheduled date." in intent.consequences


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("Create a category called Lunch", "Lunch"),
        ("Create a new category called Coffee & Snacks", "Coffee & Snacks"),
        ("Add a category Food", "Food"),
        ("Please create a category for Groceries", "Groceries"),
        ("Create a category, Pet Care", "Pet Care"),
        ("Create a new category", None),
    ],
)
def test_a_category_name_is_taken_literally(message: str, expected: str | None) -> None:
    assert extract_category_name(message) == expected


@pytest.mark.parametrize(
    "message",
    [
        "Create a category called Lunch",
        "Add a new category for groceries",
        "Make a category named Travel",
    ],
)
def test_a_category_request_is_recognised(message: str) -> None:
    assert is_category_creation(message)


@pytest.mark.parametrize(
    "message",
    [
        "Add a 20 lunch expense in the Food category",
        "Add a 20 lunch under the Food category",
        "Set my budget to 500 in the Food category",
        "What categories do I have?",
    ],
)
def test_an_expense_or_question_is_not_mistaken_for_a_category_request(message: str) -> None:
    assert not is_category_creation(message)


def test_a_category_intent_carries_only_its_literal_name() -> None:
    intent = category_intent("Coffee & Snacks")

    assert intent.action == CREATE_CATEGORY
    assert intent.resource_id is None
    assert intent.arguments == {"name": "Coffee & Snacks"}
