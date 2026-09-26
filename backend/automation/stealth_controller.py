from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import random
import secrets
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from backend.automation.os_controller import OSAction, OSActionType, RiskLevel

logger = logging.getLogger("AURA.Automation.Stealth")


@dataclass
class BezierPoint:
    x: float
    y: float
    t: float = 0.0


@dataclass
class OrganicMove:
    move_id: str
    start_x: float
    start_y: float
    end_x: float
    end_y: float
    duration: float
    curve: List[BezierPoint] = field(default_factory=list)
    jitter: float = 0.0
    overshoot: float = 0.0
    created_at: float = field(default_factory=time.time)


@dataclass
class StochasticTiming:
    base_delay: float
    actual_delay: float
    jitter_applied: float
    timestamp: float = field(default_factory=time.time)


class HumanProfile(str, Enum):
    CAUTION = "cautious"
    NORMAL = "normal"
    FAST = "fast"


_DEFAULT_PROFILES: Dict[HumanProfile, Dict[str, float]] = {
    HumanProfile.CAUTION: {"move_speed": 0.6, "typing_speed": 0.7, "delay_mult": 1.5, "jitter": 0.35, "overshoot": 0.15},
    HumanProfile.NORMAL:  {"move_speed": 1.0, "typing_speed": 1.0, "delay_mult": 1.0, "jitter": 0.20, "overshoot": 0.08},
    HumanProfile.FAST:    {"move_speed": 1.6, "typing_speed": 1.4, "delay_mult": 0.6, "jitter": 0.10, "overshoot": 0.04},
}


class BezierCurveGenerator:
    """Organic mouse trajectories via cubic Bezier with randomized control
    points and stochastic overshoot to defeat linear-interpolation detection."""

    def __init__(self, jitter: float = 0.2, overshoot: float = 0.08) -> None:
        self.jitter = jitter
        self.overshoot = overshoot

    def generate(self, start_x: float, start_y: float, end_x: float,
                 end_y: float, duration: float = 0.3,
                 steps: int = 20) -> OrganicMove:
        move_id = secrets.token_hex(8)
        dx, dy = end_x - start_x, end_y - start_y
        dist = math.hypot(dx, dy)
        if dist < 1:
            return OrganicMove(move_id=move_id, start_x=start_x, start_y=start_y,
                               end_x=end_x, end_y=end_y, duration=duration)
        perp = (-dy / dist, dx / dist)
        off = dist * self.jitter * (0.5 + random.random())
        c1 = (start_x + dx * 0.33 + perp[0] * off, start_y + dy * 0.33 + perp[1] * off)
        c2 = (start_x + dx * 0.66 - perp[0] * off * 0.5, start_y + dy * 0.66 - perp[1] * off * 0.5)
        if random.random() < 0.3:
            os_mag = dist * self.overshoot * random.uniform(0.5, 1.5)
            ang = math.atan2(dy, dx) + random.uniform(-0.4, 0.4)
            end_x += math.cos(ang) * os_mag
            end_y += math.sin(ang) * os_mag
        curve: List[BezierPoint] = []
        for i in range(steps):
            t = i / max(steps - 1, 1)
            mt = 1 - t
            x = (mt**3 * start_x + 3 * mt**2 * t * c1[0]
                 + 3 * mt * t**2 * c2[0] + t**3 * end_x)
            y = (mt**3 * start_y + 3 * mt**2 * t * c1[1]
                 + 3 * mt * t**2 * c2[1] + t**3 * end_y)
            curve.append(BezierPoint(x=x, y=y, t=t))
        return OrganicMove(move_id=move_id, start_x=start_x, start_y=start_y,
                           end_x=end_x, end_y=end_y, duration=duration,
                           curve=curve, jitter=self.jitter, overshoot=self.overshoot)

    def sample(self, move: OrganicMove, t: float) -> Tuple[float, float]:
        t = max(0.0, min(1.0, t))
        for i in range(len(move.curve) - 1):
            if move.curve[i].t <= t <= move.curve[i + 1].t:
                a, b = move.curve[i], move.curve[i + 1]
                span = b.t - a.t
                if span <= 0:
                    return a.x, a.y
                lt = (t - a.t) / span
                return a.x + (b.x - a.x) * lt, a.y + (b.y - a.y) * lt
        if move.curve:
            return move.curve[-1].x, move.curve[-1].y
        return move.end_x, move.end_y


