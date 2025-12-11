"""Schemas for AI-generated post endpoints."""
from __future__ import annotations

from pydantic import BaseModel, Field


class AIGeneratePostRequest(BaseModel):
    max_context_posts: int = Field(12, ge=1, le=50)
    lookback_hours: int = Field(72, ge=1, le=720)
    temperature: float | None = Field(None, ge=0.0, le=1.0)


__all__ = ["AIGeneratePostRequest"]
