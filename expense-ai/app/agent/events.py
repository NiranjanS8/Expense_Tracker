"""Typed server-sent events emitted by a chat turn.

The payloads are stable and deliberately small. No event carries a bearer token,
an internal tool argument, a stack trace, or another user's identifier.

``token`` deltas are provisional: they arrive as the model produces them, while
``message_complete.content`` is the authoritative answer. A client must reconcile
to that value rather than assume the deltas always concatenate to it, because a
grounded draft that turns out to be superseded is retracted there. A turn that
never streamed sends its whole answer as a single ``token`` instead.

``draft`` carries the values for one of the application's own forms. It is a
proposal only: the client pre-fills a screen with it and the user saves it, so a
draft is never itself a change.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

MESSAGE_START = "message_start"
STATUS = "status"
TOKEN = "token"
DRAFT = "draft"
MESSAGE_COMPLETE = "message_complete"
ERROR = "error"


@dataclass(frozen=True)
class StreamEvent:
    event: str
    data: dict[str, Any] = field(default_factory=dict)


def message_start(*, conversation_id: str) -> StreamEvent:
    return StreamEvent(MESSAGE_START, {"conversationId": conversation_id})


def status(*, stage: str, tool: str | None = None) -> StreamEvent:
    payload: dict[str, Any] = {"stage": stage}
    if tool is not None:
        payload["tool"] = tool
    return StreamEvent(STATUS, payload)


def token(*, text: str) -> StreamEvent:
    return StreamEvent(TOKEN, {"text": text})


def draft(*, kind: str, fields: dict[str, Any], summary: str) -> StreamEvent:
    """Values for one of the application's own forms; nothing has been saved."""
    return StreamEvent(DRAFT, {"kind": kind, "fields": fields, "summary": summary})


def message_complete(
    *,
    conversation_id: str,
    message_id: int | None,
    content: str,
    termination: str,
    tool_calls: list[str],
) -> StreamEvent:
    return StreamEvent(
        MESSAGE_COMPLETE,
        {
            "conversationId": conversation_id,
            "messageId": message_id,
            "content": content,
            "termination": termination,
            "toolCalls": tool_calls,
        },
    )


def error(*, code: str, message: str, correlation_id: str | None) -> StreamEvent:
    return StreamEvent(ERROR, {"code": code, "message": message, "correlationId": correlation_id})
