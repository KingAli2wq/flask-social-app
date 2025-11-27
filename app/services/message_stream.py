"""WebSocket channel manager for realtime message delivery."""
from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import WebSocket


class MessageStreamManager:
    """Track per-chat WebSocket connections and broadcast events."""

    def __init__(self) -> None:
        self._channels: dict[str, set[WebSocket]] = {}
        self._connections: dict[WebSocket, str] = {}
        self._lock = asyncio.Lock()

    async def connect(self, chat_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            group = self._channels.setdefault(chat_id, set())
            group.add(websocket)
            self._connections[websocket] = chat_id

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            chat_id = self._connections.pop(websocket, None)
            if not chat_id:
                return
            group = self._channels.get(chat_id)
            if group is None:
                return
            group.discard(websocket)
            if not group:
                self._channels.pop(chat_id, None)

    async def broadcast(self, chat_id: str | None, payload: dict[str, Any]) -> None:
        if not chat_id:
            return
        serialized = json.dumps(payload, default=str)
        async with self._lock:
            targets = list(self._channels.get(chat_id, ()))
        for connection in targets:
            try:
                await connection.send_text(serialized)
            except Exception:
                await self.disconnect(connection)


message_stream_manager = MessageStreamManager()


__all__ = ["message_stream_manager", "MessageStreamManager"]
