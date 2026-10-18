from __future__ import annotations

import pytest

from app.agent.policies import (
    DATA_INTENT,
    DRAFT_INTENT,
    GENERAL_INTENT,
    classify_intent,
    conversation_title,
)


@pytest.mark.parametrize(
    "message",
    [
        "How much did I spend this month?",
        "Show my largest expenses",
        "How is my food budget doing?",
        "What are my savings goals?",
        "What recurring subscriptions do I have?",
        "Compare this month with last month",
        "How many transactions do I have?",
        "Where does my money go?",
    ],
)
def test_financial_questions_are_routed_to_the_data_path(message: str) -> None:
    assert classify_intent(message) == DATA_INTENT


@pytest.mark.parametrize(
    "message",
    [
        "Hello",
        "What can you do?",
        "Who built this app?",
        "Thanks!",
    ],
)
def test_non_financial_messages_take_the_general_path(message: str) -> None:
    assert classify_intent(message) == GENERAL_INTENT


@pytest.mark.parametrize(
    "message",
    [
        "Add a 12.50 coffee expense yesterday",
        "Record my 1200 rent payment",
        "Set my budget for this month to 20000",
        "Record a 40 lunch expense yesterday",
    ],
)
def test_requests_to_record_something_take_the_draft_path(message: str) -> None:
    assert classify_intent(message) == DRAFT_INTENT


@pytest.mark.parametrize(
    "message",
    [
        "Add up my expenses this month",
        "What should I set my budget to?",
        "How much did I spend this month?",
        "Can you make changes to my account for me?",
    ],
)
def test_lookalike_phrases_never_take_the_draft_path(message: str) -> None:
    assert classify_intent(message) != DRAFT_INTENT


def test_titles_are_collapsed_and_bounded() -> None:
    assert conversation_title("  How   much did I spend?  ", max_length=80) == "How much did I spend?"
    assert conversation_title("x" * 20, max_length=10) == "x" * 9 + "\u2026"
    assert conversation_title("   ", max_length=10) == "New conversation"
