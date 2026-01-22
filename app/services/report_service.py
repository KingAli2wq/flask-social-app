"""Services for creating and reviewing user reports."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from typing import cast
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session, aliased

from ..models import Message, Post, Report, User

ReportTargetType = Literal["post", "message", "user"]


def create_report(
    db: Session,
    *,
    reporter: User,
    target_type: ReportTargetType,
    target_id: UUID,
    reason: str,
    description: str | None,
) -> Report:
    safe_reason = (reason or "").strip()
    safe_description = (description or "").strip() if description else None
    if len(safe_reason) < 2:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Reason is required")

    target_user_id: UUID | None = None
    if target_type == "user":
        target_user = db.get(User, target_id)
        if not target_user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        target_user_id = cast(UUID, target_user.id)
    elif target_type == "post":
        post = db.get(Post, target_id)
        if not post:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
        target_user_id = cast(UUID, post.user_id)
    elif target_type == "message":
        message = db.get(Message, target_id)
        if not message:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
        target_user_id = cast(UUID, message.sender_id)
    else:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid report target")

    existing = (
        db.query(Report)
        .filter(
            Report.reporter_id == reporter.id,
            Report.target_type == target_type,
            Report.target_id == target_id,
            Report.status == "open",
        )
        .first()
    )
    if existing is not None:
        setattr(existing, "reason", safe_reason)
        setattr(existing, "description", safe_description)
        db.add(existing)
        db.commit()
        db.refresh(existing)
        return existing

    report = Report(
        reporter_id=reporter.id,
        target_type=target_type,
        target_id=target_id,
        target_user_id=target_user_id,
        reason=safe_reason,
        description=safe_description,
        status="open",
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


def list_reports(
    db: Session,
    *,
    skip: int = 0,
    limit: int = 25,
    search: str | None = None,
    status_filter: str | None = "open",
) -> tuple[int, list[dict]]:
    safe_skip = max(0, int(skip or 0))
    safe_limit = max(1, min(int(limit or 25), 100))

    reporter_alias = aliased(User)

    query = (
        db.query(
            Report,
            reporter_alias.username.label("reporter_username"),
        )
        .join(reporter_alias, Report.reporter_id == reporter_alias.id)
    )

    if status_filter:
        query = query.filter(Report.status == status_filter)

    if search:
        pattern = f"%{search.lower()}%"
        query = query.filter(
            func.lower(Report.reason).like(pattern)
            | func.lower(Report.description).like(pattern)
            | func.lower(reporter_alias.username).like(pattern)
        )

    total = int(query.with_entities(func.count(Report.id)).scalar() or 0)

    rows = (
        query.order_by(Report.created_at.desc())
        .offset(safe_skip)
        .limit(safe_limit)
        .all()
    )

    items: list[dict] = []
    for report, reporter_username in rows:
        items.append(
            {
                "id": report.id,
                "status": report.status,
                "created_at": report.created_at,
                "target_type": report.target_type,
                "target_id": report.target_id,
                "target_user_id": report.target_user_id,
                "reporter_id": report.reporter_id,
                "reporter_username": reporter_username,
                "reason": report.reason,
                "description": report.description,
            }
        )

    return total, items


def get_report_summary(db: Session, *, report_id: UUID) -> dict:
    reporter_alias = aliased(User)
    row = (
        db.query(
            Report,
            reporter_alias.username.label("reporter_username"),
        )
        .join(reporter_alias, Report.reporter_id == reporter_alias.id)
        .filter(Report.id == report_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    report, reporter_username = row
    return {
        "id": report.id,
        "status": report.status,
        "created_at": report.created_at,
        "target_type": report.target_type,
        "target_id": report.target_id,
        "target_user_id": report.target_user_id,
        "reporter_id": report.reporter_id,
        "reporter_username": reporter_username,
        "reason": report.reason,
        "description": report.description,
    }


def resolve_report(db: Session, *, report_id: UUID, actor: User, action_taken: str | None = None) -> Report:
    report = db.get(Report, report_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    setattr(report, "status", "resolved")
    setattr(report, "resolved_at", datetime.now(timezone.utc))
    setattr(report, "resolved_by", cast(UUID, actor.id))
    setattr(report, "action_taken", (action_taken or "").strip() or None)

    db.add(report)
    db.commit()
    db.refresh(report)
    return report


__all__ = ["create_report", "list_reports", "get_report_summary", "resolve_report"]
