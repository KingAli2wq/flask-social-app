"""WebSocket manager dedicated to notification fanout."""
from __future__ import annotations

import asyncio
import json
from typing import Iterable

from fastapi import WebSocket


class NotificationStreamManager:
    """Tracks per-user WebSocket connections and broadcasts payloads."""

    def __init__(self) -> None:
        self._channels: dict[str, set[WebSocket]] = {}
        self._connections: dict[WebSocket, str] = {}
        self._lock = asyncio.Lock()

    async def connect(self, user_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            group = self._channels.setdefault(user_id, set())
            group.add(websocket)
            self._connections[websocket] = user_id

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            user_id = self._connections.pop(websocket, None)
            if not user_id:
                return
            group = self._channels.get(user_id)
            if group is None:
                return
            group.discard(websocket)
            if not group:
                self._channels.pop(user_id, None)

    async def broadcast(self, users: str | Iterable[str], payload: dict[str, object]) -> None:
        if not users:
            return
        if isinstance(users, str):
            target_ids = [users]
        else:
            target_ids = [user for user in users if user]
        if not target_ids:
            return
        serialized = json.dumps(payload, default=str)
        async with self._lock:
            targets: list[WebSocket] = []
            for user_id in target_ids:
                targets.extend(self._channels.get(user_id, ()))
        for ws in targets:
            try:
                await ws.send_text(serialized)
            except Exception:
                await self.disconnect(ws)


notification_stream_manager = NotificationStreamManager()


__all__ = ["notification_stream_manager", "NotificationStreamManager"]
