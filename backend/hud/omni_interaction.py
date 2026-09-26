"""BLOQUE 97 - Local Omni-Channel Natural Interaction & Immersive HUD Overlay Engine.

Synthesizes voice, text, and visual context into executable intents for the
master orchestrator, drives a non-intrusive floating HUD, and exposes real-time
omni-interaction channels. 100% local and offline.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import platform
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("AURA.OmniInteraction")


# ---------------------------------------------------------------------------
# Enums & constants
# ---------------------------------------------------------------------------

class OmniChannel(str, Enum):
    VOICE = "voice"
    TEXT = "text"
    GESTURE = "gesture"
    SCREEN_CONTEXT = "screen_context"
    HOTKEY = "hotkey"
    SYSTEM = "system"


class OmniIntent(str, Enum):
    EXECUTE = "execute"
    QUERY = "query"
    CONTROL = "control"
    NAVIGATE = "navigate"
    NOTIFY = "notify"
    CANCEL = "cancel"


class HUDMode(str, Enum):
    FLOATING = "floating"
    DOCKED = "docked"
    MINIMAL = "minimal"
    FULL = "full"
    HIDDEN = "hidden"


class HUDPosition(str, Enum):
    TOP_RIGHT = "top_right"
    TOP_LEFT = "top_left"
    BOTTOM_RIGHT = "bottom_right"
    BOTTOM_LEFT = "bottom_left"
    CENTER = "center"
    FLOATING = "floating"


VALID_CHANNELS = tuple(c.value for c in OmniChannel)
VALID_INTENTS = tuple(i.value for i in OmniIntent)
VALID_HUD_MODES = tuple(m.value for m in HUDMode)
VALID_HUD_POSITIONS = tuple(p.value for p in HUDPosition)

# Simple keyword table for offline text->intent synthesis.
_INTENT_KEYWORDS = {
    OmniIntent.EXECUTE: ("run", "execute", "open", "launch", "start", "create", "make", "do"),
    OmniIntent.QUERY: ("what", "how", "where", "when", "who", "which", "status", "show", "list"),
    OmniIntent.CONTROL: ("set", "turn", "toggle", "adjust", "enable", "disable", "lock", "mute"),
    OmniIntent.NAVIGATE: ("go", "navigate", "switch", "change", "move", "jump"),
    OmniIntent.NOTIFY: ("notify", "alert", "remind", "tell", "say"),
    OmniIntent.CANCEL: ("cancel", "stop", "abort", "close", "dismiss"),
}

# Voice confidence thresholds (offline heuristic).
_VOICE_CONFIDENCE = {"high": 0.85, "medium": 0.6, "low": 0.35}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class OmniInput:
    """A single multimodal input event captured by the omni-channel layer."""
    input_id: str = ""
    channel: str = "text"
    raw_text: str = ""
    intent: str = ""
    target: str = ""
    confidence: float = 0.0
    context: Dict[str, Any] = field(default_factory=dict)
    ts: float = 0.0
    offline_only: bool = True

    def __post_init__(self) -> None:
        if not self.input_id:
            self.input_id = uuid.uuid4().hex[:12]
        if self.channel not in VALID_CHANNELS:
            raise ValueError(f"canal no soportado: {self.channel}")
        if self.intent and self.intent not in VALID_INTENTS:
            raise ValueError(f"intencion no soportada: {self.intent}")
        if not self.ts:
            self.ts = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "input_id": self.input_id, "channel": self.channel,
            "raw_text": self.raw_text, "intent": self.intent, "target": self.target,
            "confidence": round(self.confidence, 3), "context": self.context,
            "ts": self.ts, "offline_only": self.offline_only,
        }


@dataclass
class OmniCommand:
    """Executable intent emitted by the synthesizer for the master orchestrator."""
    command_id: str = ""
    intent: str = "execute"
    action: str = ""
    target: str = ""
    params: Dict[str, Any] = field(default_factory=dict)
    source_channel: str = "text"
    confidence: float = 0.0
    ts: float = 0.0
    offline_only: bool = True

    def __post_init__(self) -> None:
        if not self.command_id:
            self.command_id = uuid.uuid4().hex[:12]
        if self.intent not in VALID_INTENTS:
            raise ValueError(f"intencion no soportada: {self.intent}")
        if not self.ts:
            self.ts = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "command_id": self.command_id, "intent": self.intent,
            "action": self.action, "target": self.target, "params": self.params,
            "source_channel": self.source_channel, "confidence": round(self.confidence, 3),
            "ts": self.ts, "offline_only": self.offline_only,
        }


@dataclass
class HUDState:
    """Immersive floating HUD state snapshot."""
    mode: HUDMode = HUDMode.FLOATING
    position: HUDPosition = HUDPosition.BOTTOM_RIGHT
    x: int = 0
    y: int = 0
    opacity: float = 0.9
    always_on_top: bool = True
    click_through: bool = False
    visible: bool = False
    cognitive_state: str = "idle"
    active_context: str = ""
    quick_actions: List[Dict[str, Any]] = field(default_factory=list)
    alerts: List[Dict[str, Any]] = field(default_factory=list)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mode": self.mode.value, "position": self.position.value,
            "x": self.x, "y": self.y, "opacity": self.opacity,
            "always_on_top": self.always_on_top, "click_through": self.click_through,
            "visible": self.visible, "cognitive_state": self.cognitive_state,
            "active_context": self.active_context,
            "quick_actions": list(self.quick_actions), "alerts": list(self.alerts),
            "updated_at": self.updated_at, "offline_only": True,
        }

    @property
    def offline_only(self) -> bool:
        return True


@dataclass
class OmniEvent:
    """Real-time event broadcast over the WebSocket channel."""
    event_id: str = ""
    type: str = "hud_change"
    payload: Dict[str, Any] = field(default_factory=dict)
    ts: float = 0.0
    offline_only: bool = True

    def __post_init__(self) -> None:
        if not self.event_id:
            self.event_id = uuid.uuid4().hex[:12]
        if not self.ts:
            self.ts = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {"event_id": self.event_id, "type": self.type,
                "payload": self.payload, "ts": self.ts, "offline_only": self.offline_only}
class OmniInputSynthesizer:
    """Local omni-channel input synthesizer.

    Correlates voice, text, gesture, screen-context, hotkey and system events
    into executable intents for the master orchestrator. 100% offline: no cloud
    speech-to-text, no external NLP, no telemetry.
    """

    DEFAULT_QUICK_ACTIONS = [
        {"id": "toggle_hud", "label": "Toggle HUD", "intent": "control"},
        {"id": "open_calendar", "label": "Calendar", "intent": "execute"},
        {"id": "mute_audio", "label": "Mute", "intent": "control"},
        {"id": "lock_screen", "label": "Lock", "intent": "control"},
    ]

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._inputs: deque = deque(maxlen=2000)
        self._commands: deque = deque(maxlen=1000)
        self._callbacks: List[Callable[[OmniCommand], None]] = []

    # -- registration ------------------------------------------------------

    def on_command(self, cb: Callable[[OmniCommand], None]) -> None:
        with self._lock:
            self._callbacks.append(cb)

    # -- ingestion ---------------------------------------------------------

    def ingest(self, channel: str, text: str = "", confidence: float = 0.0,
               context: Optional[Dict[str, Any]] = None) -> OmniInput:
        if channel not in VALID_CHANNELS:
            raise ValueError(f"canal no soportado: {channel}")
        intent, target, action = self._synthesize(channel, text, confidence, context or {})
        inp = OmniInput(channel=channel, raw_text=text, intent=intent,
                        target=target, confidence=confidence, context=context or {})
        with self._lock:
            self._inputs.append(inp)
        cmd = self._to_command(inp, action)
        with self._lock:
            self._commands.append(cmd)
        for cb in list(self._callbacks):
            try:
                cb(cmd)
            except Exception as e:
                logger.warning("Synthesizer callback error: %s", e)
        return inp

    def ingest_voice(self, transcript: str, confidence: float = 0.0,
                     context: Optional[Dict[str, Any]] = None) -> OmniInput:
        conf = min(1.0, max(0.0, confidence or 0.0))
        level = "high" if conf >= 0.8 else ("medium" if conf >= 0.5 else "low")
        ctx = dict(context or {})
        ctx.setdefault("voice_confidence_level", level)
        return self.ingest(OmniChannel.VOICE.value, transcript, conf, ctx)

    def ingest_gesture(self, gesture: str, context: Optional[Dict[str, Any]] = None) -> OmniInput:
        ctx = dict(context or {})
        ctx.setdefault("gesture_type", gesture)
        return self.ingest(OmniChannel.GESTURE.value, gesture, 0.9, ctx)

    def ingest_screen_context(self, context: Optional[Dict[str, Any]] = None) -> OmniInput:
        ctx = dict(context or {})
        ctx.setdefault("source", "screen_bridge")
        text = ctx.get("summary") or ctx.get("app") or "screen_context"
        return self.ingest(OmniChannel.SCREEN_CONTEXT.value, str(text), 0.7, ctx)

    def ingest_hotkey(self, combo: str, context: Optional[Dict[str, Any]] = None) -> OmniInput:
        ctx = dict(context or {})
        ctx.setdefault("combo", combo)
        return self.ingest(OmniChannel.HOTKEY.value, combo, 1.0, ctx)

    # -- synthesis ---------------------------------------------------------

    def _synthesize(self, channel: str, text: str, confidence: float,
                    context: Dict[str, Any]) -> tuple[str, str, str]:
        t = (text or "").strip().lower()
        intent = OmniIntent.QUERY.value
        target = ""
        action = ""
        if channel == OmniChannel.HOTKEY.value:
            intent = OmniIntent.CONTROL.value
            action = "hotkey:" + (text or "")
            target = "system"
            return intent, target, action
        if channel == OmniChannel.GESTURE.value:
            intent = OmniIntent.CONTROL.value
            action = "gesture:" + (text or "")
            target = context.get("target", "overlay")
            return intent, target, action
        if channel == OmniChannel.SCREEN_CONTEXT.value:
            intent = OmniIntent.QUERY.value
            action = "context:" + (text or "")
            target = context.get("app", "screen")
            return intent, target, action
        # text / voice
        for cand_intent, kws in _INTENT_KEYWORDS.items():
            for kw in kws:
                if t.startswith(kw) or f" {kw} " in f" {t} " or t == kw:
                    intent = cand_intent.value
                    action = kw
                    target = self._extract_target(t, cand_intent)
                    return intent, target, action
        if t:
            intent = OmniIntent.EXECUTE.value
            action = t.split()[0]
            target = t
        return intent, target, action

    @staticmethod
    def _extract_target(text: str, intent: OmniIntent) -> str:
        parts = text.split()
        if len(parts) >= 2:
            return parts[1]
        return text

    def _to_command(self, inp: OmniInput, action: str) -> OmniCommand:
        return OmniCommand(intent=inp.intent or OmniIntent.EXECUTE.value,
                           action=action or "noop", target=inp.target or "",
                           params=dict(inp.context), source_channel=inp.channel,
                           confidence=inp.confidence, ts=inp.ts)

    # -- accessors ---------------------------------------------------------

    def recent_inputs(self, limit: int = 50) -> List[OmniInput]:
        with self._lock:
            return list(self._inputs)[-limit:]

    def recent_commands(self, limit: int = 50) -> List[OmniCommand]:
        with self._lock:
            return list(self._commands)[-limit:]

    def clear(self) -> Dict[str, int]:
        with self._lock:
            ni = len(self._inputs)
            nc = len(self._commands)
            self._inputs.clear()
            self._commands.clear()
        return {"inputs_cleared": ni, "commands_cleared": nc}

    def status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "buffered_inputs": len(self._inputs),
                "buffered_commands": len(self._commands),
                "callbacks": len(self._callbacks),
                "channels": list(VALID_CHANNELS),
                "intents": list(VALID_INTENTS),
                "offline_only": True,
            }
class HUDController:
    """Immersive real-time HUD overlay controller.

    Manages a non-intrusive floating interface that surfaces cognitive state,
    system alerts and quick actions. Decoupled from the B75 OverlayBridge: this
    engine owns its own state and can coexist with it.
    """

    def __init__(self) -> None:
        self._state = HUDState()
        self._lock = threading.RLock()
        self._callbacks: List[Callable[[Dict[str, Any]], None]] = []
        self._ws_subscribers: set = set()
        self._quick_actions: List[Dict[str, Any]] = list(OmniInputSynthesizer.DEFAULT_QUICK_ACTIONS)

    # -- state access ------------------------------------------------------

    @property
    def state(self) -> HUDState:
        with self._lock:
            return self._state

    def status(self) -> Dict[str, Any]:
        with self._lock:
            st = self._state.to_dict()
        st["quick_actions_count"] = len(self._quick_actions)
        st["subscribers"] = len(self._ws_subscribers)
        return st

    # -- mutations ---------------------------------------------------------

    def set_mode(self, mode: HUDMode) -> HUDState:
        with self._lock:
            self._state.mode = mode
            self._state.visible = mode != HUDMode.HIDDEN
            self._state.updated_at = time.time()
            st = self._state
        self._emit("hud_mode", {"mode": st.mode.value, "visible": st.visible})
        return st

    def toggle_visibility(self) -> HUDState:
        with self._lock:
            if self._state.visible:
                self._state.mode = HUDMode.HIDDEN
                self._state.visible = False
            else:
                self._state.mode = HUDMode.FLOATING
                self._state.visible = True
            self._state.updated_at = time.time()
            st = self._state
        self._emit("hud_visibility", {"visible": st.visible, "mode": st.mode.value})
        return st

    def set_position(self, position: HUDPosition, x: int = 0, y: int = 0) -> HUDState:
        with self._lock:
            self._state.position = position
            self._state.x = max(0, int(x))
            self._state.y = max(0, int(y))
            self._state.updated_at = time.time()
            st = self._state
        self._emit("hud_position", {"position": st.position.value, "x": st.x, "y": st.y})
        return st

    def set_opacity(self, opacity: float) -> HUDState:
        with self._lock:
            self._state.opacity = max(0.1, min(1.0, float(opacity)))
            self._state.updated_at = time.time()
            st = self._state
        self._emit("hud_opacity", {"opacity": st.opacity})
        return st

    def set_cognitive_state(self, state: str) -> HUDState:
        with self._lock:
            self._state.cognitive_state = state or "idle"
            self._state.updated_at = time.time()
            st = self._state
        self._emit("hud_cognitive_state", {"cognitive_state": st.cognitive_state})
        return st

    def set_context(self, context: str) -> HUDState:
        with self._lock:
            self._state.active_context = context or ""
            self._state.updated_at = time.time()
            st = self._state
        self._emit("hud_context", {"active_context": st.active_context})
        return st

    def push_alert(self, title: str, message: str = "", severity: str = "info") -> dict:
        alert = {"title": title, "message": message, "severity": severity,
                 "timestamp": time.time()}
        with self._lock:
            self._state.alerts.append(alert)
            if len(self._state.alerts) > 50:
                self._state.alerts = self._state.alerts[-50:]
            self._state.updated_at = time.time()
        self._emit("hud_alert", alert)
        return alert

    def add_alert(self, severity: str, message: str) -> dict:
        return self.push_alert(title=severity, message=message, severity=severity)

    def clear_alerts(self) -> int:
        with self._lock:
            n = len(self._state.alerts)
            self._state.alerts.clear()
            self._state.updated_at = time.time()
        self._emit("hud_alerts_cleared", {"count": n})
        return n

    def set_quick_actions(self, actions: List[Dict[str, Any]]) -> int:
        with self._lock:
            self._quick_actions = list(actions or [])[:20]
            self._state.quick_actions = list(self._quick_actions)
            self._state.updated_at = time.time()
        self._emit("hud_quick_actions", {"count": len(self._quick_actions)})
        return len(self._quick_actions)

    def toggle_click_through(self) -> HUDState:
        with self._lock:
            self._state.click_through = not self._state.click_through
            self._state.updated_at = time.time()
            st = self._state
        self._emit("hud_click_through", {"click_through": st.click_through})
        return st

    # -- subscription ------------------------------------------------------

    def subscribe(self, cb: Callable[[Dict[str, Any]], None]) -> None:
        with self._lock:
            self._callbacks.append(cb)

    def subscribe_websocket(self, ws) -> None:
        with self._lock:
            self._ws_subscribers.add(ws)

    def unsubscribe_websocket(self, ws) -> None:
        with self._lock:
            self._ws_subscribers.discard(ws)

    def _emit(self, event_type: str, payload: dict) -> None:
        full = {"type": event_type, "payload": payload, "state": self._state.to_dict(),
                "ts": time.time(), "offline_only": True}
        for cb in list(self._callbacks):
            try:
                cb(full)
            except Exception as e:
                logger.warning("HUD callback error: %s", e)

    def broadcast(self, payload: Dict[str, Any]) -> None:
        self._emit(payload.get("type", "hud_change"), payload.get("payload", {}))


_global_hud: Optional[HUDController] = None
_hud_lock = threading.Lock()


def get_hud_controller() -> HUDController:
    global _global_hud
    if _global_hud is None:
        with _hud_lock:
            if _global_hud is None:
                _global_hud = HUDController()
    return _global_hud


def reset_hud_controller() -> None:
    global _global_hud
    with _hud_lock:
        _global_hud = None
class OmniInteractionEngine:
    """Master omni-interaction engine.

    Wires the OmniInputSynthesizer and HUDController together, exposes the
    real-time WebSocket channel, and relays commands to the master orchestrator
    when one is reachable. 100% local and offline.
    """

    def __init__(self, auto_start: bool = True) -> None:
        self.synthesizer = OmniInputSynthesizer()
        self.hud = HUDController()
        self.auto_start = auto_start
        self._lock = threading.RLock()
        self._events: deque = deque(maxlen=2000)
        self._callbacks: List[Callable[[Dict[str, Any]], None]] = []
        self._orchestrator = None
        self._ws_connections: set = set()
        self._ws_loop = None
        # Wire synthesizer -> HUD cognitive-state updates.
        self.synthesizer.on_command(self._on_command)

    # -- callbacks ---------------------------------------------------------

    def on_event(self, cb: Callable[[Dict[str, Any]], None]) -> None:
        with self._lock:
            self._callbacks.append(cb)

    def on_command(self, cb: Callable[[OmniCommand], None]) -> None:
        self.synthesizer.on_command(cb)

    def _emit(self, payload: Dict[str, Any]) -> None:
        with self._lock:
            self._events.append(payload)
            cbs = list(self._callbacks)
        for cb in cbs:
            try:
                cb(payload)
            except Exception as e:
                logger.warning("Omni engine callback error: %s", e)
        self._broadcast_ws(payload)

    def _on_command(self, cmd: OmniCommand) -> None:
        # Update HUD cognitive state based on the intent.
        state_map = {
            OmniIntent.EXECUTE.value: "executing",
            OmniIntent.QUERY.value: "thinking",
            OmniIntent.CONTROL.value: "controlling",
            OmniIntent.NAVIGATE.value: "navigating",
            OmniIntent.NOTIFY.value: "notifying",
            OmniIntent.CANCEL.value: "idle",
        }
        cognitive = state_map.get(cmd.intent, "active")
        try:
            self.hud.set_cognitive_state(cognitive)
        except Exception:
            pass
        self._emit({"type": "omni_command", **cmd.to_dict()})
        # Forward to master orchestrator if available.
        self._forward_to_orchestrator(cmd)

    def _forward_to_orchestrator(self, cmd: OmniCommand) -> None:
        orch = self._orchestrator
        if orch is None:
            return
        try:
            fn = getattr(orch, "execute_omni_command", None)
            if callable(fn):
                fn(cmd)
                return
            fn = getattr(orch, "dispatch", None)
            if callable(fn):
                fn(cmd.to_dict())
        except Exception as e:
            logger.warning("Orchestrator forward failed: %s", e)

    def set_orchestrator(self, orchestrator) -> None:
        with self._lock:
            self._orchestrator = orchestrator

    # -- WebSocket ---------------------------------------------------------

    def register_websocket(self, ws) -> None:
        with self._lock:
            self._ws_connections.add(ws)

    def unregister_websocket(self, ws) -> None:
        with self._lock:
            self._ws_connections.discard(ws)

    def set_ws_loop(self, loop) -> None:
        with self._lock:
            self._ws_loop = loop

    def _broadcast_ws(self, payload: Dict[str, Any]) -> None:
        with self._lock:
            conns = list(self._ws_connections)
            loop = self._ws_loop
        if not conns or loop is None or loop.is_closed():
            return
        for ws in conns:
            try:
                coro = ws.send_json(payload)
                if asyncio.iscoroutine(coro):
                    loop.call_soon_threadsafe(asyncio.ensure_future, coro)
            except Exception:
                self.unregister_websocket(ws)

    # -- public API --------------------------------------------------------

    def ingest(self, channel: str, text: str = "", confidence: float = 0.0,
               context: Optional[Dict[str, Any]] = None) -> OmniInput:
        return self.synthesizer.ingest(channel, text, confidence, context)

    def process_command(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Process an incoming omni-command from the HUD or external client."""
        channel = payload.get("channel", OmniChannel.TEXT.value)
        text = payload.get("text") or payload.get("command") or ""
        confidence = float(payload.get("confidence", 0.0) or 0.0)
        ctx = payload.get("context") or {}
        inp = self.ingest(channel, text, confidence, ctx)
        return {"status": "ok", "input": inp.to_dict()}

    def hud_action(self, action: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        params = params or {}
        hud = self.hud
        if action == "toggle":
            st = hud.toggle_visibility()
        elif action == "mode":
            st = hud.set_mode(HUDMode(params.get("mode", "floating")))
        elif action == "position":
            st = hud.set_position(HUDPosition(params.get("position", "bottom_right")),
                                  int(params.get("x", 0)), int(params.get("y", 0)))
        elif action == "opacity":
            st = hud.set_opacity(float(params.get("opacity", 0.9)))
        elif action == "alert":
            hud.push_alert(params.get("title", ""), params.get("message", ""),
                           params.get("severity", "info"))
            st = hud.state
        elif action == "clear_alerts":
            hud.clear_alerts()
            st = hud.state
        elif action == "quick_actions":
            hud.set_quick_actions(params.get("actions", []))
            st = hud.state
        elif action == "click_through":
            st = hud.toggle_click_through()
        elif action == "context":
            st = hud.set_context(params.get("context", ""))
        else:
            st = hud.state
        return {"status": "ok", "action": action, "state": st.to_dict()}

    def status(self) -> Dict[str, Any]:
        return {
            "synthesizer": self.synthesizer.status(),
            "hud": self.hud.status(),
            "events_buffered": len(self._events),
            "ws_connections": len(self._ws_connections),
            "orchestrator_connected": self._orchestrator is not None,
            "platform": platform.system(),
            "offline_only": True,
        }

    def snapshot(self) -> Dict[str, Any]:
        return {
            "hud": self.hud.state.to_dict(),
            "recent_commands": [c.to_dict() for c in self.synthesizer.recent_commands(10)],
            "recent_inputs": [i.to_dict() for i in self.synthesizer.recent_inputs(20)],
            "offline_only": True,
        }

    def reset(self) -> Dict[str, int]:
        sc = self.synthesizer.clear()
        self.hud.clear_alerts()
        with self._lock:
            ne = len(self._events)
            self._events.clear()
        return {"events_cleared": ne, **sc}


_global_engine: Optional[OmniInteractionEngine] = None
_engine_lock = threading.Lock()


def get_omni_engine() -> OmniInteractionEngine:
    global _global_engine
    if _global_engine is None:
        with _engine_lock:
            if _global_engine is None:
                _global_engine = OmniInteractionEngine()
    return _global_engine


def reset_omni_engine() -> None:
    global _global_engine
    with _engine_lock:
        _global_engine = None