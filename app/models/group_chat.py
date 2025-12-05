"""SQLAlchemy ORM model for group chats."""
from __future__ import annotations

import secrets
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base
from .associations import group_chat_members


def _generate_lock_code() -> str:
    return secrets.token_hex(24)


class GroupChat(Base):
    __tablename__ = "group_chats"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(120), nullable=False)
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    avatar_url = Column(String(512), nullable=True)
    lock_code = Column(String(128), nullable=False, unique=True, default=_generate_lock_code)
    encryption_key = Column(String(128), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    owner = relationship("User", back_populates="owned_group_chats")
    members = relationship("User", secondary=group_chat_members, back_populates="group_memberships")
    messages = relationship("Message", back_populates="group_chat", cascade="all, delete-orphan")


__all__ = ["GroupChat"]
