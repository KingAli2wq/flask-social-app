"""SQLAlchemy ORM model for ephemeral user stories."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Story(Base):
    __tablename__ = "stories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    media_asset_id = Column(UUID(as_uuid=True), ForeignKey("media_assets.id", ondelete="SET NULL"), nullable=True, index=True)
    media_url = Column(String(2048), nullable=False)
    media_content_type = Column(String(255), nullable=True)
    text_overlay = Column(String(280), nullable=True)
    text_color = Column(String(32), nullable=True)
    text_background = Column(String(120), nullable=True)
    text_position = Column(String(32), nullable=False, server_default="bottom-left")
    text_font_size = Column(Integer, nullable=False, server_default="22")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)

    author = relationship("User", back_populates="stories")
    media_asset = relationship("MediaAsset")

    def is_active(self, *, reference: datetime | None = None) -> bool:
        reference = reference or datetime.now(tz=self.created_at.tzinfo)
        return reference < self.expires_at


__all__ = ["Story"]
