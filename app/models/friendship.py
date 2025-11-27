"""ORM model representing a mutual friendship thread between two users."""
from __future__ import annotations

import secrets
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


def _generate_thread_id() -> str:
    return secrets.token_hex(24)


def _generate_lock() -> str:
    return secrets.token_hex(32)


class Friendship(Base):
    __tablename__ = "friendships"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_a_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    user_b_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    thread_id = Column(String(96), unique=True, nullable=False, default=_generate_thread_id)
    lock_code = Column(String(128), unique=True, nullable=False, default=_generate_lock)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user_a = relationship("User", foreign_keys=[user_a_id], back_populates="friendships_a")
    user_b = relationship("User", foreign_keys=[user_b_id], back_populates="friendships_b")

    __table_args__ = (UniqueConstraint("user_a_id", "user_b_id", name="uq_friendship_pair"),)

    def involves(self, user_id: uuid.UUID) -> bool:
        return user_id in {self.user_a_id, self.user_b_id}


__all__ = ["Friendship"]