class StochasticDelayEngine:
    """Applies human-like reaction-time jitter to inter-action delays so that
    the automation cadence does not match a fixed machine rhythm."""

    def __init__(self, profile: HumanProfile = HumanProfile.NORMAL,
                 base_delay: float = 0.15) -> None:
        self.profile = profile
        self.base_delay = base_delay
        self._cfg = _DEFAULT_PROFILES[profile]
        self._history: List[StochasticTiming] = []

    def next_delay(self, action_type: str = "click",
                   min_delay: float = 0.02) -> StochasticTiming:
        mult = self._cfg["delay_mult"]
        jitter = self._cfg["jitter"]
        base = max(min_delay, self.base_delay * mult)
        # Log-normal-ish jitter: multiplicative factor in [1-jitter, 1+jitter]
        factor = random.uniform(1 - jitter, 1 + jitter)
        actual = base * factor
        timing = StochasticTiming(base_delay=base, actual_delay=actual,
                                  jitter_applied=factor - 1.0)
        self._history.append(timing)
        if len(self._history) > 200:
            self._history = self._history[-200:]
        return timing

    def mean_delay(self) -> float:
        if not self._history:
            return self.base_delay
        return sum(t.actual_delay for t in self._history) / len(self._history)

    def jitter_range(self) -> Tuple[float, float]:
        if len(self._history) < 2:
            return 0.0, 0.0
        delays = [t.actual_delay for t in self._history]
        return min(delays), max(delays)


class StealthActionExecutor:
    """Wraps OS-level automation actions with organic timing, human-like
    trajectories and anti-detection heuristics before dispatching them."""

    def __init__(self, os_controller: Any = None,
                 profile: HumanProfile = HumanProfile.NORMAL) -> None:
        self._os = os_controller
        self.profile = profile
        self._cfg = _DEFAULT_PROFILES[profile]
        self.bezier = BezierCurveGenerator(jitter=self._cfg["jitter"],
                                           overshoot=self._cfg["overshoot"])
        self.delayer = StochasticDelayEngine(profile=profile)
        self._actions: List[Dict[str, Any]] = []
        self._lock = threading.Lock()

    def set_os_controller(self, os_controller: Any) -> None:
        self._os = os_controller

    async def move(self, x: float, y: float, from_x: float = 0.0,
                   from_y: float = 0.0) -> Dict[str, Any]:
        move = self.bezier.generate(from_x, from_y, x, y)
        steps = max(4, len(move.curve))
        delay = move.duration / steps
        for i, pt in enumerate(move.curve):
            if self._os is not None:
                try:
                    await self._os.dispatch(OSAction(action_type=OSActionType.MOVE,
                                                     coordinates=(pt.x, pt.y)))
                except Exception as exc:
                    logger.debug("move step failed: %s", exc)
            await asyncio.sleep(delay)
        self._record("move", {"x": x, "y": y, "move_id": move.move_id})
        return {"status": "ok", "move_id": move.move_id, "steps": steps}

    async def click(self, x: float, y: float, button: str = "left",
                    double: bool = False) -> Dict[str, Any]:
        await self._wait("click")
        action = OSAction(action_type=OSActionType.DOUBLE_CLICK if double
                          else OSActionType.CLICK,
                          coordinates=(x, y))
        ok = await self._dispatch(action)
        self._record("click", {"x": x, "y": y, "button": button, "double": double})
        return {"status": "ok" if ok else "error", "pos": [x, y]}

    async def type_text(self, text: str, interval: float = 0.05) -> Dict[str, Any]:
        per_char = interval * self._cfg["typing_speed"]
        for ch in text:
            await self._wait("type")
            await self._dispatch(OSAction(action_type=OSActionType.TYPE, text=ch))
            await asyncio.sleep(per_char)
        self._record("type", {"chars": len(text)})
        return {"status": "ok", "chars": len(text)}

    async def keypress(self, key: str) -> Dict[str, Any]:
        await self._wait("keypress")
        await self._dispatch(OSAction(action_type=OSActionType.KEYPRESS, key=key))
        self._record("keypress", {"key": key})
        return {"status": "ok", "key": key}

    async def scroll(self, amount: int, x: float = 0.0, y: float = 0.0) -> Dict[str, Any]:
        await self._wait("scroll")
        await self._dispatch(OSAction(action_type=OSActionType.SCROLL,
                                      scroll_amount=amount, coordinates=(x, y)))
        self._record("scroll", {"amount": amount})
        return {"status": "ok", "amount": amount}

    async def _wait(self, action_type: str) -> None:
        timing = self.delayer.next_delay(action_type)
        await asyncio.sleep(timing.actual_delay)

    async def _dispatch(self, action: OSAction) -> bool:
        if self._os is None:
            return False
        try:
            return await self._os.dispatch(action)
        except Exception as exc:
            logger.debug("dispatch failed: %s", exc)
            return False

    def _record(self, kind: str, payload: Dict[str, Any]) -> None:
        with self._lock:
            self._actions.append({"kind": kind, "payload": payload,
                                  "ts": time.time()})
            if len(self._actions) > 500:
                self._actions = self._actions[-500:]

    def recent_actions(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._actions[-limit:])

    def movement_stats(self) -> Dict[str, Any]:
        moves = [a for a in self._actions if a["kind"] == "move"]
        return {
            "total_actions": len(self._actions),
            "moves": len(moves),
            "profile": self.profile.value,
            "mean_delay": round(self.delayer.mean_delay(), 4),
            "jitter_range": [round(v, 4) for v in self.delayer.jitter_range()],
        }


