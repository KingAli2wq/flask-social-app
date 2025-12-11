"""Respond to @Social AI mentions in posts and comments."""
from __future__ import annotations

import asyncio
import logging
import os
import re
from typing import Any, Sequence, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Post, PostComment, User
from .ai_content_service import ensure_ai_bot_user
from .chatbot_service import ChatbotServiceError, LLMClient, SocialAIChatClient, OLLAMA_TIMEOUT
from .post_service import create_post_comment
from .safety import enforce_safe_text

logger = logging.getLogger(__name__)

_BOT_USERNAME = os.getenv("SOCIAL_AI_BOT_USERNAME", "SocialSphereAI")
_MAX_REPLY_LENGTH = 240
_MAX_CONTEXT_COMMENTS = 5
_DEFAULT_TEMPERATURE = 0.4
_MENTION_TIMEOUT = float(os.getenv("SOCIAL_AI_MENTION_TIMEOUT", "20"))

_llm_client: LLMClient | None = None


def set_ai_mention_llm_client(client: LLMClient | None) -> None:
    """Override the LLM client (useful for tests)."""

    global _llm_client
    _llm_client = client


def _get_llm_client() -> LLMClient:
    global _llm_client
    if _llm_client is None:
        _llm_client = SocialAIChatClient()
    return _llm_client


def _normalize(text: str | None) -> str:
    return (text or "").strip()


def _contains_ai_mention(text: str | None) -> bool:
    value = _normalize(text).lower()
    if not value:
        return False
    token = f"@{_BOT_USERNAME.lower()}"
    return token in value


def _recent_comment_context(db: Session, post_id: UUID, limit: int = _MAX_CONTEXT_COMMENTS) -> list[str]:
    stmt = (
        select(PostComment, User.username)
        .join(User, PostComment.user_id == User.id)
        .where(PostComment.post_id == post_id)
        .order_by(PostComment.created_at.desc())
        .limit(max(limit, 1))
    )
    rows = db.execute(stmt).all()
    context: list[str] = []
    for comment, username in rows:
        author = username or "user"
        snippet = (comment.content or "").replace("\n", " ").replace("\r", " ").strip()
        if len(snippet) > 160:
            snippet = snippet[:157].rstrip() + "..."
        context.append(f"{author}: {snippet}")
    return list(reversed(context))


def _build_messages(post: Post, actor_username: str, user_text: str, context: Sequence[str]) -> list[dict[str, str]]:
    system_prompt = (
        "You are SocialSphereAI, a friendly in-app bot replying inside post comments. "
        "Respond with one short comment (under 200 characters), upbeat and supportive. "
        "Avoid hashtags and avoid @-mentioning others unless greeting the user by name."
    )

    context_block = "\n".join(context) if context else "(no previous comments)"
    post_caption = _normalize(cast(str, getattr(post, "caption", "")))

    user_prompt = (
        f"Post caption: {post_caption or '(empty)'}\n"
        f"Latest thread: {context_block}\n"
        f"User @{actor_username} said: {user_text}\n"
        "Write a single friendly reply comment."
    )

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def _sanitize_reply(text: str) -> str:
    reply = _normalize(text).replace("\n", " ").replace("\r", " ")
    if len(reply) > _MAX_REPLY_LENGTH:
        reply = reply[:_MAX_REPLY_LENGTH].rstrip()
    enforce_safe_text(reply, field_name="comment")
    if not reply:
        raise ValueError("Empty AI reply")
    return reply


async def _generate_reply(db: Session, *, post: Post, actor_username: str, user_text: str) -> str | None:
    context = _recent_comment_context(db, cast(UUID, post.id), limit=_MAX_CONTEXT_COMMENTS)
    messages = _build_messages(post, actor_username, user_text, context)
    client = _get_llm_client()
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(client.complete, messages=messages, temperature=_DEFAULT_TEMPERATURE),
            timeout=_MENTION_TIMEOUT,
        )
    except ChatbotServiceError as exc:
        logger.error("AI mention reply failed | timeout=%s", OLLAMA_TIMEOUT)
        return None
    except (asyncio.TimeoutError, TimeoutError):
        logger.error("AI mention reply timed out after %s seconds", _MENTION_TIMEOUT)
        return None
    except Exception:
        logger.exception("AI mention reply failed unexpectedly")
        return None

    try:
        return _sanitize_reply(getattr(result, "content", ""))
    except Exception:
        logger.exception("AI mention reply was empty or unsafe")
        return None


def _should_respond(actor: User, text: str | None) -> bool:
    if (getattr(actor, "username", "") or "").lower() == _BOT_USERNAME.lower():
        return False
    return _contains_ai_mention(text)


async def respond_to_ai_mention_in_post(db: Session, *, post: Post, actor: User) -> dict[str, Any] | None:
    if not _should_respond(actor, getattr(post, "caption", None)):
        return None

    reply = await _generate_reply(db, post=post, actor_username=getattr(actor, "username", "user"), user_text=_normalize(post.caption))
    if not reply:
        return None

    bot_user = ensure_ai_bot_user(db)
    try:
        return create_post_comment(db, post_id=cast(UUID, post.id), author=bot_user, content=reply)
    except Exception:
        logger.exception("Failed to persist AI reply for post mention")
        return None


async def respond_to_ai_mention_in_comment(
    db: Session,
    *,
    post: Post,
    comment: dict[str, Any],
    actor: User,
) -> dict[str, Any] | None:
    if not _should_respond(actor, comment.get("content")):
        return None

    reply = await _generate_reply(
        db,
        post=post,
        actor_username=getattr(actor, "username", "user"),
        user_text=_normalize(cast(str, comment.get("content", ""))),
    )
    if not reply:
        return None

    bot_user = ensure_ai_bot_user(db)
    parent_id = cast(UUID | None, comment.get("id"))
    try:
        return create_post_comment(db, post_id=cast(UUID, post.id), author=bot_user, content=reply, parent_id=parent_id)
    except Exception:
        logger.exception("Failed to persist AI reply for comment mention")
        return None


__all__ = [
    "respond_to_ai_mention_in_post",
    "respond_to_ai_mention_in_comment",
    "set_ai_mention_llm_client",
]
