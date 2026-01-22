"""Report submission endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from ..database import get_session
from ..models import User
from ..schemas.reports import ReportCreateRequest, ReportCreateResponse
from ..services import get_current_user
from ..services.report_service import create_report

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("", response_model=ReportCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_report_endpoint(
    payload: ReportCreateRequest,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ReportCreateResponse:
    report = create_report(
        db,
        reporter=current_user,
        target_type=payload.target_type,
        target_id=payload.target_id,
        reason=payload.reason,
        description=payload.description,
    )
    return ReportCreateResponse.model_validate(report)


__all__ = ["router"]
