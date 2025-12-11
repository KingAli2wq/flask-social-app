"""ORM models for AI chatbot sessions and transcripts."""
from __future__ import annotations

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.types import JSON

from app.database import Base


class AiChatSession(Base):
    __tablename__ = "ai_chat_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(160), nullable=True)
    persona = Column(String(64), nullable=False, server_default="companion")
    status = Column(String(32), nullable=False, server_default="active", default="active")
    system_prompt = Column(Text, nullable=True)
    context_metadata = Column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    last_message_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="ai_chat_sessions")
    messages = relationship(
        "AiChatMessage",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="AiChatMessage.created_at",
    )


class AiChatMessage(Base):
    __tablename__ = "ai_chat_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("ai_chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    sender_role = Column(String(32), nullable=False)
    content_ciphertext = Column(Text, nullable=False)
    context_metadata = Column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    model = Column(String(128), nullable=True)
    token_count_prompt = Column(Integer, nullable=True)
    token_count_completion = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    session = relationship("AiChatSession", back_populates="messages")


__all__ = ["AiChatSession", "AiChatMessage"]
