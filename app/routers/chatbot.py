"""HTTP endpoints for the AI chatbot sandbox."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status
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
)

router = APIRouter(prefix="/chatbot", tags=["chatbot"])


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

    stream = await stream_chat_prompt(
        db,
        user=current_user,
        message=payload.message,
        session_id=payload.session_id,
        persona=payload.persona,
        title=payload.title,
        include_public_context=payload.include_public_context,
    )
    # Plain text chunks keep the client-side parser simple; the final chunk may include
    # a "[Stream error: …]" marker if generation fails mid-response.
    return StreamingResponse(stream, media_type="text/plain")


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
    summaries = list_chatbot_sessions(db, user=current_user)
    return [
        ChatbotSessionSummary(
            session_id=item.session_id,
            title=item.title,
            persona=item.persona,
            updated_at=item.updated_at,
            last_message_preview=item.last_message_preview,
        )
        for item in summaries
    ]


@router.get("/sessions/{session_id}", response_model=ChatbotSessionResponse)
def get_session_detail(
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> ChatbotSessionResponse:
    transcript = get_chatbot_transcript(db, user=current_user, session_id=session_id)
    return _to_session_response(transcript)


@router.post("/sessions", response_model=ChatbotSessionResponse, status_code=status.HTTP_201_CREATED)
def create_session(
    payload: ChatbotSessionCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> ChatbotSessionResponse:
    transcript = create_chatbot_session(db, user=current_user, persona=payload.persona, title=payload.title)
    return _to_session_response(transcript)


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> None:
    delete_chatbot_session(db, user=current_user, session_id=session_id)


__all__ = ["router"]
