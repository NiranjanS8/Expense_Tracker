"""Draft extraction is deterministic: every value comes from the caller's words."""

from __future__ import annotations

from datetime import date

import pytest

from app.agent.drafts import BUDGET_DRAFT, EXPENSE_DRAFT, extract_draft

_TODAY = date(2026, 10, 18)


def test_an_expense_request_becomes_a_form_prefill() -> None:
    proposal = extract_draft("Add a 12.50 coffee expense yesterday", today=_TODAY)

    assert proposal is not None
    assert proposal.kind == EXPENSE_DRAFT
    assert proposal.fields == {
        "amount": 12.5,
        "expenseDate": "2026-10-17",
        "description": "coffee",
        "categoryHint": "coffee",
    }
    assert "Nothing has been saved" in proposal.message


def test_a_budget_request_becomes_a_month_prefill() -> None:
    proposal = extract_draft("Set my budget for next month to 5,000", today=_TODAY)

    assert proposal is not None
    assert proposal.kind == BUDGET_DRAFT
    assert proposal.fields == {"amount": 5000.0, "budgetMonth": "2026-11"}


def test_an_expense_without_a_date_defaults_to_today() -> None:
    proposal = extract_draft("add 250 for electricity bill", today=_TODAY)

    assert proposal is not None
    assert proposal.fields["expenseDate"] == "2026-10-18"
    assert proposal.fields["description"] == "electricity"


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("add 12.50 for coffee on 2026-09-03", "2026-09-03"),
        ("record coffee on 17/10 for 12.50", "2026-10-17"),
        ("log a 40 lunch tomorrow", "2026-10-19"),
    ],
)
def test_the_stated_date_is_read_off_the_message(message: str, expected: str) -> None:
    proposal = extract_draft(message, today=_TODAY)

    assert proposal is not None
    assert proposal.fields["expenseDate"] == expected


def test_a_date_is_never_mistaken_for_the_amount() -> None:
    # "17/10" is a date, so the single amount is 12.50.
    proposal = extract_draft("record coffee on 17/10 for 12.50", today=_TODAY)

    assert proposal is not None
    assert proposal.fields["amount"] == 12.5
    assert "17" not in str(proposal.fields["amount"])


def test_a_request_without_an_amount_yields_no_draft() -> None:
    assert extract_draft("add a coffee expense", today=_TODAY) is None


def test_a_zero_amount_yields_no_draft() -> None:
    assert extract_draft("add a 0 coffee expense", today=_TODAY) is None


def test_the_description_never_invents_wording() -> None:
    proposal = extract_draft("add 12.50", today=_TODAY)

    assert proposal is not None
    assert proposal.fields["description"] == "Expense"


def test_the_summary_states_the_proposed_values() -> None:
    proposal = extract_draft("add a 12.50 coffee expense yesterday", today=_TODAY)

    assert proposal is not None
    assert proposal.summary == "Expense of 12.50 for coffee on 2026-10-17"
