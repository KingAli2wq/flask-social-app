"""Mailgun webhooks for inbound support email."""
from __future__ import annotations

import hashlib
import hmac
import logging
import os

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.support import SupportTicket

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks/mailgun", tags=["mailgun"])


def verify_mailgun_signature(timestamp: str | None, token: str | None, signature: str | None, signing_key: str) -> bool:
    if not timestamp or not token or not signature:
        return False
    message = f"{timestamp}{token}".encode("utf-8")
    digest = hmac.new(signing_key.encode("utf-8"), msg=message, digestmod=hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, signature)


def _get_form_text(form, key: str) -> str | None:
    value = form.get(key)
    if value is None or isinstance(value, UploadFile):
        return None
    return str(value)


@router.post("/support", response_class=PlainTextResponse)
async def support_webhook(request: Request, db: Session = Depends(get_db)) -> PlainTextResponse:
    form = await request.form()
    timestamp = _get_form_text(form, "timestamp")
    token = _get_form_text(form, "token")
    signature = _get_form_text(form, "signature")

    signing_key = os.getenv("MAILGUN_SIGNING_KEY")
    if not signing_key:
        logger.error("MAILGUN_SIGNING_KEY is not configured")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Mailgun signing disabled")

    if not verify_mailgun_signature(timestamp, token, signature, signing_key):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid Mailgun signature")

    sender = _get_form_text(form, "sender") or _get_form_text(form, "from")
    recipient = _get_form_text(form, "recipient")
    subject = (_get_form_text(form, "subject") or "").strip() or "(no subject)"
    body_text = _get_form_text(form, "stripped-text") or _get_form_text(form, "body-plain") or ""
    body_html = _get_form_text(form, "body-html") or None

    if not sender or not recipient:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing sender or recipient")

    ticket = SupportTicket(
        from_address=str(sender),
        to_address=str(recipient),
        subject=str(subject),
        body=str(body_text),
        body_html=str(body_html) if body_html is not None else None,
        status="open",
    )

    db.add(ticket)
    try:
        db.commit()
    except Exception:  # pragma: no cover - defensive logging
        db.rollback()
        logger.exception("Failed to persist support ticket from %s", sender)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unable to store ticket")

    logger.info("Created support ticket %s from %s subject=%s", ticket.id, sender, subject)
    return PlainTextResponse("OK")


__all__ = ["router", "verify_mailgun_signature"]
