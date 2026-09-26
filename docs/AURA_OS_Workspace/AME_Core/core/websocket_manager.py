#!/usr/bin/env python3
"""AURA WebSocket Manager — Broadcast bidireccional en tiempo real."""

import asyncio, json, threading
from fastapi import WebSocket, WebSocketDisconnect
from typing import Set


class WSManager:
    def __init__(self):
        self._connections: Set[WebSocket] = set()
        self._lock = threading.Lock()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        with self._lock:
            self._connections.add(ws)

    async def disconnect(self, ws: WebSocket):
        with self._lock:
            if ws in self._connections:
                self._connections.remove(ws)

    async def broadcast(self, data: dict):
        payload = json.dumps(data)
        dead = set()
        for ws in self._connections.copy():
            try:
                await ws.send_text(payload)
            except:
                dead.add(ws)
        with self._lock:
            for ws in dead:
                self._connections.discard(ws)


manager = WSManager()
