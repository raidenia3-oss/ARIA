"""ARIA Integration — Connects observer, suggestion engine, and content generator."""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

try:
    from backend.aria_observer_v2 import AriaObserverV2

    OBSERVER_AVAILABLE = True
except Exception:
    OBSERVER_AVAILABLE = False
    AriaObserverV2 = None

try:
    from backend.aria_suggestion_engine import SuggestionEngine

    SUGGESTION_AVAILABLE = True
except Exception:
    SUGGESTION_AVAILABLE = False
    SuggestionEngine = None

try:
    from backend.aria_content_engine import AriaContentEngine

    CONTENT_AVAILABLE = True
except Exception:
    CONTENT_AVAILABLE = False
    AriaContentEngine = None

try:
    import psutil

    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

try:
    import win32gui

    try:
        import win32process
    except ImportError:
        win32process = None
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

SUGGESTION_DIMENSIONS = {
    "story": "creation",
    "character": "creation",
    "world": "creation",
    "prompt": "delivery",
    "general": "discovery",
    "security": "cyber",
    "research": "discovery",
    "analysis": "cyber",
}


class AriaIntegration:
    """Integrates observer + suggestion engine + content generator."""

    def __init__(self, backend_url: str = "http://localhost:8000") -> None:
        self.backend_url = backend_url
        self._running = False
        self._loop_task: Optional[asyncio.Task] = None
        self._ws_connections: List[Any] = []
        self._suggestion_id = 0

        if OBSERVER_AVAILABLE:
            self.observer = AriaObserverV2(backend_url=backend_url, poll_interval=2)
        else:
            self.observer = None

        if SUGGESTION_AVAILABLE:
            self.suggestion_engine = SuggestionEngine()
        else:
            self.suggestion_engine = None

        if CONTENT_AVAILABLE:
            self.content_engine = AriaContentEngine()
        else:
            self.content_engine = None

        self._executor = ThreadPoolExecutor(max_workers=4)

    async def start_full_aria(self) -> Dict[str, Any]:
        result = {
            "observer": False,
            "suggestion_engine": False,
            "content_engine": False,
            "websocket": False,
        }
        if self.observer:
            try:
                self.observer.start()
                result["observer"] = True
            except Exception:
                pass
        if self.suggestion_engine:
            result["suggestion_engine"] = True
        if self.content_engine:
            result["content_engine"] = True
        self._running = True
        result["websocket"] = True
        self._loop_task = asyncio.create_task(self.suggestion_loop())
        return result

    async def stop_full_aria(self) -> Dict[str, Any]:
        self._running = False
        if self._loop_task:
            self._loop_task.cancel()
            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass
        if self.observer:
            self.observer.stop()
        for ws in self._ws_connections:
            try:
                ws.close()
            except Exception:
                pass
        self._ws_connections.clear()
        return {"status": "stopped"}

    async def suggestion_loop(self) -> None:
        while self._running:
            try:
                if not self.observer or not self.suggestion_engine:
                    await asyncio.sleep(10)
                    continue
                context = self.observer.build_context()
                suggestions = await self.suggestion_engine.generate_live_suggestions(
                    context, count=3
                )
                mood = await self.observer.track_mood()
                intent = await self.observer.detect_intent()
                keywords = await self.observer.extract_context_keywords()

                for s in suggestions:
                    dim = SUGGESTION_DIMENSIONS.get(
                        s.get("suggestion_type", "general"), "discovery"
                    )
                    self._emit_to_clients(
                        {
                            "type": "suggestion",
                            "dimension": dim,
                            "suggestion": s,
                        }
                    )

                self._emit_to_clients({"type": "mood", **mood})
                self._emit_to_clients(
                    {
                        "type": "intent",
                        "intent": intent.get("intent"),
                        "confidence": intent.get("confidence"),
                        "keywords": keywords[:5],
                    }
                )
                self._emit_to_clients(
                    {
                        "type": "activity",
                        "text": f"Actividad: {context.get('current_app', 'unknown')} | Mood: {mood.get('mood')}",
                    }
                )
            except asyncio.CancelledError:
                break
            except Exception:
                pass
            await asyncio.sleep(10)

    def _emit_to_clients(self, data: dict) -> None:
        msg = json.dumps(data)
        for ws in self._ws_connections:
            try:
                if hasattr(ws, "send") and getattr(ws, "open", True):
                    ws.send(msg)
            except Exception:
                pass

    async def websocket_handler(self, websocket: Any) -> None:
        self._ws_connections.append(websocket)
        try:
            while True:
                try:
                    raw = await websocket.receive_text()
                except Exception:
                    break
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    await websocket.send_json({"type": "error", "message": "invalid JSON"})
                    continue

                msg_type = msg.get("type", "")
                if msg_type == "accept":
                    sid = msg.get("suggestion_id")
                    if sid and self.suggestion_engine:
                        result = await self.suggestion_engine.accept_suggestion(sid)
                        await websocket.send_json({"type": "accept_result", **result})
                elif msg_type == "reject":
                    sid = msg.get("suggestion_id")
                    if sid and self.suggestion_engine:
                        result = await self.suggestion_engine.learn_from_rejection(sid)
                        await websocket.send_json({"type": "reject_result", **result})
                elif msg_type == "get_suggestions":
                    if self.suggestion_engine:
                        profile = msg.get("profile", {})
                        suggestions = await self.suggestion_engine.personalize_suggestions(profile)
                        await websocket.send_json(
                            {"type": "personalized", "suggestions": suggestions}
                        )
                elif msg_type == "generate_content":
                    content_type = msg.get("content_type", "story")
                    context = msg.get("context", {})
                    if self.content_engine:
                        result = await self.content_engine.suggest_content(context)
                        await websocket.send_json({"type": "content_result", **result})
                elif msg_type == "context_request":
                    if self.observer:
                        ctx = self.observer.build_context()
                        await websocket.send_json({"type": "context", "context": ctx})
                else:
                    await websocket.send_json({"type": "ok"})
        except Exception:
            pass
        finally:
            if websocket in self._ws_connections:
                self._ws_connections.remove(websocket)

    async def get_suggestions(self, count: int = 3) -> List[Dict[str, Any]]:
        if not self.observer or not self.suggestion_engine:
            return []
        context = self.observer.build_context()
        return await self.suggestion_engine.generate_live_suggestions(context, count)

    async def accept_suggestion(self, suggestion_id: str) -> Dict[str, Any]:
        if self.suggestion_engine:
            return await self.suggestion_engine.accept_suggestion(suggestion_id)
        return {"status": "error", "message": "Suggestion engine not available"}

    async def reject_suggestion(self, suggestion_id: str) -> Dict[str, Any]:
        if self.suggestion_engine:
            return await self.suggestion_engine.learn_from_rejection(suggestion_id)
        return {"status": "error", "message": "Suggestion engine not available"}
