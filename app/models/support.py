"""Support ticket records for inbound support email."""
from __future__ import annotations

import uuid

from sqlalchemy import Column, DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.database import Base


class SupportTicket(Base):
    __tablename__ = "support_tickets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    from_address = Column(String(512), nullable=False)
    to_address = Column(String(512), nullable=False)
    subject = Column(String(512), nullable=False)
    body = Column(Text, nullable=False)
    body_html = Column(Text, nullable=True)
    status = Column(String(32), nullable=False, server_default="open", default="open")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


__all__ = ["SupportTicket"]
