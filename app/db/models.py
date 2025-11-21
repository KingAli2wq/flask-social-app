"""ORM models backed by PostgreSQL."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


def _utcnow() -> datetime:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc)


class User(Base):
    """Persisted user accounts."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(150), unique=True, nullable=False, index=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    bio: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    website: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False)
    last_active_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    posts: Mapped[list["Post"]] = relationship("Post", back_populates="author", cascade="all, delete-orphan")
    sent_messages: Mapped[list["Message"]] = relationship(
        "Message",
        back_populates="sender",
        cascade="all, delete-orphan",
        foreign_keys="Message.sender_id",
    )
    received_messages: Mapped[list["Message"]] = relationship(
        "Message",
        back_populates="recipient",
        foreign_keys="Message.recipient_id",
    )
    notifications: Mapped[list["Notification"]] = relationship(
        "Notification",
        back_populates="recipient",
        cascade="all, delete-orphan",
        foreign_keys="Notification.recipient_id",
    )
    media_assets: Mapped[list["MediaAsset"]] = relationship(
        "MediaAsset",
        back_populates="uploader",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:  # pragma: no cover - repr helper
        return f"User(id={self.id!s}, username={self.username!r})"


class Post(Base):
    """Persisted social posts."""

    __tablename__ = "posts"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    media_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    media_asset_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("media_assets.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    author: Mapped[User] = relationship("User", back_populates="posts")
    media_asset: Mapped["MediaAsset | None"] = relationship("MediaAsset", back_populates="posts")

    def __repr__(self) -> str:  # pragma: no cover - repr helper
        return f"Post(id={self.id!s}, user_id={self.user_id!s})"


class Message(Base):
    """Persisted chat or direct messages."""

    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chat_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    sender_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    recipient_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    attachments: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    sender: Mapped[User] = relationship("User", foreign_keys=[sender_id], back_populates="sent_messages")
    recipient: Mapped[User | None] = relationship("User", foreign_keys=[recipient_id], back_populates="received_messages")

    def __repr__(self) -> str:  # pragma: no cover - repr helper
        return f"Message(id={self.id!s}, chat_id={self.chat_id!r})"


class Notification(Base):
    """Persisted user notifications."""

    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recipient_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    type: Mapped[str] = mapped_column(String(100), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    recipient: Mapped[User] = relationship("User", foreign_keys=[recipient_id], back_populates="notifications")
    actor: Mapped[User | None] = relationship("User", foreign_keys=[actor_id])

    def __repr__(self) -> str:  # pragma: no cover - repr helper
        return f"Notification(id={self.id!s}, recipient_id={self.recipient_id!s})"


class MediaAsset(Base):
    """Metadata for DigitalOcean Spaces uploads."""

    __tablename__ = "media_assets"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    key: Mapped[str] = mapped_column(String(1024), nullable=False, unique=True)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    bucket: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(255), nullable=False)
    folder: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    uploader: Mapped[User | None] = relationship("User", back_populates="media_assets")
    posts: Mapped[list[Post]] = relationship("Post", back_populates="media_asset")

    def __repr__(self) -> str:  # pragma: no cover - repr helper
        return f"MediaAsset(id={self.id!s}, key={self.key!r})"
