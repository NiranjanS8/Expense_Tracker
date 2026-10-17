"""Integration tests for the metrics scrape endpoint and its wiring."""

from __future__ import annotations

import httpx

from app.core.config import Settings
from app.integrations.model_provider import ChatResponse, FinishReason, ToolCall
from app.observability.metrics import metrics
from tests.conftest import CURRENT_USER_PATH, Harness, parse_sse

_CHAT_PATH = "/api/v1/chat"
_SUMMARY_PATH = "/api/expenses/summary"
_AUTH = {"Authorization": "Bearer valid-token"}


def _identity_response() -> httpx.Response:
    return httpx.Response(
        200,
        json={"id": 1, "fullName": "Demo User", "email": "demo@expensetracker.com", "role": "USER"},
    )


def _summary_response() -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "totalAmount": "120.00",
            "transactionCount": 4,
            "startDate": "2026-10-01",
            "endDate": "2026-10-31",
        },
    )


def _answer(text: str) -> ChatResponse:
    return ChatResponse(provider="fake", model="fake-1", content=text, finish_reason=FinishReason.STOP)


def _identity_responder(request: httpx.Request) -> httpx.Response:
    return _identity_response()


def _spending_summary_call() -> ChatResponse:
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


def test_metrics_endpoint_is_closed_by_default(harness: Harness) -> None:
    response = harness.client.get("/metrics")

    assert response.status_code == 404


def test_metrics_endpoint_renders_prometheus_text_when_enabled(settings: Settings) -> None:
    enabled = settings.model_copy(update={"metrics_enabled": True})
    with Harness(enabled) as harness:
        harness.respond_from(_identity_responder)
        harness.script_model(_answer("Hello."))
        harness.client.post(_CHAT_PATH, json={"message": "Hello"}, headers=_AUTH)

        response = harness.client.get("/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    body = response.text
    # Bounded labels: the endpoint name, never a concrete conversation id.
    assert 'expense_ai_http_requests_total{method="POST",route="submit_message",status="200"} 1' in body
    assert 'expense_ai_chat_turns_total{outcome="answered"} 1' in body
    assert "# TYPE expense_ai_http_request_duration_seconds histogram" in body


def test_a_completed_turn_records_tool_and_model_metrics(harness: Harness) -> None:
    def responder(request: httpx.Request) -> httpx.Response:
        if request.url.path == CURRENT_USER_PATH:
            return _identity_response()
        if request.url.path == _SUMMARY_PATH:
            return _summary_response()
        return httpx.Response(404)

    harness.respond_from(responder)
    harness.script_model(_spending_summary_call(), _answer("You spent 120.00."))

    harness.client.post(_CHAT_PATH, json={"message": "How much did I spend this month?"}, headers=_AUTH)

    assert (
        metrics.counter_value(
            "expense_ai_tool_calls_total", {"tool": "get_spending_summary", "outcome": "ok"}
        )
        == 1
    )
    assert (
        metrics.histogram_count("expense_ai_tool_call_duration_seconds", {"tool": "get_spending_summary"})
        == 1
    )
    # The fake provider reports no tokens, so only the calls are counted. The plan
    # node runs twice: once to request the tool, once to compose from its result.
    assert (
        metrics.counter_value(
            "expense_ai_model_calls_total", {"provider": "fake", "node": "plan", "outcome": "ok"}
        )
        == 2
    )


def test_sse_chat_still_completes_with_metrics_recording(harness: Harness) -> None:
    harness.respond_from(_identity_responder)
    harness.script_model(_answer("Hello."))

    response = harness.client.post(_CHAT_PATH, json={"message": "Hello"}, headers=_AUTH)

    assert response.status_code == 200
    assert parse_sse(response.text)[-1][0] == "message_complete"


def test_authentication_denials_are_counted(harness: Harness) -> None:
    response = harness.client.post(_CHAT_PATH, json={"message": "Hello"})

    assert response.status_code == 401
    assert metrics.counter_value("expense_ai_auth_denials_total", {"reason": "unauthenticated"}) == 1


def test_rate_limit_rejections_are_counted() -> None:
    limited = Settings(
        _env_file=None,
        llm_provider="fake",
        expense_tracker_base_url="http://spring.test",
        identity_cache_ttl_seconds=0,
        database_url="sqlite+aiosqlite:///:memory:",
        auto_create_schema=True,
        chat_rate_limit_per_minute=1,
    )
    with Harness(limited) as harness:
        harness.respond_from(_identity_responder)
        harness.script_model(_answer("Hello."), _answer("Hello again."))

        harness.client.post(_CHAT_PATH, json={"message": "Hello"}, headers=_AUTH)
        rejected = harness.client.post(_CHAT_PATH, json={"message": "Hello again"}, headers=_AUTH)

    assert rejected.status_code == 429
    assert metrics.counter_value("expense_ai_rate_limit_rejections_total", {"scope": "http"}) == 1
