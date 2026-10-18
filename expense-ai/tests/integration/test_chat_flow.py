from __future__ import annotations

from typing import Any

import httpx

from app.core.config import Settings
from app.integrations.model_provider import (
    ChatRequest,
    ChatResponse,
    FinishReason,
    ModelProvider,
    ProviderUnavailableError,
    ToolCall,
)
from tests.conftest import CURRENT_USER_PATH, Harness, Responder, parse_sse

_CHAT_PATH = "/api/v1/chat"
_CONVERSATIONS_PATH = "/api/v1/conversations"
_SUMMARY_PATH = "/api/expenses/summary"
_AUTH = {"Authorization": "Bearer valid-token"}
_SUMMARY_BODY = {
    "totalAmount": "120.00",
    "transactionCount": 4,
    "startDate": "2026-10-01",
    "endDate": "2026-10-31",
}


def _upstream_responder(*, user_id: int = 1, summary_status: int = 200) -> Responder:
    def responder(request: httpx.Request) -> httpx.Response:
        if request.url.path == CURRENT_USER_PATH:
            return httpx.Response(
                200,
                json={
                    "id": user_id,
                    "fullName": "Demo User",
                    "email": "demo@expensetracker.com",
                    "role": "USER",
                },
            )
        if request.url.path == _SUMMARY_PATH:
            return httpx.Response(summary_status, json=_SUMMARY_BODY)
        return httpx.Response(404)

    return responder


def _tool_call(name: str, arguments: dict[str, object], *, call_id: str = "call-1") -> ChatResponse:
    return ChatResponse(
        provider="fake",
        model="fake-1",
        tool_calls=[ToolCall(id=call_id, name=name, arguments=arguments)],
        finish_reason=FinishReason.TOOL_CALLS,
    )


def _answer(text: str) -> ChatResponse:
    return ChatResponse(provider="fake", model="fake-1", content=text, finish_reason=FinishReason.STOP)


def _post(harness: Harness, message: str, *, conversation_id: str | None = None) -> Any:
    # The TestClient's response type comes from its own httpx, not this import; the
    # helpers below only read ``status_code`` and ``text``.
    body: dict[str, object] = {"message": message}
    if conversation_id is not None:
        body["conversation_id"] = conversation_id
    return harness.client.post(_CHAT_PATH, json=body, headers=_AUTH)


def _complete(body: str) -> dict[str, object]:
    return dict(parse_sse(body))["message_complete"]


def test_chat_grounds_its_answer_in_the_tool_result(harness: Harness) -> None:
    harness.respond_from(_upstream_responder())
    harness.script_model(
        _tool_call("get_spending_summary", {"start_date": "2026-10-01", "end_date": "2026-10-31"}),
        _answer("You spent 120.00 across 4 transactions in October."),
    )

    response = _post(harness, "How much did I spend this month?")

    assert response.status_code == 200
    names = [name for name, _ in parse_sse(response.text)]
    assert names[0] == "message_start"
    assert names[-1] == "message_complete"

    complete = _complete(response.text)
    assert complete["content"] == "You spent 120.00 across 4 transactions in October."
    assert complete["toolCalls"] == ["get_spending_summary"]

    summary_requests = harness.requests_to(_SUMMARY_PATH)
    assert len(summary_requests) == 1
    # The tool call carries only validated filters: never a user identifier.
    assert dict(summary_requests[0].url.params) == {"startDate": "2026-10-01", "endDate": "2026-10-31"}
    assert summary_requests[0].headers["authorization"] == "Bearer valid-token"


def test_turn_is_persisted_and_readable_by_its_owner(harness: Harness) -> None:
    harness.respond_from(_upstream_responder())
    harness.script_model(
        _tool_call("get_spending_summary", {"start_date": "2026-10-01", "end_date": "2026-10-31"}),
        _answer("You spent 120.00."),
    )

    complete = _complete(_post(harness, "How much did I spend this month?").text)
    conversation_id = complete["conversationId"]

    listing = harness.client.get(_CONVERSATIONS_PATH, headers=_AUTH)
    assert listing.status_code == 200
    conversations = listing.json()
    assert len(conversations) == 1
    assert conversations[0]["id"] == conversation_id
    assert conversations[0]["title"] == "How much did I spend this month?"

    detail = harness.client.get(f"{_CONVERSATIONS_PATH}/{conversation_id}", headers=_AUTH)
    assert detail.status_code == 200
    messages = detail.json()["messages"]
    assert [message["role"] for message in messages] == ["user", "assistant"]
    assert messages[1]["content"] == "You spent 120.00."
    assert complete["messageId"] == messages[1]["id"]


