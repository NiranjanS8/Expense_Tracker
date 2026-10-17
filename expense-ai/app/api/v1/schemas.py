"""Response models for the conversation API.

Field names are snake_case on the Python side and camelCase on the wire, matching
the existing Spring Boot JSON conventions the frontend already consumes.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class _ApiModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class ConversationSummary(_ApiModel):
    id: str
    title: str
    status: str
    created_at: datetime
    updated_at: datetime


class MessageView(_ApiModel):
    id: int
    role: str
    content: str
    created_at: datetime


class ConversationDetail(ConversationSummary):
    messages: list[MessageView]
