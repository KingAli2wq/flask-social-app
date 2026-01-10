"""Association tables shared across ORM models."""
from __future__ import annotations

from sqlalchemy import Column, DateTime, ForeignKey, String, Table, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.database import Base


group_chat_members = Table(
    "group_chat_members",
    Base.metadata,
    Column("group_chat_id", UUID(as_uuid=True), ForeignKey("group_chats.id", ondelete="CASCADE"), primary_key=True),
    Column("user_id", UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("joined_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    Column("role", String(32), nullable=False, server_default=text("'member'")),
)


__all__ = ["group_chat_members"]
