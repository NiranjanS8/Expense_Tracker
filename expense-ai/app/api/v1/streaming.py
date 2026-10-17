"""Server-sent-event encoding.

The wire format is the standard ``event:``/``data:`` pair terminated by a blank
line, so any SSE client can consume it.
"""

from __future__ import annotations

import json

from app.agent.events import StreamEvent

SSE_MEDIA_TYPE = "text/event-stream"
SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


def encode_sse(event: StreamEvent) -> str:
    payload = json.dumps(event.data, separators=(",", ":"), default=str)
    return f"event: {event.event}\ndata: {payload}\n\n"
