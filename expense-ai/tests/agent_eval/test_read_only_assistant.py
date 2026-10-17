"""Agent evaluation: a versioned dataset run deterministically against the app.

The dataset in ``evals/datasets/read_only_assistant.json`` records, for each
representative prompt, the tool choice it should drive, the evidence the model
must be shown, and the answer behaviour expected. Model steps are scripted and
Spring Boot is stubbed, so the suite is deterministic, offline and cheap to run
in CI; a model-backed evaluation is a separate, opt-in concern.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
import pytest
from pydantic import BaseModel, ConfigDict, Field

from app.agent.policies import classify_intent
from app.core.config import Settings
from app.integrations.model_provider import (
    ChatResponse,
    FakeModelProvider,
    FinishReason,
    Role,
    ToolCall,
)
from tests.conftest import CURRENT_USER_PATH, Harness, Responder, parse_sse

_DATASET_PATH = Path(__file__).resolve().parents[2] / "evals" / "datasets" / "read_only_assistant.json"
_CHAT_PATH = "/api/v1/chat"
_AUTH = {"Authorization": "Bearer eval-token"}


class _ToolCallSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class _ModelStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_call: _ToolCallSpec | None = None
    answer: str | None = None


class _UpstreamRoute(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    status: int = 200
    body: Any = None


class _Expectation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_calls: list[str]
    termination: str
    answer_contains: list[str] = Field(default_factory=list)
    answer_excludes: list[str] = Field(default_factory=list)
    grounding_evidence: list[str] = Field(default_factory=list)
    upstream_paths: dict[str, int] = Field(default_factory=dict)


class _EvalCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    category: str
    prompt: str
    intent: str
    upstream: list[_UpstreamRoute] = Field(default_factory=list)
    model: list[_ModelStep]
    expect: _Expectation


class _Dataset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int
    description: str
    cases: list[_EvalCase]


def _load_dataset() -> _Dataset:
    return _Dataset.model_validate_json(_DATASET_PATH.read_text(encoding="utf-8"))


DATASET = _load_dataset()


def _responder(case: _EvalCase) -> Responder:
    routes = {route.path: route for route in case.upstream}

    def responder(request: httpx.Request) -> httpx.Response:
        if request.url.path == CURRENT_USER_PATH:
            return httpx.Response(
                200,
                json={"id": 1, "fullName": "Eval User", "email": "eval@expensetracker.com", "role": "USER"},
            )
        route = routes.get(request.url.path)
        if route is None:
            return httpx.Response(404)
        return httpx.Response(route.status, json=route.body)

    return responder


def _script(case: _EvalCase) -> list[ChatResponse]:
    responses: list[ChatResponse] = []
    for index, step in enumerate(case.model):
        if step.tool_call is not None:
            responses.append(
                ChatResponse(
                    provider="fake",
                    model="fake-1",
                    tool_calls=[
                        ToolCall(
                            id=f"call-{index + 1}",
                            name=step.tool_call.name,
                            arguments=step.tool_call.arguments,
                        )
                    ],
                    finish_reason=FinishReason.TOOL_CALLS,
                )
            )
        else:
            responses.append(
                ChatResponse(
                    provider="fake",
                    model="fake-1",
                    content=step.answer or "",
                    finish_reason=FinishReason.STOP,
                )
            )
    return responses


def _complete(body: str) -> dict[str, Any]:
    return dict(parse_sse(body))["message_complete"]


def _tool_evidence(provider: FakeModelProvider) -> str:
    return " ".join(
        message.content or ""
        for call in provider.calls
        for message in call.messages
        if message.role is Role.TOOL
    )


@pytest.mark.parametrize("case", DATASET.cases, ids=lambda case: case.id)
def test_case(case: _EvalCase, settings: Settings) -> None:
    assert classify_intent(case.prompt) == case.intent, "the deterministic intent gate changed"

    with Harness(settings) as harness:
        harness.respond_from(_responder(case))
        provider = harness.script_model(*_script(case))

        response = harness.client.post(_CHAT_PATH, json={"message": case.prompt}, headers=_AUTH)

        assert response.status_code == 200
        complete = _complete(response.text)
        content = str(complete["content"])

        assert complete["toolCalls"] == case.expect.tool_calls
        assert complete["termination"] == case.expect.termination
        for needle in case.expect.answer_contains:
            assert needle in content, f"answer missing {needle!r}"
        for needle in case.expect.answer_excludes:
            assert needle not in content, f"answer leaked {needle!r}"

        evidence = _tool_evidence(provider)
        for needle in case.expect.grounding_evidence:
            assert needle in evidence, f"model never saw {needle!r}"

        for path, count in case.expect.upstream_paths.items():
            assert len(harness.requests_to(path)) == count, f"unexpected calls to {path}"
