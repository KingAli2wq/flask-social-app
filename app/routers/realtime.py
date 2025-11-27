"""WebSocket endpoints that emit realtime feed notifications."""
from __future__ import annotations

import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..services.realtime import feed_updates_manager

router = APIRouter()
logger = logging.getLogger(__name__)


@router.websocket("/ws/feed")
async def feed_updates(websocket: WebSocket) -> None:
    """Maintain a long-lived connection that pushes feed refresh events."""

    await feed_updates_manager.connect(websocket)
    logger.info("Feed socket connected from %s", websocket.client)
    try:
        while True:
            try:
                raw = await websocket.receive_text()
            except WebSocketDisconnect:
                break
            except Exception:
                logger.exception("Feed socket receive failed")
                break

            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                payload = {"type": raw}

            message_type = (payload.get("type") or "").lower()
            if message_type == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
            elif message_type == "hello":
                await websocket.send_text(json.dumps({"type": "ready"}))
            # All other messages are ignored, but receiving them keeps the connection alive.
    finally:
        await feed_updates_manager.disconnect(websocket)
        logger.info("Feed socket disconnected from %s", websocket.client)


__all__ = ["router"]