@dataclass
class MacroStep:
    action: str
    params: Dict[str, Any] = field(default_factory=dict)
    sleep_after: float = 0.0


class StealthMacroRunner:
    """Executes a sequence of stealth actions as a scripted macro, applying
    per-step stochastic delays and organic motion so the whole sequence does
    not look batched."""

    def __init__(self, executor: StealthActionExecutor) -> None:
        self.executor = executor
        self._macros: Dict[str, List[MacroStep]] = {}
        self._history: List[Dict[str, Any]] = []

    def register(self, name: str, steps: List[Dict[str, Any]]) -> None:
        parsed = [MacroStep(action=s.get("action", "click"),
                            params=s.get("params", {}),
                            sleep_after=s.get("sleep_after", 0.0))
                   for s in steps]
        self._macros[name] = parsed

    async def run(self, name: str, **kwargs: Any) -> Dict[str, Any]:
        steps = self._macros.get(name)
        if not steps:
            return {"status": "error", "error": f"macro '{name}' not found"}
        started = time.time()
        results: List[Dict[str, Any]] = []
        for idx, step in enumerate(steps):
            try:
                res = await self._execute_step(step, kwargs)
                results.append(res)
            except Exception as exc:
                results.append({"status": "error", "error": str(exc)})
                break
            if step.sleep_after > 0:
                await asyncio.sleep(step.sleep_after)
        entry = {"macro": name, "started": started, "duration": time.time() - started,
                 "steps": len(steps), "results": results}
        self._history.append(entry)
        if len(self._history) > 200:
            self._history = self._history[-200:]
        return {"status": "ok", "entry": entry}

    async def _execute_step(self, step: MacroStep,
                            ctx: Dict[str, Any]) -> Dict[str, Any]:
        action = step.action
        params = {**step.params, **ctx}
        if action == "move":
            return await self.executor.move(float(params.get("x", 0)),
                                            float(params.get("y", 0)),
                                            float(params.get("from_x", 0)),
                                            float(params.get("from_y", 0)))
        if action == "click":
            return await self.executor.click(float(params.get("x", 0)),
                                             float(params.get("y", 0)),
                                             params.get("button", "left"),
                                             bool(params.get("double", False)))
        if action == "type":
            return await self.executor.type_text(str(params.get("text", "")))
        if action == "keypress":
            return await self.executor.keypress(str(params.get("key", "")))
        if action == "scroll":
            return await self.executor.scroll(int(params.get("amount", 0)))
        return {"status": "error", "error": f"unknown action {action}"}

    def history(self, limit: int = 50) -> List[Dict[str, Any]]:
        return list(self._history[-limit:])

    def list_macros(self) -> List[str]:
        return list(self._macros.keys())


# --------------------------------------------------------------------------- #
# REST routes
# --------------------------------------------------------------------------- #

