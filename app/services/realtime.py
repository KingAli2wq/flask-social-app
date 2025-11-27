"""In-memory WebSocket broadcast helpers for lightweight realtime updates."""
from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import WebSocket


class WebSocketManager:
    """Tracks active WebSocket connections and broadcasts JSON payloads."""

    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections.add(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections.discard(websocket)

    async def broadcast(self, message: dict[str, Any]) -> None:
        payload = json.dumps(message, default=str)
        async with self._lock:
            targets = list(self._connections)
        for connection in targets:
            try:
                await connection.send_text(payload)
            except Exception:
                await self.disconnect(connection)


feed_updates_manager = WebSocketManager()


__all__ = ["feed_updates_manager", "WebSocketManager"]
