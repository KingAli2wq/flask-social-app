"""SQLAlchemy ORM model for application users."""
from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Column, DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func, expression

from app.database import Base
from .associations import group_chat_members
from .friend_request import FriendRequest
from .friendship import Friendship
from .follow import Follow


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(150), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=True)
    display_name = Column(String(150), nullable=True)
    hashed_password = Column(String(255), nullable=False)
    bio = Column(String(500), nullable=True)
    location = Column(String(255), nullable=True)
    website = Column(String(255), nullable=True)
    avatar_url = Column(String(1024), nullable=True)
    role = Column(String(32), nullable=False, server_default="user", default="user")
    email_verified_at = Column(DateTime(timezone=True), nullable=True)
    email_verification_code = Column(String(12), nullable=True)
    email_verification_sent_at = Column(DateTime(timezone=True), nullable=True)
    email_dm_notifications = Column(Boolean, nullable=False, server_default=expression.false(), default=False)
    allow_friend_requests = Column(Boolean, nullable=False, server_default=expression.true(), default=True)
    dm_followers_only = Column(Boolean, nullable=False, server_default=expression.false(), default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    last_active_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    posts = relationship("Post", back_populates="author", cascade="all, delete-orphan")
    sent_messages = relationship(
        "Message",
        foreign_keys="Message.sender_id",
        back_populates="sender",
        cascade="all, delete-orphan",
    )
    received_messages = relationship(
        "Message",
        foreign_keys="Message.recipient_id",
        back_populates="recipient",
    )
    notifications_received = relationship(
        "Notification",
        foreign_keys="Notification.recipient_id",
        back_populates="recipient",
        cascade="all, delete-orphan",
    )
    notifications_sent = relationship(
        "Notification",
        foreign_keys="Notification.sender_id",
        back_populates="sender",
    )
    owned_group_chats = relationship("GroupChat", back_populates="owner", cascade="all, delete-orphan")
    group_memberships = relationship("GroupChat", secondary=group_chat_members, back_populates="members")
    media_assets = relationship("MediaAsset", back_populates="uploader", cascade="all, delete-orphan")
    stories = relationship("Story", back_populates="author", cascade="all, delete-orphan")
    ai_chat_sessions = relationship("AiChatSession", back_populates="user", cascade="all, delete-orphan")
    friendships_a = relationship(
        "Friendship",
        foreign_keys="Friendship.user_a_id",
        back_populates="user_a",
        cascade="all, delete-orphan",
    )
    friendships_b = relationship(
        "Friendship",
        foreign_keys="Friendship.user_b_id",
        back_populates="user_b",
        cascade="all, delete-orphan",
    )
    friend_requests_sent = relationship(
        "FriendRequest",
        foreign_keys="FriendRequest.sender_id",
        back_populates="sender",
        cascade="all, delete-orphan",
    )
    friend_requests_received = relationship(
        "FriendRequest",
        foreign_keys="FriendRequest.recipient_id",
        back_populates="recipient",
        cascade="all, delete-orphan",
    )
    follower_relations = relationship(
        "Follow",
        foreign_keys="Follow.following_id",
        back_populates="following",
        cascade="all, delete-orphan",
    )
    following_relations = relationship(
        "Follow",
        foreign_keys="Follow.follower_id",
        back_populates="follower",
        cascade="all, delete-orphan",
    )
    post_likes = relationship("PostLike", back_populates="user", cascade="all, delete-orphan")
    media_likes = relationship("MediaLike", back_populates="user", cascade="all, delete-orphan")
    media_dislikes = relationship("MediaDislike", back_populates="user", cascade="all, delete-orphan")
    post_dislikes = relationship("PostDislike", back_populates="user", cascade="all, delete-orphan")
    post_comments = relationship("PostComment", back_populates="user", cascade="all, delete-orphan")
    media_comments = relationship("MediaComment", back_populates="user", cascade="all, delete-orphan")


__all__ = ["User"]
