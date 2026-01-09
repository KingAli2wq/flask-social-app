"""System-level routes for diagnostics and emotion testing."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field
from starlette.responses import JSONResponse

from ..services.app_lock_service import (
    create_app_lock_token,
    is_app_lock_enabled,
    is_unlocked_from_cookie,
    lock_cookie_name,
    verify_app_lock_password,
)
from ..services.emotion_service import build_emotion_directive, detect_emotions

router = APIRouter(prefix="/system", tags=["system"])


class EmotionProbeRequest(BaseModel):
    text: str = Field(..., description="Content to analyse for dominant emotions")
    top_k: int = Field(3, ge=1, le=6, description="Number of emotions to return")
    min_score: float | None = Field(None, ge=0, le=1, description="Optional minimum confidence filter")


class EmotionPredictionSchema(BaseModel):
    label: str
    score: float


class EmotionProbeResponse(BaseModel):
    text: str
    predictions: list[EmotionPredictionSchema]
    directive: str | None


class AppLockStatusResponse(BaseModel):
    enabled: bool
    unlocked: bool


class AppLockUnlockRequest(BaseModel):
    password: str = Field(..., min_length=1)


@router.post("/test-emotions", response_model=EmotionProbeResponse)
def test_emotions(payload: EmotionProbeRequest) -> EmotionProbeResponse:
    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Text cannot be empty")

    predictions = detect_emotions(text, top_k=payload.top_k, min_score=payload.min_score)
    directive = build_emotion_directive(predictions)
    serialized = [EmotionPredictionSchema(label=item.label, score=item.score) for item in predictions]
    return EmotionProbeResponse(text=text, predictions=serialized, directive=directive)


@router.get("/app-lock/status", response_model=AppLockStatusResponse)
def app_lock_status(request: Request) -> AppLockStatusResponse:
    enabled = is_app_lock_enabled()
    if not enabled:
        return AppLockStatusResponse(enabled=False, unlocked=True)

    token = request.cookies.get(lock_cookie_name())
    return AppLockStatusResponse(enabled=True, unlocked=is_unlocked_from_cookie(token))


@router.post("/app-lock/unlock", response_model=AppLockStatusResponse)
def app_lock_unlock(payload: AppLockUnlockRequest, request: Request) -> JSONResponse:
    enabled = is_app_lock_enabled()
    if not enabled:
        return JSONResponse(status_code=status.HTTP_200_OK, content=AppLockStatusResponse(enabled=False, unlocked=True).model_dump())

    if not verify_app_lock_password(payload.password):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content=AppLockStatusResponse(enabled=True, unlocked=False).model_dump(),
        )

    token = create_app_lock_token()
    response = JSONResponse(status_code=status.HTTP_200_OK, content=AppLockStatusResponse(enabled=True, unlocked=True).model_dump())
    response.set_cookie(
        lock_cookie_name(),
        token,
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https",
        path="/",
    )
    return response


__all__ = ["router"]