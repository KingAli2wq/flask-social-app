"""SQLAlchemy ORM model for stored media assets."""
from __future__ import annotations

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class MediaAsset(Base):
    __tablename__ = "media_assets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    key = Column(String(1024), nullable=False, unique=True)
    url = Column(String(2048), nullable=False)
    bucket = Column(String(255), nullable=False)
    content_type = Column(String(255), nullable=False)
    folder = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    uploader = relationship("User", back_populates="media_assets")
    posts = relationship("Post", back_populates="media_asset")


__all__ = ["MediaAsset"]