def test_multi_turn_reuses_the_same_conversation(harness: Harness) -> None:
    harness.respond_from(_upstream_responder())

    harness.script_model(_answer("Hello, I can help with your expenses."))
    first = _complete(_post(harness, "Hello").text)

    harness.script_model(_answer("You are welcome."))
    second = _complete(_post(harness, "Thanks", conversation_id=str(first["conversationId"])).text)
    assert second["conversationId"] == first["conversationId"]

    detail = harness.client.get(f"{_CONVERSATIONS_PATH}/{first['conversationId']}", headers=_AUTH)
    assert len(detail.json()["messages"]) == 4


def test_conversation_history_is_sent_back_to_the_model(harness: Harness) -> None:
    harness.respond_from(_upstream_responder())

    harness.script_model(
        _tool_call("get_spending_summary", {"start_date": "2026-10-01", "end_date": "2026-10-31"}),
        _answer("First answer."),
    )
    conversation_id = _complete(_post(harness, "How much did I spend this month?").text)["conversationId"]

    provider = harness.script_model(_answer("Second answer."))
    _post(harness, "How much did I spend last month?", conversation_id=str(conversation_id))

    # The second turn must carry the earlier exchange as context.
    contents = [message.content for message in provider.calls[0].messages if message.content]
    assert "First answer." in contents
    assert "How much did I spend this month?" in contents


def test_tool_calls_are_bounded_per_turn(settings: Settings) -> None:
    bounded = settings.model_copy(update={"agent_max_tool_calls": 1})
    with Harness(bounded) as harness:
        harness.respond_from(_upstream_responder())
        harness.script_model(
            _tool_call("get_spending_summary", {"start_date": "2026-10-01", "end_date": "2026-10-31"}),
            _answer("Final grounded answer."),
        )

        complete = _complete(_post(harness, "How much did I spend?").text)

        assert complete["toolCalls"] == ["get_spending_summary"]
        assert len(harness.requests_to(_SUMMARY_PATH)) == 1


def test_unregistered_tool_is_refused_without_an_upstream_call(harness: Harness) -> None:
    harness.respond_from(_upstream_responder())
    harness.script_model(_tool_call("delete_everything", {"all": True}), _answer("never"))

    complete = _complete(_post(harness, "How much did I spend this month?").text)

    assert complete["toolCalls"] == []
    assert harness.requests_to(_SUMMARY_PATH) == []
    assert "won't guess" in str(complete["content"])


def test_invalid_tool_arguments_are_refused(harness: Harness) -> None:
    harness.respond_from(_upstream_responder())
    harness.script_model(_tool_call("get_spending_summary", {"userId": 2}), _answer("never"))

    complete = _complete(_post(harness, "How much did I spend this month?").text)

    assert harness.requests_to(_SUMMARY_PATH) == []
    assert complete["content"] == (
        "I couldn't retrieve the data needed to answer that, and I won't guess at the figures. "
        "Please try again shortly."
    )


class _UnavailableProvider(ModelProvider):
    name = "unavailable"

    async def complete(self, request: ChatRequest) -> ChatResponse:
        raise ProviderUnavailableError("provider is down")


def test_model_failure_never_produces_fabricated_figures(harness: Harness) -> None:
    harness.respond_from(_upstream_responder())
    harness.use_model(_UnavailableProvider())

    complete = _complete(_post(harness, "How much did I spend this month?").text)

    assert "temporarily unavailable" in str(complete["content"])
    assert complete["toolCalls"] == []
    assert harness.requests_to(_SUMMARY_PATH) == []


def test_upstream_failure_is_reported_without_inventing_a_total(harness: Harness) -> None:
    harness.respond_from(_upstream_responder(summary_status=503))
    harness.script_model(
        _tool_call("get_spending_summary", {"start_date": "2026-10-01", "end_date": "2026-10-31"}),
        _answer("never"),
    )

    complete = _complete(_post(harness, "How much did I spend this month?").text)

    assert complete["toolCalls"] == ["get_spending_summary"]
    assert "won't guess" in str(complete["content"])


