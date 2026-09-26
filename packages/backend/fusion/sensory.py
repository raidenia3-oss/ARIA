"""BLOQUE 83 - Multi-Modal Sensory Fusion & Contextual Awareness Engine (parte 1/2)."""
from __future__ import annotations
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
VALID_SOURCES = ("vision", "audio", "hardware", "memory", "network", "system")
VALID_SEVERITIES = ("info", "low", "medium", "high", "critical")
_SEV_WEIGHT = {"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
SOURCE_WEIGHT = {"vision": 1.0, "audio": 1.0, "hardware": 1.2, "memory": 1.1, "network": 1.1, "system": 0.8}
CRITICAL_THRESHOLD = 6.0
ANOMALY_THRESHOLD = 9.0

@dataclass
class SensorEvent:
    event_id: str = ""
    source: str = "system"
    kind: str = "generic"
    payload: Dict[str, Any] = field(default_factory=dict)
    severity: str = "info"
    ts: float = 0.0
    def __post_init__(self) -> None:
        if not self.event_id:
            self.event_id = uuid.uuid4().hex[:12]
        if self.source not in VALID_SOURCES:
            raise ValueError(f"fuente no soportada: {self.source}")
        if self.severity not in VALID_SEVERITIES:
            raise ValueError(f"severidad no soportada: {self.severity}")
        if not self.ts:
            self.ts = time.time()
    def to_dict(self) -> Dict[str, Any]:
        return {"event_id": self.event_id, "source": self.source, "kind": self.kind,
                "payload": self.payload, "severity": self.severity, "ts": self.ts, "offline_only": True}
    def score(self) -> float:
        return _SEV_WEIGHT[self.severity] * SOURCE_WEIGHT.get(self.source, 1.0)

@dataclass
class ContextSnapshot:
    snapshot_id: str = ""
    ts: float = 0.0
    window_s: float = 30.0
    event_count: int = 0
    sources: Dict[str, int] = field(default_factory=dict)
    fused_score: float = 0.0
    state: str = "nominal"
    anomalies: List[str] = field(default_factory=list)
    top_events: List[Dict[str, Any]] = field(default_factory=list)
    def to_dict(self) -> Dict[str, Any]:
        return {"snapshot_id": self.snapshot_id, "ts": self.ts, "window_s": self.window_s,
                "event_count": self.event_count, "sources": self.sources,
                "fused_score": round(self.fused_score, 3), "state": self.state,
                "anomalies": self.anomalies, "top_events": self.top_events, "offline_only": True}

class SensoryBus:
    def __init__(self, capacity: int = 2000) -> None:
        self._lock = threading.Lock()
        self._events: deque = deque(maxlen=max(64, capacity))
        self._subs: List[Callable[[SensorEvent], None]] = []
    def publish(self, event: SensorEvent) -> SensorEvent:
        with self._lock:
            self._events.append(event)
            subs = list(self._subs)
        for cb in subs:
            try:
                cb(event)
            except Exception:
                pass
        return event
    def subscribe(self, cb: Callable[[SensorEvent], None]) -> None:
        with self._lock:
            self._subs.append(cb)
    def window(self, window_s: float = 30.0, limit: int = 200) -> List[SensorEvent]:
        cutoff = time.time() - max(0.0, window_s)
        with self._lock:
            items = [e for e in self._events if e.ts >= cutoff]
        items.sort(key=lambda e: e.ts)
        return items[-limit:]
    def clear(self) -> int:
        with self._lock:
            n = len(self._events)
            self._events.clear()
            return n
    def __len__(self) -> int:
        with self._lock:
            return len(self._events)

class ContextEvaluator:
    def evaluate(self, events: List[SensorEvent], window_s: float = 30.0) -> ContextSnapshot:
        now = time.time()
        sources: Dict[str, int] = {}
        score = 0.0
        anomalies: List[str] = []
        for e in events:
            sources[e.source] = sources.get(e.source, 0) + 1
            score += e.score()
        crit = [e for e in events if e.severity == "critical"]
        if crit:
            anomalies.append(f"{len(crit)} evento(s) critico(s) en ventana")
        by_src = sorted(sources.items(), key=lambda kv: kv[1], reverse=True)
        if by_src and by_src[0][1] >= max(5, len(events) * 0.7) and len(events) >= 5:
            anomalies.append(f"rafaga dominante de '{by_src[0][0]}' ({by_src[0][1]}/{len(events)})")
        if score >= ANOMALY_THRESHOLD:
            state = "anomaly"
        elif score >= CRITICAL_THRESHOLD:
            state = "alert"
        elif score > 0:
            state = "active"
        else:
            state = "nominal"
        top = sorted(events, key=lambda e: (e.score(), e.ts), reverse=True)[:5]
        return ContextSnapshot(snapshot_id=uuid.uuid4().hex[:12], ts=now, window_s=window_s,
            event_count=len(events), sources=sources, fused_score=round(score, 3),
            state=state, anomalies=anomalies, top_events=[e.to_dict() for e in top])

class FusionEngine:
    def __init__(self, capacity: int = 2000) -> None:
        self._lock = threading.Lock()
        self.bus = SensoryBus(capacity=capacity)
        self.evaluator = ContextEvaluator()
        self._history: List[ContextSnapshot] = []
        self._last: Optional[ContextSnapshot] = None
    def ingest(self, source: str, kind: str = "generic", payload: Optional[Dict[str, Any]] = None, severity: str = "info", ts: float = 0.0) -> SensorEvent:
        ev = SensorEvent(source=source, kind=kind, payload=payload or {}, severity=severity, ts=ts or time.time())
        return self.bus.publish(ev)
    def snapshot(self, window_s: float = 30.0) -> ContextSnapshot:
        snap = self.evaluator.evaluate(self.bus.window(window_s=window_s), window_s=window_s)
        with self._lock:
            self._last = snap
            self._history.append(snap)
            if len(self._history) > 200:
                self._history = self._history[-200:]
        return snap
    def last(self) -> Optional[ContextSnapshot]:
        with self._lock:
            return self._last
    def history(self, limit: int = 20) -> List[ContextSnapshot]:
        with self._lock:
            return list(self._history[-limit:])
    def reset(self) -> Dict[str, int]:
        n_events = self.bus.clear()
        with self._lock:
            n_snaps = len(self._history)
            self._history.clear()
            self._last = None
        return {"events_cleared": n_events, "snapshots_cleared": n_snaps}

_global_fusion: Optional[FusionEngine] = None
_fusion_lock = threading.Lock()

def get_fusion_engine() -> FusionEngine:
    global _global_fusion
    with _fusion_lock:
        if _global_fusion is None:
            _global_fusion = FusionEngine()
        return _global_fusion

def reset_fusion_engine() -> None:
    global _global_fusion
    with _fusion_lock:
        _global_fusion = None
