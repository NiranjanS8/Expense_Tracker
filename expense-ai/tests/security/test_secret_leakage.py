"""Security tests: secrets and financial filters stay out of logs and responses."""

from __future__ import annotations

import logging

import httpx
import pytest

from app.integrations.model_provider import ChatResponse, FinishReason, ToolCall
from app.observability.metrics import metrics
from tests.conftest import CURRENT_USER_PATH, Harness, parse_sse

_CHAT_PATH = "/api/v1/chat"
_SUMMARY_PATH = "/api/expenses/summary"
_TOKEN = "super-secret-token"
_FILTER = "therapist-copay"
_AUTH = {"Authorization": f"Bearer {_TOKEN}"}


def _identity_response() -> httpx.Response:
    return httpx.Response(
        200, json={"id": 1, "fullName": "Demo", "email": "demo@expensetracker.com", "role": "USER"}
    )


def _responder(request: httpx.Request) -> httpx.Response:
    if request.url.path == CURRENT_USER_PATH:
        return _identity_response()
    if request.url.path == _SUMMARY_PATH:
        return httpx.Response(
            200,
            json={
                "totalAmount": "10.00",
                "transactionCount": 1,
                "startDate": "2026-10-01",
                "endDate": "2026-10-31",
            },
        )
    return httpx.Response(404)


def _search_call() -> ChatResponse:
    return ChatResponse(
        provider="fake",
        model="fake-1",
        tool_calls=[
            ToolCall(
                id="call-1",
                name="get_spending_summary",
                arguments={
                    "start_date": "2026-10-01",
                    "end_date": "2026-10-31",
                    "search": _FILTER,
                },
            )
        ],
        finish_reason=FinishReason.TOOL_CALLS,
    )


def _answer(text: str) -> ChatResponse:
    return ChatResponse(provider="fake", model="fake-1", content=text, finish_reason=FinishReason.STOP)


def test_tokens_and_filters_never_appear_in_logs(harness: Harness, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO)
    harness.respond_from(_responder)
    harness.script_model(_search_call(), _answer("You spent 10.00."))

    harness.client.post(_CHAT_PATH, json={"message": "How much did I spend this month?"}, headers=_AUTH)

    assert _TOKEN not in caplog.text
    assert _FILTER not in caplog.text


def test_the_stream_and_metrics_never_carry_the_token(harness: Harness) -> None:
    harness.respond_from(_responder)
    harness.script_model(_answer("Hello."))

    response = harness.client.post(_CHAT_PATH, json={"message": "Hello"}, headers=_AUTH)

    assert response.status_code == 200
    assert _TOKEN not in response.text
    assert _TOKEN not in metrics.render()


def test_error_responses_expose_no_internal_detail(harness: Harness) -> None:
    def responder(request: httpx.Request) -> httpx.Response:
        if request.url.path == CURRENT_USER_PATH:
            return _identity_response()
        return httpx.Response(503)

    harness.respond_from(responder)
    harness.script_model(_search_call(), _answer("never"))

    response = harness.client.post(
        _CHAT_PATH, json={"message": "How much did I spend this month?"}, headers=_AUTH
    )

    # The failure degrades to a safe event; nothing carries the token, the filter
    # or a stack trace back to the client.
    for _, data in parse_sse(response.text):
        rendered = str(data)
        assert _TOKEN not in rendered
        assert _FILTER not in rendered
        assert "Traceback" not in rendered