def _deltas(body: str) -> list[str]:
    return [str(data["text"]) for name, data in parse_sse(body) if name == "token"]


def test_the_grounded_answer_arrives_incrementally(harness: Harness) -> None:
    harness.respond_from(_upstream_responder())
    harness.script_model(
        _tool_call("get_spending_summary", {"start_date": "2026-10-01", "end_date": "2026-10-31"}),
        _answer("You spent 120.00 across 4 transactions in October."),
    )

    response = _post(harness, "How much did I spend this month?")

    deltas = _deltas(response.text)
    assert len(deltas) > 1
    assert "".join(deltas) == "You spent 120.00 across 4 transactions in October."
    assert _complete(response.text)["content"] == "You spent 120.00 across 4 transactions in October."


def test_a_conversational_turn_arrives_incrementally(harness: Harness) -> None:
    harness.respond_from(_upstream_responder())
    harness.script_model(_answer("Hello, I can help with your expenses."))

    deltas = _deltas(_post(harness, "Hello there").text)

    assert len(deltas) > 1
    assert "".join(deltas) == "Hello, I can help with your expenses."


def test_a_data_question_answered_from_memory_is_never_streamed(harness: Harness) -> None:
    harness.respond_from(_upstream_responder())
    # The model answered a data question without retrieving anything: invented figures.
    harness.script_model(_answer("You spent 999.99 on nothing in particular."))

    response = _post(harness, "How much did I spend this month?")

    complete = _complete(response.text)
    # Not as a delta, and not in the final content.
    assert "999.99" not in response.text
    assert "can't answer it reliably" in str(complete["content"])
    assert _deltas(response.text) == [complete["content"]]


def _draft(body: str) -> dict[str, Any]:
    return dict(parse_sse(body))["draft"]


def test_a_record_request_is_drafted_and_issues_no_write(harness: Harness) -> None:
    harness.respond_from(_upstream_responder())

    response = _post(harness, "Add a 12.50 coffee expense yesterday")

    proposal = _draft(response.text)
    assert proposal["kind"] == "expense"
    assert proposal["fields"]["amount"] == 12.5
    assert proposal["fields"]["description"] == "coffee"
    assert _complete(response.text)["termination"] == "drafted"
    # The draft arrives before the completion, so a client can attach it to the
    # message it is about to finalise.
    names = [name for name, _ in parse_sse(response.text)]
    assert names[0] == "message_start"
    assert names[-1] == "message_complete"
    assert names.index("draft") < names.index("message_complete")
    # The whole turn reached Spring Boot with reads only: no create, update or delete.
    assert {request.method for request in harness.requests} == {"GET"}


def test_a_draft_is_produced_without_consulting_the_model(harness: Harness) -> None:
    harness.respond_from(_upstream_responder())
    harness.use_model(_UnavailableProvider())

    response = _post(harness, "Add a 12.50 coffee expense yesterday")

    assert _draft(response.text)["kind"] == "expense"
    assert "Nothing has been saved" in str(_complete(response.text)["content"])


def test_a_record_request_without_an_amount_asks_for_one(harness: Harness) -> None:
    harness.respond_from(_upstream_responder())

    response = _post(harness, "Add a coffee expense")

    assert "draft" not in [name for name, _ in parse_sse(response.text)]
    complete = _complete(response.text)
    assert complete["termination"] == "draft_incomplete"
    assert "need the amount" in str(complete["content"])


def test_a_draft_is_persisted_as_text_without_a_write(harness: Harness) -> None:
    harness.respond_from(_upstream_responder())

    complete = _complete(_post(harness, "Set my budget for next month to 5000").text)

    detail = harness.client.get(f"{_CONVERSATIONS_PATH}/{complete['conversationId']}", headers=_AUTH)
    messages = detail.json()["messages"]
    assert [message["role"] for message in messages] == ["user", "assistant"]
    assert "Nothing has been saved" in messages[1]["content"]
    assert {request.method for request in harness.requests} == {"GET"}
