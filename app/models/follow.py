"""SQLAlchemy ORM model for follower relationships."""
from __future__ import annotations

from sqlalchemy import Column, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Follow(Base):
    __tablename__ = "follows"

    follower_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    following_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    follower = relationship("User", foreign_keys=[follower_id], back_populates="following_relations")
    following = relationship("User", foreign_keys=[following_id], back_populates="follower_relations")


__all__ = ["Follow"]
