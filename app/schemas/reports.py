"""Schemas for user reports."""
from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


ReportTargetType = Literal["post", "message", "user"]
ReportStatus = Literal["open", "resolved"]


class ReportCreateRequest(BaseModel):
    target_type: ReportTargetType
    target_id: UUID
    reason: str = Field(min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=1000)


class ReportCreateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: str
    created_at: datetime


class ModerationReportSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: str
    created_at: datetime

    target_type: str
    target_id: UUID
    target_user_id: UUID | None = None

    reporter_id: UUID
    reporter_username: str | None = None

    reason: str
    description: str | None = None


class ModerationReportList(BaseModel):
    total: int
    items: list[ModerationReportSummary]


class ModerationReportResolveRequest(BaseModel):
    action_taken: str | None = Field(default=None, max_length=64)


__all__ = [
    "ReportTargetType",
    "ReportStatus",
    "ReportCreateRequest",
    "ReportCreateResponse",
    "ModerationReportSummary",
    "ModerationReportList",
    "ModerationReportResolveRequest",
]
