"""Domain helpers for the AI chatbot experience."""
from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Final, List, Protocol, Sequence, cast
from uuid import UUID

from fastapi import HTTPException, status
import httpx
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..models import AiChatMessage, AiChatSession, Post, Story, User
from ..security.data_vault import DataVaultError, decrypt_text, encrypt_text
from .safety import enforce_safe_text

BACKEND_BASE_URL = os.getenv("BACKEND_BASE_URL", "http://localhost:8080").rstrip("/")
AI_CHAT_URL = f"{BACKEND_BASE_URL}/ai/chat"
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "120"))

logger = logging.getLogger(__name__)

_DEFAULT_SYSTEM_PROMPT = (
    "You are SocialSphere, an in-app AI companion. Offer concise, friendly answers, "
    "reference public posts or stories when helpful, and guide users toward positive community interactions."
)
_MAX_HISTORY = 15
_RESPONSE_HISTORY = 40
_DEFAULT_PERSONA: Final[str] = "default"
_PERSONA_ALIASES: Final[dict[str, str]] = {
    "deep-understanding": "deep",
    "deep_understanding": "deep",
    "deepunderstanding": "deep",
}
_PERSONA_PROMPTS: Final[dict[str, str]] = {
    "default": _DEFAULT_SYSTEM_PROMPT,
    "freaky": (
        "You are SocialSphere in Freaky mode. Stay encouraging and safe, but deliver playful, unexpected takes, "
        "bold metaphors, and surprising icebreakers that spark creative conversations."
    ),
    "deep": (
        "You are SocialSphere in Deep Understanding mode. Offer thoughtful, well-structured guidance, "
        "reflect user intent, and surface follow-up questions that help them reason carefully."
    ),
}


def _normalize_persona_key(value: str | None) -> str:
    if not value:
        return _DEFAULT_PERSONA
    token = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    if not token:
        return _DEFAULT_PERSONA
    token = _PERSONA_ALIASES.get(token, token)
    if token not in _PERSONA_PROMPTS:
        return _DEFAULT_PERSONA
    return token


def _resolve_persona(persona: str | None) -> tuple[str, str]:
    key = _normalize_persona_key(persona)
    prompt = _PERSONA_PROMPTS.get(key, _PERSONA_PROMPTS[_DEFAULT_PERSONA])
    return key, prompt


@dataclass(slots=True)
class ChatCompletionResult:
    content: str
    prompt_tokens: int
    completion_tokens: int
    model: str


class LLMClient(Protocol):
    def complete(self, *, messages: Sequence[dict[str, str]], temperature: float = 0.2) -> ChatCompletionResult:
        """Return a completion from the underlying model."""
        ...


