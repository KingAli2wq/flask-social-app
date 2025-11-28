"""SQLAlchemy ORM model for notifications."""
from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func, expression

from app.database import Base


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recipient_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sender_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    type = Column(String(100), nullable=False)
    content = Column(Text, nullable=False)
    read = Column(Boolean, nullable=False, server_default=expression.false(), default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    payload = Column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    emailed_at = Column(DateTime(timezone=True), nullable=True)

    recipient = relationship(
        "User",
        foreign_keys=[recipient_id],
        back_populates="notifications_received",
    )
    sender = relationship(
        "User",
        foreign_keys=[sender_id],
        back_populates="notifications_sent",
    )


__all__ = ["Notification"]
