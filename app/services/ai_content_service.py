"""AI content helpers for generating bot posts from recent community activity."""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Sequence, cast
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..models import Post, User
from .auth_service import hash_password
from .chatbot_service import ChatbotServiceError, LLMClient, SocialAIChatClient, OLLAMA_TIMEOUT
from .post_service import create_post_record
from .safety import enforce_safe_text

logger = logging.getLogger(__name__)

_BOT_USERNAME = os.getenv("SOCIAL_AI_BOT_USERNAME", "SocialSphereAI")
_BOT_DISPLAY_NAME = os.getenv("SOCIAL_AI_BOT_DISPLAY_NAME", "Social AI")
_BOT_BIO = os.getenv("SOCIAL_AI_BOT_BIO", "Community highlights and friendly check-ins from Social AI.")

_MAX_CAPTION_LENGTH = 280
_DEFAULT_LOOKBACK_HOURS = 72
_DEFAULT_CONTEXT_POSTS = 12
_DEFAULT_TEMPERATURE = 0.35

_llm_client: LLMClient | None = None


def set_ai_content_llm_client(client: LLMClient | None) -> None:
    """Override the LLM client (useful for tests)."""

    global _llm_client
    _llm_client = client


def _get_llm_client() -> LLMClient:
    global _llm_client
    if _llm_client is None:
        _llm_client = SocialAIChatClient()
    return _llm_client


def _now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_ai_bot_user(db: Session) -> User:
    existing = db.scalars(select(User).where(User.username == _BOT_USERNAME)).first()
    if existing:
        return existing

    try:
        bot = User(
            username=_BOT_USERNAME,
            display_name=_BOT_DISPLAY_NAME,
            bio=_BOT_BIO,
            hashed_password=hash_password(f"{_BOT_USERNAME}-auto-secret"),
            role="user",
        )
        db.add(bot)
        db.commit()
        db.refresh(bot)
        return bot
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Failed to create AI bot user")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unable to create AI bot user") from exc


def _recent_posts(
    db: Session,
    *,
    limit: int = _DEFAULT_CONTEXT_POSTS,
    lookback_hours: int = _DEFAULT_LOOKBACK_HOURS,
    exclude_user_id: UUID | None = None,
) -> list[Post]:
    cutoff = _now() - timedelta(hours=max(lookback_hours, 1))
    stmt = select(Post).where(Post.created_at >= cutoff).order_by(Post.created_at.desc()).limit(max(limit, 1))
    if exclude_user_id is not None:
        stmt = stmt.where(Post.user_id != exclude_user_id)
    return list(db.scalars(stmt))


def _format_posts_for_prompt(posts: Sequence[Post]) -> str:
    if not posts:
        return "(No recent posts. Offer a welcoming, upbeat note to start the day.)"

    lines: list[str] = []
    for idx, post in enumerate(posts, start=1):
        caption = (cast(str, getattr(post, "caption", "")) or "").strip()
        author = getattr(post, "author", None)
        username = getattr(author, "username", None) or "user"
        created_at = getattr(post, "created_at", None)
        timestamp = created_at.isoformat() if isinstance(created_at, datetime) else "recent"
        snippet = caption.replace("\n", " ").replace("\r", " ").strip()
        if len(snippet) > 200:
            snippet = snippet[:197].rstrip() + "..."
        lines.append(f"{idx}. [{timestamp}] {username}: {snippet}")
    return "\n".join(lines)


def _build_prompt(posts: Sequence[Post]) -> list[dict[str, str]]:
    context = _format_posts_for_prompt(posts)
    system_prompt = (
        "You are Social AI, posting as the SocialSphere community bot. "
        "Write a single friendly, human-sounding post that fits naturally into a social feed. "
        "Keep it concise (under 200 characters), avoid hashtags and @mentions, and never ask the community to break rules."
    )
    user_prompt = (
        "Recent community posts (most recent first):\n"
        f"{context}\n\n"
        "Write one new post that feels relevant and supportive. Do not explain what you are doing; only return the post text."
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def _normalize_caption(text: str) -> str:
    normalized = (text or "").replace("\n", " ").replace("\r", " ").strip()
    if len(normalized) > _MAX_CAPTION_LENGTH:
        normalized = normalized[:_MAX_CAPTION_LENGTH].rstrip()
    enforce_safe_text(normalized, field_name="caption")
    if not normalized:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="AI response was empty")
    return normalized


def generate_ai_caption(
    db: Session,
    *,
    max_context_posts: int = _DEFAULT_CONTEXT_POSTS,
    lookback_hours: int = _DEFAULT_LOOKBACK_HOURS,
    temperature: float | None = None,
    exclude_user_id: UUID | None = None,
) -> str:
    posts = _recent_posts(
        db,
        limit=max_context_posts,
        lookback_hours=lookback_hours,
        exclude_user_id=exclude_user_id,
    )
    messages = _build_prompt(posts)

    client = _get_llm_client()
    try:
        temp = _DEFAULT_TEMPERATURE if temperature is None else temperature
        result = client.complete(messages=messages, temperature=temp)
    except ChatbotServiceError as exc:
        logger.error("AI content generation failed | timeout=%s", OLLAMA_TIMEOUT)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    caption = getattr(result, "content", "")
    return _normalize_caption(caption)


async def create_ai_post(
    db: Session,
    *,
    max_context_posts: int = _DEFAULT_CONTEXT_POSTS,
    lookback_hours: int = _DEFAULT_LOOKBACK_HOURS,
    temperature: float | None = None,
) -> Post:
    bot_user = ensure_ai_bot_user(db)
    caption = generate_ai_caption(
        db,
        max_context_posts=max_context_posts,
        lookback_hours=lookback_hours,
        temperature=temperature,
        exclude_user_id=cast(UUID, bot_user.id),
    )
    return await create_post_record(db, user_id=cast(UUID, bot_user.id), caption=caption)


__all__ = [
    "create_ai_post",
    "generate_ai_caption",
    "ensure_ai_bot_user",
    "set_ai_content_llm_client",
]