class SocialAIChatClient(LLMClient):
    """HTTP client that proxies chatbot requests through the internal /ai/chat endpoint."""

    def __init__(self, *, endpoint: str | None = None) -> None:
        self._endpoint = (endpoint or AI_CHAT_URL).rstrip("/")
        self._client = httpx.Client(timeout=OLLAMA_TIMEOUT)

    def complete(self, *, messages: Sequence[dict[str, str]], temperature: float = 0.2) -> ChatCompletionResult:
        if not messages:
            raise ChatbotServiceError("No messages provided")

        latest_user = next((msg for msg in reversed(messages) if msg.get("role") == "user"), None)
        if latest_user is None:
            raise ChatbotServiceError("No user message found in messages")

        user_message = cast(str, latest_user.get("content") or "").strip()
        if not user_message:
            raise ChatbotServiceError("User message was empty")

        history: list[dict[str, str]] = []
        for msg in messages:
            if msg is latest_user:
                continue
            role = msg.get("role")
            content = (msg.get("content") or "").strip()
            if role in {"user", "assistant"} and content:
                history.append({"role": cast(str, role), "content": content})

        payload = {
            "message": user_message,
            "mode": "default",
            "history": history,
            "confirmed_adult": False,
        }

        try:
            response = self._client.post(self._endpoint, json=payload)
            response.raise_for_status()
        except httpx.ReadTimeout as exc:  # pragma: no cover - timeout path
            logger.error(
                "SocialAIChatClient timeout | endpoint=%s timeout=%s error=%s",
                self._endpoint,
                OLLAMA_TIMEOUT,
                type(exc).__name__,
            )
            raise ChatbotServiceError("Local LLM request timed out") from exc
        except httpx.TimeoutException as exc:  # pragma: no cover - timeout path
            logger.error(
                "SocialAIChatClient timeout | endpoint=%s timeout=%s error=%s",
                self._endpoint,
                OLLAMA_TIMEOUT,
                type(exc).__name__,
            )
            raise ChatbotServiceError("Local LLM request timed out") from exc
        except httpx.HTTPStatusError as exc:  # pragma: no cover - status path
            status = exc.response.status_code if exc.response is not None else "unknown"
            logger.error(
                "SocialAIChatClient HTTP status error | endpoint=%s status=%s timeout=%s",
                self._endpoint,
                status,
                OLLAMA_TIMEOUT,
            )
            raise ChatbotServiceError("Social AI request failed") from exc
        except httpx.HTTPError as exc:  # pragma: no cover - network failure path
            logger.error(
                "SocialAIChatClient transport error | endpoint=%s timeout=%s error=%s",
                self._endpoint,
                OLLAMA_TIMEOUT,
                type(exc).__name__,
            )
            raise ChatbotServiceError("Social AI request failed") from exc

        try:
            data = cast(dict[str, Any], response.json())
        except ValueError as exc:
            raise ChatbotServiceError("Social AI response was not valid JSON") from exc

        reply = data.get("reply")
        if not isinstance(reply, str):
            raise ChatbotServiceError("Invalid AI response format")

        return ChatCompletionResult(content=reply, prompt_tokens=0, completion_tokens=0, model="social-ai-local")


@dataclass(slots=True)
class ChatbotMessageDTO:
    id: UUID
    session_id: UUID
    role: str
    content: str
    model: str | None
    created_at: datetime


@dataclass(slots=True)
class ChatbotTranscript:
    session: AiChatSession
    messages: List[ChatbotMessageDTO]


@dataclass(slots=True)
class ChatbotSessionSummaryDTO:
    session_id: UUID
    title: str | None
    persona: str
    updated_at: datetime
    last_message_preview: str | None


class ChatbotServiceError(RuntimeError):
    """Raised when chatbot generation fails."""


_llm_client: LLMClient | None = None


def set_llm_client(client: LLMClient | None) -> None:
    """Override the global LLM client (used by tests)."""

    global _llm_client
    _llm_client = client


def _get_llm_client() -> LLMClient:
    global _llm_client
    if _llm_client is None:
        _llm_client = SocialAIChatClient()
    return _llm_client


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _encrypt(message: str) -> str:
    try:
        return encrypt_text(message)
    except DataVaultError as exc:
        raise ChatbotServiceError("Unable to protect chatbot message") from exc


def _decrypt(value: str | None) -> str:
    if not value:
        return ""
    try:
        return decrypt_text(value)
    except DataVaultError:
        return ""


def _ensure_session(
    db: Session,
    *,
    user: User,
    session_id: UUID | None,
    persona: str | None,
    title: str | None,
) -> AiChatSession:
    requested_persona, requested_prompt = _resolve_persona(persona)
    cleaned_title = (title or "").strip() or None
    if session_id is not None:
        session = db.get(AiChatSession, session_id)
        if session is None or cast(UUID, session.user_id) != user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found")
        if persona:
            target_persona, target_prompt = requested_persona, requested_prompt
        else:
            target_persona, target_prompt = _resolve_persona(cast(str | None, session.persona))
        if cast(str | None, session.persona) != target_persona:
            setattr(session, "persona", target_persona)
        if cast(str | None, session.system_prompt) != target_prompt:
            setattr(session, "system_prompt", target_prompt)
        if cleaned_title and not cast(str | None, session.title):
            setattr(session, "title", cleaned_title)
        return session

    session = AiChatSession(
        user_id=user.id,
        persona=requested_persona,
        title=cleaned_title,
        system_prompt=requested_prompt,
    )
    db.add(session)
    db.flush()
    return session


