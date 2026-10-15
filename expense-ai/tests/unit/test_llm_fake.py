from __future__ import annotations

from app.integrations.model_provider.fake import FakeModelProvider
from app.integrations.model_provider.types import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    FinishReason,
    Role,
)


async def test_fake_provider_echoes_last_user_message_when_unscripted() -> None:
    provider = FakeModelProvider()

    response = await provider.complete(
        ChatRequest(
            messages=[
                ChatMessage(role=Role.SYSTEM, content="ignore me"),
                ChatMessage(role=Role.USER, content="How are my goals?"),
            ]
        )
    )

    assert response.content == "[fake] How are my goals?"
    assert response.finish_reason is FinishReason.STOP


async def test_fake_provider_returns_scripted_responses_in_order() -> None:
    scripted = ChatResponse(provider="fake", model="fake-1", content="first")
    provider = FakeModelProvider(scripted_responses=[scripted])

    response = await provider.complete(ChatRequest(messages=[ChatMessage(role=Role.USER, content="hi")]))

    assert response is scripted
    assert len(provider.calls) == 1
