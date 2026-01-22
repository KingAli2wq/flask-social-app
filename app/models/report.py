"""SQLAlchemy ORM model for user-submitted reports."""
from __future__ import annotations

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Report(Base):
    __tablename__ = "reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    reporter_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # "post" | "message" | "user"
    target_type = Column(String(16), nullable=False, index=True)
    target_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    # Cached for moderation actions (ban/delete account) even if the original target is deleted.
    target_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    reason = Column(String(120), nullable=False)
    description = Column(Text, nullable=True)

    status = Column(String(32), nullable=False, server_default="open", default="open", index=True)

    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolved_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action_taken = Column(String(64), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    reporter = relationship("User", foreign_keys=[reporter_id])
    target_user = relationship("User", foreign_keys=[target_user_id])
    resolver = relationship("User", foreign_keys=[resolved_by])


__all__ = ["Report"]
