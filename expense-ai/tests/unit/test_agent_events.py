from __future__ import annotations

from app.agent.events import (
    ERROR,
    MESSAGE_COMPLETE,
    MESSAGE_START,
    TOKEN,
    error,
    message_complete,
    message_start,
    status,
    token,
)
from app.api.v1.streaming import encode_sse


def test_message_start_carries_the_conversation_id() -> None:
    event = message_start(conversation_id="conv-1")

    assert event.event == MESSAGE_START
    assert event.data == {"conversationId": "conv-1"}


def test_status_can_name_the_tool_in_flight() -> None:
    assert status(stage="planning").data == {"stage": "planning"}
    assert status(stage="retrieving", tool="get_spending_summary").data == {
        "stage": "retrieving",
        "tool": "get_spending_summary",
    }


def test_message_complete_exposes_stable_identifiers() -> None:
    event = message_complete(
        conversation_id="conv-1",
        message_id=7,
        content="You spent 120.00.",
        termination="answered",
        tool_calls=["get_spending_summary"],
    )

    assert event.event == MESSAGE_COMPLETE
    assert event.data["conversationId"] == "conv-1"
    assert event.data["messageId"] == 7
    assert event.data["toolCalls"] == ["get_spending_summary"]


def test_error_payload_has_no_internal_detail() -> None:
    event = error(code="upstream_unavailable", message="Try later.", correlation_id="corr-1")

    assert event.event == ERROR
    assert set(event.data) == {"code", "message", "correlationId"}


def test_events_encode_as_server_sent_events() -> None:
    encoded = encode_sse(token(text="hello"))

    assert encoded == f'event: {TOKEN}\ndata: {{"text":"hello"}}\n\n'
