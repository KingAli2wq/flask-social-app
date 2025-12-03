"""SQLAlchemy ORM model for stored media assets."""
from __future__ import annotations

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, Text, UniqueConstraint
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
    likes = relationship("MediaLike", back_populates="asset", cascade="all, delete-orphan")
    dislikes = relationship("MediaDislike", back_populates="asset", cascade="all, delete-orphan")
    comments = relationship("MediaComment", back_populates="asset", cascade="all, delete-orphan")


class MediaLike(Base):
    __tablename__ = "media_likes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    media_asset_id = Column(UUID(as_uuid=True), ForeignKey("media_assets.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    asset = relationship("MediaAsset", back_populates="likes")
    user = relationship("User", back_populates="media_likes")

    __table_args__ = (UniqueConstraint("media_asset_id", "user_id", name="uq_media_likes_asset_user"),)


class MediaDislike(Base):
    __tablename__ = "media_dislikes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    media_asset_id = Column(UUID(as_uuid=True), ForeignKey("media_assets.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    asset = relationship("MediaAsset", back_populates="dislikes")
    user = relationship("User", back_populates="media_dislikes")

    __table_args__ = (UniqueConstraint("media_asset_id", "user_id", name="uq_media_dislikes_asset_user"),)


class MediaComment(Base):
    __tablename__ = "media_comments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    media_asset_id = Column(UUID(as_uuid=True), ForeignKey("media_assets.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    parent_id = Column(UUID(as_uuid=True), ForeignKey("media_comments.id", ondelete="CASCADE"), nullable=True, index=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    asset = relationship("MediaAsset", back_populates="comments")
    user = relationship("User", back_populates="media_comments")
    parent = relationship("MediaComment", remote_side=[id], back_populates="replies")
    replies = relationship("MediaComment", back_populates="parent", cascade="all, delete-orphan")


__all__ = ["MediaAsset", "MediaLike", "MediaDislike", "MediaComment"]
