"""Deterministic model provider for tests and key-less local runs.

It never invents financial data: without a scripted response it echoes the most
recent user message prefixed with ``[fake]``, which is obviously synthetic.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import ClassVar

from app.integrations.model_provider.base import ModelProvider, ProviderConfig
from app.integrations.model_provider.types import (
    ChatRequest,
    ChatResponse,
    FinishReason,
    Role,
    TokenUsage,
)


class FakeModelProvider(ModelProvider):
    name: ClassVar[str] = "fake"

    def __init__(
        self,
        config: ProviderConfig | None = None,
        *,
        scripted_responses: Sequence[ChatResponse] | None = None,
    ) -> None:
        self._scripted = list(scripted_responses or [])
        self.calls: list[ChatRequest] = []

    async def complete(self, request: ChatRequest) -> ChatResponse:
        self.calls.append(request)

        if self._scripted:
            return self._scripted.pop(0)

        last_user = next(
            (message.content for message in reversed(request.messages) if message.role is Role.USER),
            None,
        )
        return ChatResponse(
            provider=self.name,
            model="fake-1",
            content=f"[fake] {last_user or ''}".strip(),
            finish_reason=FinishReason.STOP,
            usage=TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
        )
