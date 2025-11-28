"""Lightweight SMTP helper for transactional emails."""
from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from ..config import get_settings

logger = logging.getLogger(__name__)


class EmailDeliveryError(RuntimeError):
    """Raised when the SMTP transport fails."""


def _smtp_enabled() -> bool:
    settings = get_settings()
    return bool(
        settings.email_host
        and settings.email_from_address
    )


def send_email(to_address: str, subject: str, body: str) -> bool:
    """Send a plaintext email if SMTP settings are configured.

    Returns ``True`` when the email was successfully queued, ``False`` when
    delivery is skipped due to missing configuration or recipient address.
    Raises ``EmailDeliveryError`` when the SMTP transport fails mid-flight.
    """

    if not to_address or not subject or not body:
        logger.debug("Email delivery skipped: incomplete payload (to=%s)", to_address)
        return False

    if not _smtp_enabled():
        logger.info("Email delivery skipped: SMTP disabled")
        return False

    settings = get_settings()
    host = settings.email_host
    from_address = settings.email_from_address
    if not host or not from_address:
        logger.debug("Email delivery skipped: incomplete SMTP config (host or from)")
        return False

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = from_address
    message["To"] = to_address
    message.set_content(body)

    try:
        with smtplib.SMTP(host, settings.email_port, timeout=20) as smtp:
            if settings.email_use_tls:
                smtp.starttls()
            if settings.email_username and settings.email_password:
                smtp.login(settings.email_username, settings.email_password)
            smtp.send_message(message)
    except Exception as exc:  # pragma: no cover - network interactions
        logger.exception("Failed to send email to %s", to_address)
        raise EmailDeliveryError(str(exc)) from exc

    return True


__all__ = ["send_email", "EmailDeliveryError"]
