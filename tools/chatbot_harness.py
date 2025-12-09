"""Command-line harness for exercising the chatbot service without HTTP."""
from __future__ import annotations

import argparse
import sys
from typing import Iterable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import User
from app.services import ChatbotServiceError, list_chatbot_sessions, send_chat_prompt


def _collect_user(db: Session, username: str, *, auto_create: bool) -> User:
    record = db.scalar(select(User).where(User.username == username))
    if record:
        return record
    if not auto_create:
        raise SystemExit(f"User '{username}' does not exist. Pass --auto-create to provision one for testing.")
    user = User(username=username, hashed_password="!chatbot-harness!")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _parse_session_id(raw: str | None) -> UUID | None:
    if not raw:
        return None
    try:
        return UUID(raw.strip())
    except ValueError as exc:  # pragma: no cover - defensive CLI parsing
        raise SystemExit(f"'{raw}' is not a valid session id") from exc


def _print_transcript(transcript) -> None:
    session = transcript.session
    print(f"Session: {session.id} | persona={session.persona} | updated={session.updated_at:%Y-%m-%d %H:%M:%S}")
    print("-" * 80)
    for message in transcript.messages:
        role = message.role.upper()
        preview = (message.content or "").strip()
        print(f"[{role}] {message.created_at:%H:%M:%S} :: {preview}")
    print("-" * 80)


def _print_session_summaries(summaries: Iterable) -> None:
    for summary in summaries:
        preview = summary.last_message_preview or "(no messages)"
        print(
            f"{summary.session_id} | persona={summary.persona} | updated={summary.updated_at:%Y-%m-%d %H:%M:%S} | "
            f"preview={preview}"
        )


def _run_chat(args: argparse.Namespace) -> int:
    with SessionLocal() as db:
        user = _collect_user(db, args.username, auto_create=args.auto_create)
        session_id = _parse_session_id(args.session_id)
        try:
            transcript = send_chat_prompt(
                db,
                user=user,
                message=args.message,
                session_id=session_id,
                persona=args.persona,
                title=args.title,
                include_public_context=not args.skip_context,
            )
        except ChatbotServiceError as exc:
            print(f"Chatbot call failed: {exc}", file=sys.stderr)
            return 2
        _print_transcript(transcript)
    return 0


def _run_list(args: argparse.Namespace) -> int:
    with SessionLocal() as db:
        user = _collect_user(db, args.username, auto_create=args.auto_create)
        summaries = list_chatbot_sessions(db, user=user)
        if not summaries:
            print("No chatbot sessions found for this user.")
            return 0
        _print_session_summaries(summaries)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Developer harness for the AI chatbot.")
    subcommands = parser.add_subparsers(dest="command", required=True)

    chat = subcommands.add_parser("chat", help="Send a prompt and print the transcript.")
    chat.add_argument("message", help="User message to send to the chatbot.")
    chat.add_argument("--username", default="devchat", help="Existing username to impersonate (default: %(default)s).")
    chat.add_argument("--session-id", help="Existing session id to continue.")
    chat.add_argument("--persona", help="Override the session persona.")
    chat.add_argument("--title", help="Set a title when starting a new session.")
    chat.add_argument("--skip-context", action="store_true", help="Disable public post/story context in the prompt.")
    chat.add_argument(
        "--auto-create",
        action="store_true",
        help="Create the username automatically for local testing when it does not exist.",
    )
    chat.set_defaults(func=_run_chat)

    sessions = subcommands.add_parser("sessions", help="List previous chatbot sessions for a user.")
    sessions.add_argument("--username", default="devchat", help="Username to inspect (default: %(default)s).")
    sessions.add_argument(
        "--auto-create",
        action="store_true",
        help="Create the username automatically when missing to avoid errors.",
    )
    sessions.set_defaults(func=_run_list)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = getattr(args, "func", None)
    if handler is None:
        parser.error("Please supply a sub-command")
    return handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
