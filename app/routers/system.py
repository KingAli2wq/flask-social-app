"""System-level routes for diagnostics and emotion testing."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
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


@router.post("/test-emotions", response_model=EmotionProbeResponse)
def test_emotions(payload: EmotionProbeRequest) -> EmotionProbeResponse:
    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Text cannot be empty")

    predictions = detect_emotions(text, top_k=payload.top_k, min_score=payload.min_score)
    directive = build_emotion_directive(predictions)
    serialized = [EmotionPredictionSchema(label=item.label, score=item.score) for item in predictions]
    return EmotionProbeResponse(text=text, predictions=serialized, directive=directive)


__all__ = ["router"]