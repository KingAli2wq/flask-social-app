"""Moderation-focused API endpoints."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from ..database import get_session
from ..models import User
from ..schemas import (
    ModerationDashboardResponse,
    ModerationRoleUpdateRequest,
    ModerationUserSummary,
)
from ..services import (
    delete_post_record,
    load_moderation_dashboard,
    require_owner,
    require_roles,
    update_user_role,
)

router = APIRouter(prefix="/moderation", tags=["moderation"])


@router.get("/dashboard", response_model=ModerationDashboardResponse)
async def moderation_dashboard_endpoint(
    db: Session = Depends(get_session),
    current_user: User = Depends(require_roles("owner", "admin")),
) -> ModerationDashboardResponse:
    return load_moderation_dashboard(db)


@router.patch("/users/{user_id}/role", response_model=ModerationUserSummary)
async def moderation_update_role_endpoint(
    user_id: UUID,
    payload: ModerationRoleUpdateRequest,
    db: Session = Depends(get_session),
    current_user: User = Depends(require_owner()),
) -> ModerationUserSummary:
    return update_user_role(db, actor=current_user, target_user_id=user_id, new_role=payload.role)


@router.delete("/posts/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def moderation_delete_post_endpoint(
    post_id: UUID,
    db: Session = Depends(get_session),
    current_user: User = Depends(require_roles("owner", "admin")),
) -> None:
    delete_post_record(
        db,
        post_id=post_id,
        requester_id=current_user.id,
        requester_role=getattr(current_user, "role", None),
        delete_media=True,
    )


__all__ = ["router"]
