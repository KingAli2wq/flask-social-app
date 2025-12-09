"""Lightweight SMTP helper for transactional emails."""
from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

import requests

from ..config import get_settings
from ..security.secrets import MissingSecretError, is_placeholder, require_secret

logger = logging.getLogger(__name__)


class EmailDeliveryError(RuntimeError):
    """Raised when the SMTP transport fails."""


def _resolve_email_password() -> str:
    try:
        return require_secret("EMAIL_PASSWORD")
    except MissingSecretError as exc:
        raise EmailDeliveryError(str(exc)) from exc


def _resolve_mailgun_api_key() -> str:
    try:
        return require_secret("MAILGUN_API_KEY")
    except MissingSecretError as exc:
        raise EmailDeliveryError(str(exc)) from exc


def _smtp_enabled() -> bool:
    settings = get_settings()
    return bool(settings.email_host and settings.email_from_address)


def _mailgun_enabled() -> bool:
    settings = get_settings()
    api_key = settings.mailgun_api_key
    if not api_key or is_placeholder(api_key):
        return False
    return bool(settings.mailgun_domain and settings.email_from_address)


def _send_via_smtp(to_address: str, subject: str, body: str) -> None:
    settings = get_settings()
    host = settings.email_host
    from_address = settings.email_from_address
    if not host or not from_address:
        raise EmailDeliveryError("SMTP is not fully configured")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = from_address
    message["To"] = to_address
    message.set_content(body)

    username = (settings.email_username or "").strip()

    try:
        with smtplib.SMTP(host, settings.email_port, timeout=20) as smtp:
            if settings.email_use_tls:
                smtp.starttls()
            if username:
                password = _resolve_email_password()
                smtp.login(username, password)
            smtp.send_message(message)
    except Exception as exc:  # pragma: no cover - network interactions
        logger.exception("SMTP delivery failed for %s", to_address)
        raise EmailDeliveryError(str(exc)) from exc


def _send_via_mailgun(to_address: str, subject: str, body: str) -> None:
    settings = get_settings()
    domain = settings.mailgun_domain
    from_address = settings.email_from_address
    if not domain or not from_address:
        raise EmailDeliveryError("Mailgun is not configured")
    api_key = _resolve_mailgun_api_key()

    url = f"https://api.mailgun.net/v3/{domain}/messages"
    try:
        response = requests.post(
            url,
            auth=("api", api_key),
            data={
                "from": from_address,
                "to": to_address,
                "subject": subject,
                "text": body,
            },
            timeout=20,
        )
    except requests.RequestException as exc:  # pragma: no cover - network interactions
        logger.exception("Mailgun request failed for %s", to_address)
        raise EmailDeliveryError(str(exc)) from exc

    if response.status_code >= 400:
        logger.error("Mailgun returned %s: %s", response.status_code, response.text)
        raise EmailDeliveryError(f"Mailgun delivery failed with status {response.status_code}")


def send_email(to_address: str, subject: str, body: str) -> bool:
    """Send a plaintext email if SMTP settings are configured.

    Returns ``True`` when the email was successfully queued, ``False`` when
    delivery is skipped due to missing configuration or recipient address.
    Raises ``EmailDeliveryError`` when the SMTP transport fails mid-flight.
    """

    if not to_address or not subject or not body:
        raise EmailDeliveryError("Email payload is incomplete")

    smtp_enabled = _smtp_enabled()
    mailgun_enabled = _mailgun_enabled()
    if not smtp_enabled and not mailgun_enabled:
        raise EmailDeliveryError(
            "Email delivery is not configured. Provide SMTP settings or Mailgun credentials."
        )

    if smtp_enabled:
        try:
            _send_via_smtp(to_address, subject, body)
            return True
        except EmailDeliveryError as exc:
            logger.warning("SMTP delivery failed, attempting fallback if available: %s", exc)
            if not mailgun_enabled:
                raise

    if mailgun_enabled:
        _send_via_mailgun(to_address, subject, body)
        return True

    raise EmailDeliveryError("All email transports failed")


__all__ = ["send_email", "EmailDeliveryError"]
