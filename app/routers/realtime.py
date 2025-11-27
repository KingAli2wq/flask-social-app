"""WebSocket endpoints that emit realtime feed notifications."""
from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..services.realtime import feed_updates_manager

router = APIRouter()


@router.websocket("/ws/feed")
async def feed_updates(websocket: WebSocket) -> None:
    """Maintain a long-lived connection that pushes feed refresh events."""

    await feed_updates_manager.connect(websocket)
    try:
        while True:
            # We do not expect messages but receive() keeps the connection alive and
            # allows clients to send optional pings without causing disconnects.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception:
        # Defensive; unexpected errors should not crash the server.
        pass
    finally:
        await feed_updates_manager.disconnect(websocket)


__all__ = ["router"]
