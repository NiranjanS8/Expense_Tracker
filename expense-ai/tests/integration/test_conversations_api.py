from __future__ import annotations

from app.integrations.model_provider import ChatResponse, FinishReason
from tests.conftest import Harness, parse_sse

_CHAT_PATH = "/api/v1/chat"
_CONVERSATIONS_PATH = "/api/v1/conversations"
_AUTH = {"Authorization": "Bearer valid-token"}


def _answer(text: str) -> ChatResponse:
    return ChatResponse(provider="fake", model="fake-1", content=text, finish_reason=FinishReason.STOP)


def _create_conversation(harness: Harness) -> str:
    harness.script_model(_answer("Hello, I can help."))
    response = harness.client.post(_CHAT_PATH, json={"message": "Hello"}, headers=_AUTH)
    return str(dict(parse_sse(response.text))["message_complete"]["conversationId"])


def test_missing_conversation_is_reported_as_not_found(harness: Harness) -> None:
    harness.authenticate()

    response = harness.client.get(f"{_CONVERSATIONS_PATH}/does-not-exist", headers=_AUTH)

    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_deleting_a_missing_conversation_is_not_found(harness: Harness) -> None:
    harness.authenticate()

    response = harness.client.delete(f"{_CONVERSATIONS_PATH}/does-not-exist", headers=_AUTH)

    assert response.status_code == 404


def test_owner_can_delete_their_conversation(harness: Harness) -> None:
    harness.authenticate()
    conversation_id = _create_conversation(harness)

    deleted = harness.client.delete(f"{_CONVERSATIONS_PATH}/{conversation_id}", headers=_AUTH)

    assert deleted.status_code == 204
    assert harness.client.get(f"{_CONVERSATIONS_PATH}/{conversation_id}", headers=_AUTH).status_code == 404
    assert harness.client.get(_CONVERSATIONS_PATH, headers=_AUTH).json() == []


def test_conversation_detail_exposes_camel_case_fields(harness: Harness) -> None:
    harness.authenticate()
    conversation_id = _create_conversation(harness)

    detail = harness.client.get(f"{_CONVERSATIONS_PATH}/{conversation_id}", headers=_AUTH).json()

    assert set(detail) == {"id", "title", "status", "createdAt", "updatedAt", "messages"}
    assert set(detail["messages"][0]) == {"id", "role", "content", "createdAt"}
