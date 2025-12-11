"""HTTP endpoints for the AI chatbot sandbox."""
from __future__ import annotations

import logging
from time import perf_counter
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..database import get_session
from ..models import User
from ..schemas.chatbot import (
    ChatbotMessagePayload,
    ChatbotPromptRequest,
    ChatbotSessionCreateRequest,
    ChatbotSessionResponse,
    ChatbotSessionSummary,
)
from ..services import (
    ChatbotTranscript,
    create_chatbot_session,
    delete_chatbot_session,
    get_chatbot_transcript,
    get_current_user,
    list_chatbot_sessions,
    send_chat_prompt,
    stream_chat_prompt,
    warmup_social_ai_model,
)

router = APIRouter(prefix="/chatbot", tags=["chatbot"])
logger = logging.getLogger(__name__)


def _schedule_social_ai_warmup(background_tasks: BackgroundTasks) -> None:
    """Best-effort helper so warmup failures never break session creation."""

    try:
        background_tasks.add_task(warmup_social_ai_model)
    except Exception:  # pragma: no cover - defensive guard
        logger.warning("Unable to enqueue Social AI warmup task", exc_info=True)


def _to_message_payload(transcript: ChatbotTranscript) -> list[ChatbotMessagePayload]:
    return [
        ChatbotMessagePayload(
            id=message.id,
            session_id=message.session_id,
            role=message.role,
            content=message.content,
            model=message.model,
            created_at=message.created_at,
        )
        for message in transcript.messages
    ]


def _to_session_response(transcript: ChatbotTranscript) -> ChatbotSessionResponse:
    session = transcript.session
    return ChatbotSessionResponse(
        session_id=session.id,
        persona=session.persona,
        title=session.title,
        updated_at=session.updated_at,
        status=session.status,
        messages=_to_message_payload(transcript),
    )


def _handle_prompt(
    payload: ChatbotPromptRequest,
    *,
    current_user: User,
    db: Session,
) -> ChatbotSessionResponse:
    transcript = send_chat_prompt(
        db,
        user=current_user,
        message=payload.message,
        session_id=payload.session_id,
        persona=payload.persona,
        title=payload.title,
        include_public_context=payload.include_public_context,
    )
    return _to_session_response(transcript)


@router.post("/messages", response_model=ChatbotSessionResponse)
def create_chat_message(
    payload: ChatbotPromptRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> ChatbotSessionResponse:
    return _handle_prompt(payload, current_user=current_user, db=db)


@router.post("/messages/stream")
async def create_chat_message_stream(
    payload: ChatbotPromptRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> StreamingResponse:
    """Stream Social AI output as UTF-8 chunks so the UI can show incremental typing."""
    start = perf_counter()
    meta = {
        "user_id": str(current_user.id),
        "session_id": str(payload.session_id or ""),
        "persona": payload.persona,
    }
    logger.info("Social AI stream start | user=%s session=%s", meta["user_id"], meta["session_id"])
    stream = await stream_chat_prompt(
        db,
        user=current_user,
        message=payload.message,
        session_id=payload.session_id,
        persona=payload.persona,
        title=payload.title,
        include_public_context=payload.include_public_context,
    )

    async def _instrumented_stream():
        chunk_count = 0
        first_chunk_logged = False
        try:
            async for chunk in stream:
                if not first_chunk_logged:
                    first_chunk_logged = True
                    first_latency = (perf_counter() - start) * 1000
                    logger.info(
                        "Social AI stream first chunk | user=%s session=%s latency_ms=%.1f",
                        meta["user_id"],
                        meta["session_id"],
                        first_latency,
                    )
                chunk_count += 1
                yield chunk
        except Exception:
            logger.exception(
                "Social AI stream failed | user=%s session=%s chunks=%s",
                meta["user_id"],
                meta["session_id"],
                chunk_count,
            )
            raise
        finally:
            total_duration = (perf_counter() - start) * 1000
            logger.info(
                "Social AI stream finished | user=%s session=%s chunks=%s duration_ms=%.1f",
                meta["user_id"],
                meta["session_id"],
                chunk_count,
                total_duration,
            )

    # Plain text chunks keep the client-side parser simple; the final chunk may include
    # a "[Stream error: …]" marker if generation fails mid-response.
    return StreamingResponse(_instrumented_stream(), media_type="text/plain")


@router.post("/test", response_model=ChatbotSessionResponse)
def run_test_chat(
    payload: ChatbotPromptRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> ChatbotSessionResponse:
    return _handle_prompt(payload, current_user=current_user, db=db)


@router.get("/sessions", response_model=list[ChatbotSessionSummary])
def list_sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> list[ChatbotSessionSummary]:
    start = perf_counter()
    try:
        summaries = list_chatbot_sessions(db, user=current_user)
        response = [
            ChatbotSessionSummary(
                session_id=item.session_id,
                title=item.title,
                persona=item.persona,
                status=item.status,
                updated_at=item.updated_at,
                last_message_preview=item.last_message_preview,
            )
            for item in summaries
        ]
        duration = (perf_counter() - start) * 1000
        logger.info(
            "Social AI sessions list success | user=%s count=%s duration_ms=%.1f",
            current_user.id,
            len(response),
            duration,
        )
        return response
    except Exception:
        duration = (perf_counter() - start) * 1000
        logger.exception(
            "Social AI sessions list failed | user=%s duration_ms=%.1f",
            current_user.id,
            duration,
        )
        raise


@router.get("/sessions/{session_id}", response_model=ChatbotSessionResponse)
def get_session_detail(
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> ChatbotSessionResponse:
    start = perf_counter()
    try:
        transcript = get_chatbot_transcript(db, user=current_user, session_id=session_id)
        response = _to_session_response(transcript)
        duration = (perf_counter() - start) * 1000
        logger.info(
            "Social AI transcript success | user=%s session=%s duration_ms=%.1f",
            current_user.id,
            session_id,
            duration,
        )
        return response
    except Exception:
        duration = (perf_counter() - start) * 1000
        logger.exception(
            "Social AI transcript failed | user=%s session=%s duration_ms=%.1f",
            current_user.id,
            session_id,
            duration,
        )
        raise


@router.post("/sessions", response_model=ChatbotSessionResponse, status_code=status.HTTP_201_CREATED)
def create_session(
    payload: ChatbotSessionCreateRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> ChatbotSessionResponse:
    start = perf_counter()
    try:
        transcript = create_chatbot_session(db, user=current_user, persona=payload.persona, title=payload.title)
    except Exception:
        duration = (perf_counter() - start) * 1000
        logger.exception(
            "Social AI session create failed | user=%s duration_ms=%.1f",
            current_user.id,
            duration,
        )
        raise

    response = _to_session_response(transcript)
    duration = (perf_counter() - start) * 1000
    logger.info(
        "Social AI session create success | user=%s session=%s duration_ms=%.1f",
        current_user.id,
        response.session_id,
        duration,
    )
    _schedule_social_ai_warmup(background_tasks)
    return response


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> None:
    delete_chatbot_session(db, user=current_user, session_id=session_id)


__all__ = ["router"]