def _load_recent_messages(db: Session, session_id: UUID, *, limit: int) -> list[AiChatMessage]:
    stmt = (
        select(AiChatMessage)
        .where(AiChatMessage.session_id == session_id)
        .order_by(AiChatMessage.created_at.desc(), AiChatMessage.id.desc())
        .limit(limit)
    )
    rows = list(db.scalars(stmt))
    rows.reverse()
    return rows


def _serialize_messages(messages: Sequence[AiChatMessage]) -> list[ChatbotMessageDTO]:
    return [
        ChatbotMessageDTO(
            id=cast(UUID, msg.id),
            session_id=cast(UUID, msg.session_id),
            role=cast(str, msg.sender_role),
            content=_decrypt(cast(str | None, msg.content_ciphertext)),
            model=cast(str | None, msg.model),
            created_at=cast(datetime, msg.created_at),
        )
        for msg in messages
    ]


def _summarize_posts(db: Session, *, limit: int = 5) -> list[str]:
    stmt = (
        select(Post, User.username)
        .join(User, Post.user_id == User.id)
        .order_by(Post.created_at.desc())
        .limit(limit)
    )
    summaries: list[str] = []
    for post, username in db.execute(stmt):
        caption = (post.caption or "").strip()
        snippet = caption[:200].replace("\n", " ") if caption else "(no caption)"
        summaries.append(f"Post by @{username}: {snippet}")
    return summaries


def _summarize_stories(db: Session, *, limit: int = 5) -> list[str]:
    stmt = (
        select(Story, User.username)
        .join(User, Story.user_id == User.id)
        .order_by(Story.created_at.desc())
        .limit(limit)
    )
    summaries: list[str] = []
    for story, username in db.execute(stmt):
        overlay = (story.text_overlay or "").strip() or "visual story"
        summaries.append(f"Story by @{username}: {overlay}")
    return summaries


def _build_context_blob(db: Session, *, user: User, include_public_context: bool) -> str:
    lines = [
        f"Current user profile: @{user.username} | display={user.display_name or 'n/a'} | bio={(user.bio or 'n/a')}",
    ]
    if include_public_context:
        posts = _summarize_posts(db)
        stories = _summarize_stories(db)
        if posts:
            lines.append("Recent posts:\n- " + "\n- ".join(posts))
        if stories:
            lines.append("Recent stories:\n- " + "\n- ".join(stories))
    return "\n\n".join(lines)


def _prepare_llm_messages(
    *,
    session: AiChatSession,
    history: Sequence[AiChatMessage],
    context_blob: str,
) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    system_prompt = cast(str | None, session.system_prompt) or _DEFAULT_SYSTEM_PROMPT
    if context_blob:
        system_prompt = f"{system_prompt}\n\nContext:\n{context_blob}"
    messages.append({"role": "system", "content": system_prompt})
    for message in history[-_MAX_HISTORY:]:
        content = _decrypt(cast(str | None, message.content_ciphertext))
        if not content:
            continue
        role = cast(str, message.sender_role)
        messages.append({"role": role, "content": content})
    return messages


def _persist_message(
    db: Session,
    *,
    session_id: UUID,
    role: str,
    content: str,
    model: str | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
) -> AiChatMessage:
    message = AiChatMessage(
        session_id=session_id,
        sender_role=role,
        content_ciphertext=_encrypt(content),
        model=model,
        token_count_prompt=prompt_tokens,
        token_count_completion=completion_tokens,
    )
    db.add(message)
    db.flush()
    return message
