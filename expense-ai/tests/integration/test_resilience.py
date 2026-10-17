"""Integration tests for resilience: failures degrade safely and stay bounded."""

from __future__ import annotations

import httpx

from app.core.config import Settings
from app.integrations.model_provider import (
    ChatRequest,
    ChatResponse,
    FinishReason,
    ModelProvider,
    ProviderRateLimitedError,
    ProviderTimeoutError,
    ToolCall,
)
from app.observability.metrics import metrics
from tests.conftest import CURRENT_USER_PATH, Harness, parse_sse

_CHAT_PATH = "/api/v1/chat"
_SUMMARY_PATH = "/api/expenses/summary"
_AUTH = {"Authorization": "Bearer token-1"}


def _identity_response() -> httpx.Response:
    return httpx.Response(
        200, json={"id": 1, "fullName": "Demo", "email": "demo@expensetracker.com", "role": "USER"}
    )


def _summary_call() -> ChatResponse:
    return ChatResponse(
        provider="fake",
        model="fake-1",
        tool_calls=[
            ToolCall(
                id="call-1",
                name="get_spending_summary",
                arguments={"start_date": "2026-10-01", "end_date": "2026-10-31"},
            )
        ],
        finish_reason=FinishReason.TOOL_CALLS,
    )


def _answer(text: str) -> ChatResponse:
    return ChatResponse(provider="fake", model="fake-1", content=text, finish_reason=FinishReason.STOP)


def _complete(body: str) -> dict[str, object]:
    return dict(parse_sse(body))["message_complete"]


def _post(harness: Harness, message: str) -> str:
    return harness.client.post(_CHAT_PATH, json={"message": message}, headers=_AUTH).text


def _raising_provider(error: Exception) -> ModelProvider:
    class _Provider(ModelProvider):
        name = "raising"

        async def complete(self, request: ChatRequest) -> ChatResponse:
            raise error

    return _Provider()


def test_upstream_timeout_is_reported_without_inventing_a_total(harness: Harness) -> None:
    def responder(request: httpx.Request) -> httpx.Response:
        if request.url.path == CURRENT_USER_PATH:
            return _identity_response()
        raise httpx.TimeoutException("upstream timed out")

    harness.respond_from(responder)
    harness.script_model(_summary_call(), _answer("never"))

    complete = _complete(_post(harness, "How much did I spend this month?"))

    assert complete["termination"] == "tool_error"
    assert "won't guess" in str(complete["content"])


def test_upstream_transport_error_is_reported_safely(harness: Harness) -> None:
    def responder(request: httpx.Request) -> httpx.Response:
        if request.url.path == CURRENT_USER_PATH:
            return _identity_response()
        raise httpx.ConnectError("connection refused")

    harness.respond_from(responder)
    harness.script_model(_summary_call(), _answer("never"))

    complete = _complete(_post(harness, "How much did I spend this month?"))

    assert complete["termination"] == "tool_error"
    assert complete["toolCalls"] == ["get_spending_summary"]


def test_provider_timeout_never_produces_fabricated_figures(harness: Harness) -> None:
    harness.respond_from(lambda request: _identity_response())
    harness.use_model(_raising_provider(ProviderTimeoutError("timed out")))

    complete = _complete(_post(harness, "How much did I spend this month?"))

    assert complete["toolCalls"] == []
    assert "temporarily unavailable" in str(complete["content"])


def test_provider_rate_limit_degrades_to_a_safe_answer(harness: Harness) -> None:
    harness.respond_from(lambda request: _identity_response())
    harness.use_model(_raising_provider(ProviderRateLimitedError("slow down")))

    complete = _complete(_post(harness, "How much did I spend this month?"))

    assert complete["termination"] == "model_error"
    assert harness.requests_to(_SUMMARY_PATH) == []


def test_client_disconnect_still_records_exactly_one_turn(harness: Harness) -> None:
    harness.respond_from(lambda request: _identity_response())
    harness.script_model(_answer("Hello."))

    with harness.client.stream("POST", _CHAT_PATH, json={"message": "Hello"}, headers=_AUTH) as response:
        assert response.status_code == 200
        for _ in response.iter_text():
            break

    assert metrics.histogram_count("expense_ai_chat_turn_duration_seconds") == 1


def test_exhausted_step_budget_is_reported_safely(settings: Settings) -> None:
    bounded = settings.model_copy(update={"agent_recursion_limit": 1})
    with Harness(bounded) as harness:
        harness.respond_from(lambda request: _identity_response())
        harness.script_model(_answer("never"))

        events = dict(parse_sse(_post(harness, "How much did I spend this month?")))

    assert "error" in events
    assert events["error"]["code"] == "iteration_limit"
