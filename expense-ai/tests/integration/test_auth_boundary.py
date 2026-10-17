from __future__ import annotations

import httpx

from tests.conftest import CURRENT_USER_PATH, Harness, parse_sse

_CHAT_PATH = "/api/v1/chat"


def test_chat_requires_an_authorization_header(harness: Harness) -> None:
    response = harness.client.post(_CHAT_PATH, json={"message": "hello"})

    assert response.status_code == 401
    assert response.json()["code"] == "unauthenticated"


def test_malformed_authorization_scheme_is_rejected(harness: Harness) -> None:
    response = harness.client.post(
        _CHAT_PATH,
        json={"message": "hello"},
        headers={"Authorization": "Basic abc"},
    )

    assert response.status_code == 401


def test_chat_rejects_an_upstream_invalid_token(harness: Harness) -> None:
    harness.responder = lambda _request: httpx.Response(403)

    response = harness.client.post(
        _CHAT_PATH,
        json={"message": "hello"},
        headers={"Authorization": "Bearer expired-token"},
    )

    assert response.status_code == 401
    assert response.json()["code"] == "unauthenticated"


def test_chat_passes_authentication_then_streams_events(harness: Harness) -> None:
    harness.authenticate(user_id=42)

    response = harness.client.post(
        _CHAT_PATH,
        json={"message": "What can you do?"},
        headers={"Authorization": "Bearer valid-token"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    event_names = [name for name, _ in parse_sse(response.text)]
    assert event_names[0] == "message_start"
    assert event_names[-1] == "message_complete"
    assert len(harness.requests_to(CURRENT_USER_PATH)) == 1


def test_chat_never_fabricates_an_answer_to_a_data_question_without_tools(harness: Harness) -> None:
    harness.authenticate()

    # The default fake provider returns prose without calling any tool, so the
    # graph must refuse rather than present the prose as a financial figure.
    response = harness.client.post(
        _CHAT_PATH,
        json={"message": "How much did I spend this month?"},
        headers={"Authorization": "Bearer valid-token"},
    )

    events = dict(parse_sse(response.text))
    assert events["message_complete"]["content"] != "[fake] How much did I spend this month?"
    assert events["message_complete"]["toolCalls"] == []


def test_conversation_routes_require_authentication(harness: Harness) -> None:
    assert harness.client.get("/api/v1/conversations").status_code == 401
    assert harness.client.get("/api/v1/conversations/abc").status_code == 401
    assert harness.client.delete("/api/v1/conversations/abc").status_code == 401


def test_conversation_list_is_empty_for_a_new_user(harness: Harness) -> None:
    harness.authenticate()

    response = harness.client.get(
        "/api/v1/conversations",
        headers={"Authorization": "Bearer valid-token"},
    )

    assert response.status_code == 200
    assert response.json() == []


def test_invalid_chat_body_is_rejected_before_authentication_logic(harness: Harness) -> None:
    harness.authenticate()

    response = harness.client.post(
        _CHAT_PATH,
        json={"message": ""},
        headers={"Authorization": "Bearer valid-token"},
    )

    assert response.status_code == 400
    assert response.json()["code"] == "invalid_request"


def test_oversized_request_body_is_rejected(harness: Harness) -> None:
    harness.authenticate()

    response = harness.client.post(
        _CHAT_PATH,
        content=b"x" * (harness.settings.max_request_bytes + 1),
        headers={"Authorization": "Bearer valid-token", "Content-Type": "application/json"},
    )

    assert response.status_code == 413
    assert response.json()["code"] == "payload_too_large"


def test_correlation_id_is_generated_and_echoed(harness: Harness) -> None:
    response = harness.client.get("/health/live")

    assert response.headers["X-Correlation-Id"]


def test_inbound_correlation_id_is_echoed_and_forwarded(harness: Harness) -> None:
    harness.authenticate()

    response = harness.client.post(
        _CHAT_PATH,
        json={"message": "hello"},
        headers={"Authorization": "Bearer valid-token", "X-Correlation-Id": "corr-abc"},
    )

    assert response.headers["X-Correlation-Id"] == "corr-abc"
    upstream = harness.requests_to(CURRENT_USER_PATH)[0]
    assert upstream.headers["x-correlation-id"] == "corr-abc"


def test_chat_is_rate_limited_per_user(harness: Harness) -> None:
    harness.authenticate(user_id=99)

    for _ in range(harness.settings.chat_rate_limit_per_minute):
        response = harness.client.post(
            _CHAT_PATH,
            json={"message": "hello"},
            headers={"Authorization": "Bearer valid-token"},
        )
        assert response.status_code == 200

    limited = harness.client.post(
        _CHAT_PATH,
        json={"message": "hello"},
        headers={"Authorization": "Bearer valid-token"},
    )

    assert limited.status_code == 429
    assert limited.json()["code"] == "rate_limited"
    assert "Retry-After" in limited.headers
