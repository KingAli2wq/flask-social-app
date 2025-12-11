"""Schemas supporting the AI chatbot endpoints."""
from __future__ import annotations

from datetime import datetime
from typing import List
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class ChatbotPromptRequest(BaseModel):
    session_id: UUID | None = Field(
        default=None,
        description="Existing chatbot session to append to. Omit to start a new session.",
    )
    message: str = Field(..., min_length=1, max_length=2000)
    persona: str | None = Field(default=None, max_length=64)
    title: str | None = Field(default=None, max_length=160)
    include_public_context: bool = Field(
        default=True,
        description="When true, recent posts and stories will be summarized for the model.",
    )
    mode: str | None = Field(
        default=None,
        max_length=64,
        description="Optional alias for persona used by the UI to switch behavior modes.",
    )

    @model_validator(mode="after")
    def trim_message(self) -> "ChatbotPromptRequest":
        self.message = (self.message or "").strip()
        if not self.message:
            raise ValueError("Message cannot be empty")
        persona_source = (self.mode or self.persona or "").strip().lower()
        if persona_source:
            self.persona = persona_source
            self.mode = persona_source
        elif self.persona:
            self.persona = (self.persona or "").strip().lower() or None
            self.mode = self.persona
        return self


class ChatbotSessionCreateRequest(BaseModel):
    persona: str | None = Field(default=None, max_length=64)
    mode: str | None = Field(default=None, max_length=64)
    title: str | None = Field(default=None, max_length=160)

    @model_validator(mode="after")
    def normalize_fields(self) -> "ChatbotSessionCreateRequest":
        persona_source = (self.mode or self.persona or "").strip().lower()
        if persona_source:
            self.persona = persona_source
            self.mode = persona_source
        else:
            self.persona = None
            self.mode = None
        self.title = (self.title or "").strip() or None
        return self


class ChatbotMessagePayload(BaseModel):
    id: UUID
    session_id: UUID
    role: str
    content: str
    model: str | None = None
    created_at: datetime


class ChatbotSessionResponse(BaseModel):
    session_id: UUID
    persona: str
    title: str | None = None
    updated_at: datetime
    status: str = Field(default="active")
    messages: List[ChatbotMessagePayload]


class ChatbotSessionSummary(BaseModel):
    session_id: UUID
    title: str | None = None
    persona: str
    updated_at: datetime
    status: str = Field(default="active")
    last_message_preview: str | None = None


__all__ = [
    "ChatbotPromptRequest",
    "ChatbotSessionCreateRequest",
    "ChatbotMessagePayload",
    "ChatbotSessionResponse",
    "ChatbotSessionSummary",
]
