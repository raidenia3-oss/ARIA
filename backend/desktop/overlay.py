"""AURA Desktop HUD Overlay Bridge (Bloque 75)."""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("AURA.Overlay")


class OverlayMode(str, Enum):
    HIDDEN = "hidden"
    MINIMAL = "minimal"
    COMPACT = "compact"
    FULL = "full"
    DND = "dnd"


class OverlayPosition(str, Enum):
    TOP_RIGHT = "top_right"
    TOP_LEFT = "top_left"
    BOTTOM_RIGHT = "bottom_right"
    BOTTOM_LEFT = "bottom_left"
    CENTER = "center"
    CUSTOM = "custom"


@dataclass
class OverlayState:
    mode: OverlayMode = OverlayMode.HIDDEN
    position: OverlayPosition = OverlayPosition.TOP_RIGHT
    custom_x: int = 0
    custom_y: int = 0
    opacity: float = 0.85
    always_on_top: bool = True
    click_through: bool = False
    visible: bool = False
    pinned: bool = False
    current_context: str = ""
    notifications: List[Dict[str, Any]] = field(default_factory=list)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mode": self.mode.value, "position": self.position.value,
            "custom_x": self.custom_x, "custom_y": self.custom_y,
            "opacity": self.opacity, "always_on_top": self.always_on_top,
            "click_through": self.click_through, "visible": self.visible,
            "pinned": self.pinned, "current_context": self.current_context,
            "notifications_count": len(self.notifications), "updated_at": self.updated_at,
        }


class OverlayBridge:
    def __init__(self) -> None:
        self._state = OverlayState()
        self._lock = threading.Lock()
        self._callbacks: List[Callable] = []
        self._ws_subscribers: set = set()

    @property
    def state(self) -> OverlayState:
        with self._lock:
            return self._state

    def set_mode(self, mode: OverlayMode) -> OverlayState:
        with self._lock:
            self._state.mode = mode
            self._state.visible = mode != OverlayMode.HIDDEN
            self._state.updated_at = time.time()
            state = self._state
        self._notify_change("mode", {"mode": mode.value})
        return state

    def toggle_visibility(self) -> OverlayState:
        with self._lock:
            if self._state.mode == OverlayMode.HIDDEN:
                self._state.mode = OverlayMode.COMPACT
                self._state.visible = True
            else:
                self._state.mode = OverlayMode.HIDDEN
                self._state.visible = False
            self._state.updated_at = time.time()
            state = self._state
        self._notify_change("visibility", {"visible": state.visible})
        return state

    def set_position(self, position: OverlayPosition, x=0, y=0) -> OverlayState:
        with self._lock:
            self._state.position = position
            self._state.custom_x = x
            self._state.custom_y = y
            self._state.updated_at = time.time()
            state = self._state
        self._notify_change("position", {"position": position.value, "x": x, "y": y})
        return state

    def set_opacity(self, opacity: float) -> OverlayState:
        with self._lock:
            self._state.opacity = max(0.1, min(1.0, opacity))
            self._state.updated_at = time.time()
            state = self._state
        self._notify_change("opacity", {"opacity": self._state.opacity})
        return state

    def set_context(self, context: str) -> OverlayState:
        with self._lock:
            self._state.current_context = context
            self._state.updated_at = time.time()
            state = self._state
        self._notify_change("context", {"context": context})
        return state

    def add_notification(self, title, message, kind="info") -> dict:
        notif = {"title": title, "message": message, "kind": kind, "timestamp": time.time()}
        with self._lock:
            self._state.notifications.append(notif)
            if len(self._state.notifications) > 50:
                self._state.notifications = self._state.notifications[-50:]
        self._notify_change("notification", notif)
        return notif

    def clear_notifications(self) -> int:
        with self._lock:
            count = len(self._state.notifications)
            self._state.notifications.clear()
        self._notify_change("notifications_cleared", {"count": count})
        return count

    def toggle_dnd(self) -> OverlayState:
        with self._lock:
            if self._state.mode == OverlayMode.DND:
                self._state.mode = OverlayMode.COMPACT
            else:
                self._state.mode = OverlayMode.DND
            self._state.updated_at = time.time()
            state = self._state
        self._notify_change("dnd", {"dnd": self._state.mode == OverlayMode.DND})
        return state

    def toggle_pin(self) -> OverlayState:
        with self._lock:
            self._state.pinned = not self._state.pinned
            self._state.updated_at = time.time()
            state = self._state
        self._notify_change("pin", {"pinned": self._state.pinned})
        return state

    def subscribe_websocket(self, ws) -> None:
        self._ws_subscribers.add(ws)

    def unsubscribe_websocket(self, ws) -> None:
        self._ws_subscribers.discard(ws)

    def add_change_callback(self, callback: Callable) -> None:
        self._callbacks.append(callback)

    def _notify_change(self, change_type: str, data: dict) -> None:
        payload = {"type": "overlay_change", "change": change_type, "data": data, "state": self._state.to_dict()}
        for cb in self._callbacks:
            try:
                cb(payload)
            except Exception as e:
                logger.warning("Overlay callback error: %s", e)

    def status(self) -> dict:
        with self._lock:
            return {"status": "ok", "state": self._state.to_dict(), "subscribers": len(self._ws_subscribers)}


_bridge = None
_bridge_lock = threading.Lock()


def get_overlay_bridge():
    global _bridge
    if _bridge is None:
        with _bridge_lock:
            if _bridge is None:
                _bridge = OverlayBridge()
    return _bridge


def reset_overlay_bridge():
    global _bridge
    with _bridge_lock:
        _bridge = None


__all__ = ["OverlayMode", "OverlayPosition", "OverlayState", "OverlayBridge", "get_overlay_bridge", "reset_overlay_bridge"]