try:
    from fastapi import APIRouter, HTTPException
    from pydantic import BaseModel

    router = APIRouter(prefix="/api/automation/organic", tags=["automation", "stealth"])

    _executor = StealthActionExecutor()
    _runner = StealthMacroRunner(_executor)

    class MoveRequest(BaseModel):
        x: float
        y: float
        from_x: float = 0.0
        from_y: float = 0.0

    class ClickRequest(BaseModel):
        x: float
        y: float
        button: str = "left"
        double: bool = False

    class TypeRequest(BaseModel):
        text: str
        interval: float = 0.05

    class KeypressRequest(BaseModel):
        key: str

    class ScrollRequest(BaseModel):
        amount: int
        x: float = 0.0
        y: float = 0.0

    class MacroRegisterRequest(BaseModel):
        name: str
        steps: List[Dict[str, Any]]

    class MacroRunRequest(BaseModel):
        name: str

    @router.get("/profile")
    async def get_profile() -> Dict[str, Any]:
        return {"profile": _executor.profile.value,
                "cfg": _DEFAULT_PROFILES[_executor.profile]}

    @router.post("/profile/{profile}")
    async def set_profile(profile: str) -> Dict[str, Any]:
        try:
            p = HumanProfile(profile)
        except ValueError:
            raise HTTPException(status_code=400, detail="invalid profile")
        cfg = _DEFAULT_PROFILES[p]
        _executor.profile = p
        _executor._cfg = cfg
        _executor.bezier = BezierCurveGenerator(jitter=cfg["jitter"], overshoot=cfg["overshoot"])
        _executor.delayer = StochasticDelayEngine(profile=p)
        return {"status": "ok", "profile": p.value}

    @router.post("/move")
    async def post_move(req: MoveRequest) -> Dict[str, Any]:
        return await _executor.move(req.x, req.y, req.from_x, req.from_y)

    @router.post("/click")
    async def post_click(req: ClickRequest) -> Dict[str, Any]:
        return await _executor.click(req.x, req.y, req.button, req.double)

    @router.post("/type")
    async def post_type(req: TypeRequest) -> Dict[str, Any]:
        return await _executor.type_text(req.text, req.interval)

    @router.post("/keypress")
    async def post_keypress(req: KeypressRequest) -> Dict[str, Any]:
        return await _executor.keypress(req.key)

    @router.post("/scroll")
    async def post_scroll(req: ScrollRequest) -> Dict[str, Any]:
        return await _executor.scroll(req.amount, req.x, req.y)

    @router.post("/macro/register")
    async def post_register_macro(req: MacroRegisterRequest) -> Dict[str, Any]:
        _runner.register(req.name, req.steps)
        return {"status": "ok", "name": req.name}

    @router.post("/macro/run")
    async def post_run_macro(req: MacroRunRequest) -> Dict[str, Any]:
        return await _runner.run(req.name)

    @router.get("/macro")
    async def list_macros() -> Dict[str, Any]:
        return {"macros": _runner.list_macros()}

    @router.get("/macro/history")
    async def macro_history(limit: int = 20) -> Dict[str, Any]:
        return {"history": _runner.history(limit)}

    @router.get("/stats")
    async def movement_stats() -> Dict[str, Any]:
        return _executor.movement_stats()

    @router.get("/actions")
    async def recent_actions(limit: int = 50) -> Dict[str, Any]:
        return {"actions": _executor.recent_actions(limit)}

except Exception as exc:  # pragma: no cover
    logger.warning("stealth routes skipped: %s", exc)
    router = None  # type: ignore


_stealth_executor: Optional[StealthActionExecutor] = None
_stealth_runner: Optional[StealthMacroRunner] = None


def get_stealth_executor() -> Optional[StealthActionExecutor]:
    global _stealth_executor
    if _stealth_executor is None:
        _stealth_executor = StealthActionExecutor()
    return _stealth_executor


def get_stealth_runner() -> Optional[StealthMacroRunner]:
    global _stealth_runner
    if _stealth_runner is None:
        _stealth_runner = StealthMacroRunner(get_stealth_executor())
    return _stealth_runner


def get_stealth_controller() -> Tuple[Optional[StealthActionExecutor],
                                       Optional[StealthMacroRunner]]:
    return get_stealth_executor(), get_stealth_runner()


__all__ = [
    "BezierCurveGenerator",
    "BezierPoint",
    "HumanProfile",
    "MacroStep",
    "OrganicMove",
    "StealthActionExecutor",
    "StealthMacroRunner",
    "StochasticDelayEngine",
    "StochasticTiming",
    "get_stealth_controller",
    "get_stealth_executor",
    "get_stealth_runner",
]