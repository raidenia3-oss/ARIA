"""BLOQUE 84 - Predictive Intent Analyzer + Proactive Scheduler (parte 1/2)."""
from __future__ import annotations
import threading
import time
import uuid
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
CONFIRM_THRESHOLD = 0.55
AUTO_THRESHOLD = 0.8
VALID_IMPACT = ("low", "medium", "high")
INTENT_SIGNALS = {"rag_precache": ("memory", "network"), "resource_tune": ("hardware", "system"),
    "context_warmup": ("vision", "audio"), "mesh_probe": ("network", "system")}

@dataclass
class IntentHypothesis:
    hypothesis_id: str = ""
    intent: str = ""
    confidence: float = 0.0
    signals: Dict[str, int] = field(default_factory=dict)
    suggested_action: str = ""
    impact: str = "low"
    ts: float = 0.0
    def __post_init__(self) -> None:
        if not self.hypothesis_id:
            self.hypothesis_id = uuid.uuid4().hex[:12]
        if not self.ts:
            self.ts = time.time()
    def to_dict(self) -> Dict[str, Any]:
        return {"hypothesis_id": self.hypothesis_id, "intent": self.intent,
                "confidence": round(self.confidence, 3), "signals": self.signals,
                "suggested_action": self.suggested_action, "impact": self.impact,
                "ts": self.ts, "offline_only": True}

@dataclass
class ProactiveTask:
    task_id: str = ""
    hypothesis_id: str = ""
    action: str = ""
    impact: str = "low"
    status: str = "scheduled"
    result: Optional[Dict[str, Any]] = None
    created_at: float = 0.0
    executed_at: float = 0.0
    def __post_init__(self) -> None:
        if not self.task_id:
            self.task_id = uuid.uuid4().hex[:12]
        if not self.created_at:
            self.created_at = time.time()
    def to_dict(self) -> Dict[str, Any]:
        return {"task_id": self.task_id, "hypothesis_id": self.hypothesis_id,
                "action": self.action, "impact": self.impact, "status": self.status,
                "result": self.result, "created_at": self.created_at,
                "executed_at": self.executed_at, "offline_only": True}

class IntentAnalyzer:
    def analyze(self, source_counts: Dict[str, int], fused_score: float = 0.0, state: str = "nominal") -> List[IntentHypothesis]:
        total = sum(source_counts.values())
        hyps: List[IntentHypothesis] = []
        if total <= 0:
            return hyps
        for intent, wanted in INTENT_SIGNALS.items():
            hits = sum(source_counts.get(s, 0) for s in wanted)
            coverage = hits / max(1, total)
            if coverage <= 0:
                continue
            conf = round(min(0.95, coverage * 0.7 + min(1.0, fused_score / 10.0) * 0.3), 3)
            if conf < CONFIRM_THRESHOLD:
                continue
            impact = "low" if intent in ("rag_precache", "context_warmup") else "medium"
            hyps.append(IntentHypothesis(intent=intent, confidence=conf,
                signals={s: source_counts.get(s, 0) for s in wanted},
                suggested_action=f"run:{intent}", impact=impact))
        hyps.sort(key=lambda h: h.confidence, reverse=True)
        return hyps

class TaskGatekeeper:
    def __init__(self) -> None:
        self._handlers: Dict[str, Callable[..., Dict[str, Any]]] = {}
        self._lock = threading.Lock()
    def register_handler(self, action: str, fn: Callable[..., Dict[str, Any]]) -> None:
        with self._lock:
            self._handlers[action] = fn
    def decide(self, hyp: IntentHypothesis) -> str:
        if hyp.impact == "high":
            return "needs_confirm"
        if hyp.confidence >= AUTO_THRESHOLD:
            return "auto"
        return "needs_confirm"
    def execute(self, task: ProactiveTask) -> ProactiveTask:
        with self._lock:
            fn = self._handlers.get(task.action)
        task.executed_at = time.time()
        if fn is None:
            task.status = "success"
            task.result = {"action": task.action, "noop": True, "offline": True}
            return task
        try:
            task.result = fn(hypothesis_id=task.hypothesis_id)
            task.status = "success"
        except Exception as exc:
            task.status = "error"
            task.result = {"error": str(exc)[:200]}
        return task

class PredictiveEngine:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.analyzer = IntentAnalyzer()
        self.gatekeeper = TaskGatekeeper()
        self._hyps: List[IntentHypothesis] = []
        self._tasks: Dict[str, ProactiveTask] = {}
        self._log: List[Dict[str, Any]] = []
    def observe(self, source_counts: Dict[str, int], fused_score: float = 0.0, state: str = "nominal") -> Dict[str, Any]:
        hyps = self.analyzer.analyze(source_counts, fused_score, state)
        scheduled: List[ProactiveTask] = []
        pending: List[IntentHypothesis] = []
        with self._lock:
            for h in hyps:
                self._hyps.append(h)
            self._hyps = self._hyps[-200:]
        for h in hyps:
            if self.gatekeeper.decide(h) == "auto":
                t = ProactiveTask(hypothesis_id=h.hypothesis_id, action=h.suggested_action, impact=h.impact, status="scheduled")
                with self._lock:
                    self._tasks[t.task_id] = t
                self.gatekeeper.execute(t)
                with self._lock:
                    self._log.append({"task_id": t.task_id, "action": t.action, "status": t.status, "ts": time.time()})
                scheduled.append(t)
            else:
                pending.append(h)
        return {"hypotheses": [h.to_dict() for h in hyps],
                "auto_scheduled": [t.to_dict() for t in scheduled],
                "pending_confirm": [h.to_dict() for h in pending], "offline_only": True}
    def confirm(self, hypothesis_id: str) -> Dict[str, Any]:
        with self._lock:
            hyp = next((h for h in self._hyps if h.hypothesis_id == hypothesis_id), None)
        if hyp is None:
            return {"confirmed": False, "reason": "not found"}
        t = ProactiveTask(hypothesis_id=hyp.hypothesis_id, action=hyp.suggested_action, impact=hyp.impact, status="scheduled")
        with self._lock:
            self._tasks[t.task_id] = t
        self.gatekeeper.execute(t)
        with self._lock:
            self._log.append({"task_id": t.task_id, "action": t.action, "status": t.status, "ts": time.time(), "confirmed": True})
        return {"confirmed": True, "task": t.to_dict()}
    def tasks(self, limit: int = 50) -> List[ProactiveTask]:
        with self._lock:
            return list(self._tasks.values())[-limit:]
    def hypotheses(self, limit: int = 50) -> List[IntentHypothesis]:
        with self._lock:
            return list(self._hyps[-limit:])
    def ledger(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._log[-limit:])
    def reset(self) -> None:
        with self._lock:
            self._hyps.clear(); self._tasks.clear(); self._log.clear()

_global_pred: Optional[PredictiveEngine] = None
_pred_lock = threading.Lock()

def get_predictive_engine() -> PredictiveEngine:
    global _global_pred
    with _pred_lock:
        if _global_pred is None:
            _global_pred = PredictiveEngine()
        return _global_pred

def reset_predictive_engine() -> None:
    global _global_pred
    with _pred_lock:
        _global_pred = None