def send_chat_prompt(
    db: Session,
    *,
    user: User,
    message: str,
    session_id: UUID | None,
    persona: str | None,
    title: str | None,
    include_public_context: bool,
) -> ChatbotTranscript:
    cleaned_message = (message or "").strip()
    if not cleaned_message:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Message cannot be empty")
    enforce_safe_text(cleaned_message, field_name="message")
    session = _ensure_session(db, user=user, session_id=session_id, persona=persona, title=title)
    session_identifier = cast(UUID, session.id)
    _persist_message(db, session_id=session_identifier, role="user", content=cleaned_message)

    history = _load_recent_messages(db, session_identifier, limit=_MAX_HISTORY)
    context_blob = _build_context_blob(db, user=user, include_public_context=include_public_context)
    llm_messages = _prepare_llm_messages(session=session, history=history, context_blob=context_blob)
    result = _get_llm_client().complete(messages=llm_messages)
    _persist_message(
        db,
        session_id=session_identifier,
        role="assistant",
        content=result.content,
        model=result.model,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
    )

    timestamp = _now()
    setattr(session, "last_message_at", timestamp)
    setattr(session, "updated_at", timestamp)

    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise ChatbotServiceError("Failed to save chatbot exchange") from exc

    messages = _load_recent_messages(db, session_identifier, limit=_RESPONSE_HISTORY)
    return ChatbotTranscript(session=session, messages=_serialize_messages(messages))


def get_chatbot_transcript(
    db: Session,
    *,
    user: User,
    session_id: UUID,
) -> ChatbotTranscript:
    session = db.get(AiChatSession, session_id)
    if session is None or cast(UUID, session.user_id) != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found")
    messages = _load_recent_messages(db, cast(UUID, session.id), limit=_RESPONSE_HISTORY)
    return ChatbotTranscript(session=session, messages=_serialize_messages(messages))


def list_chatbot_sessions(db: Session, *, user: User) -> list[ChatbotSessionSummaryDTO]:
    stmt = (
        select(AiChatSession)
        .where(AiChatSession.user_id == user.id)
        .order_by(AiChatSession.updated_at.desc())
    )
    sessions = list(db.scalars(stmt))
    summaries: list[ChatbotSessionSummaryDTO] = []
    for session in sessions:
        preview_stmt = (
            select(AiChatMessage)
            .where(AiChatMessage.session_id == session.id)
            .order_by(AiChatMessage.created_at.desc(), AiChatMessage.id.desc())
            .limit(1)
        )
        preview_row = db.scalar(preview_stmt)
        preview_text = _decrypt(cast(str | None, getattr(preview_row, "content_ciphertext", None))) if preview_row else None
        summaries.append(
            ChatbotSessionSummaryDTO(
                session_id=cast(UUID, session.id),
                title=cast(str | None, session.title),
                persona=cast(str, session.persona),
                updated_at=cast(datetime, session.updated_at),
                last_message_preview=(preview_text[:160] if preview_text else None),
            )
        )
    return summaries


def create_chatbot_session(
    db: Session,
    *,
    user: User,
    persona: str | None,
    title: str | None,
) -> ChatbotTranscript:
    session = _ensure_session(db, user=user, session_id=None, persona=persona, title=title)
    timestamp = _now()
    setattr(session, "last_message_at", timestamp)
    setattr(session, "updated_at", timestamp)
    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise ChatbotServiceError("Failed to create chatbot session") from exc
    return ChatbotTranscript(session=session, messages=[])


def delete_chatbot_session(
    db: Session,
    *,
    user: User,
    session_id: UUID,
) -> None:
    session = db.get(AiChatSession, session_id)
    if session is None or cast(UUID, session.user_id) != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found")
    try:
        db.delete(session)
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise ChatbotServiceError("Failed to delete chatbot session") from exc


__all__ = [
    "ChatbotServiceError",
    "ChatbotMessageDTO",
    "ChatbotTranscript",
    "ChatbotSessionSummaryDTO",
    "send_chat_prompt",
    "list_chatbot_sessions",
    "get_chatbot_transcript",
    "create_chatbot_session",
    "delete_chatbot_session",
    "set_llm_client",
]
