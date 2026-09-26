"""AURA Local Agentic Memory & Experience Reinforcement Engine (Bloque 57)."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from backend.services.memory_engine import MemoryEngine, MemoryRecord

logger = logging.getLogger("AURA.Agent.MemoryStore")


class TraceOutcome(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    CORRECTED = "corrected"
    PARTIAL = "partial"


@dataclass
class ExecutionTrace:
    trace_id: str
    task_id: str
    objective: str
    outcome: TraceOutcome
    steps: List[Dict[str, Any]] = field(default_factory=list)
    error: str = ""
    correction: str = ""
    duration_ms: float = 0.0
    created_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "task_id": self.task_id,
            "objective": self.objective,
            "outcome": self.outcome.value,
            "steps": self.steps,
            "error": self.error,
            "correction": self.correction,
            "duration_ms": self.duration_ms,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }


class AgentMemoryStore:
    """Episodic memory store for agent execution traces."""

    def __init__(self, memory_engine: Optional[MemoryEngine] = None, trace_dir: Optional[str] = None) -> None:
        self._lock = threading.Lock()
        self._engine = memory_engine or MemoryEngine()
        self._traces: Dict[str, ExecutionTrace] = {}
        self._trace_dir = Path(trace_dir or os.getenv("AURA_TRACE_DIR", os.path.join("data", "agent_traces")))
        self._trace_dir.mkdir(parents=True, exist_ok=True)
        self._load_traces()

    def _load_traces(self) -> None:
        try:
            for f in sorted(self._trace_dir.glob("*.json")):
                try:
                    data = json.loads(f.read_text(encoding="utf-8"))
                    self._restore_trace(data)
                except Exception as exc:
                    logger.debug("skip corrupt trace %s: %s", f.name, exc)
        except Exception as exc:
            logger.debug("trace dir load failed: %s", exc)

    def _restore_trace(self, data: Dict[str, Any]) -> None:
        try:
            outcome = TraceOutcome(str(data.get("outcome", "partial")))
        except ValueError:
            outcome = TraceOutcome.PARTIAL
        trace = ExecutionTrace(
            trace_id=str(data.get("trace_id", "")),
            task_id=str(data.get("task_id", "")),
            objective=str(data.get("objective", "")),
            outcome=outcome,
            steps=list(data.get("steps", []) or []),
            error=str(data.get("error", "")),
            correction=str(data.get("correction", "")),
            duration_ms=float(data.get("duration_ms", 0.0)),
            created_at=float(data.get("created_at", time.time())),
            metadata=dict(data.get("metadata", {}) or {}),
        )
        self._traces[trace.trace_id] = trace

    def _trace_file(self, trace_id: str) -> Path:
        safe = re.sub(r"[^A-Za-z0-9_-]", "_", trace_id)[:64] or "trace"
        return self._trace_dir / f"{safe}.json"

    def _save_trace(self, trace: ExecutionTrace) -> None:
        try:
            self._trace_file(trace.trace_id).write_text(
                json.dumps(trace.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.debug("trace persist failed %s: %s", trace.trace_id, exc)

    def record_trace(self, trace: ExecutionTrace) -> str:
        with self._lock:
            self._traces[trace.trace_id] = trace
            self._save_trace(trace)
            self._index_trace(trace)
        return trace.trace_id

    def _index_trace(self, trace: ExecutionTrace) -> None:
        try:
            text = self._trace_to_text(trace)
            metadata = {
                "trace_id": trace.trace_id,
                "task_id": trace.task_id,
                "outcome": trace.outcome.value,
                "objective": trace.objective,
                "error": trace.error,
                "correction": trace.correction,
                "duration_ms": trace.duration_ms,
                "kind": "agent_trace",
            }
            self._engine.remember(
                text=text,
                memory_type="episodic",
                source="agent",
                session_id=trace.task_id,
                metadata=metadata,
            )
        except Exception as exc:
            logger.debug("trace index failed: %s", exc)

    def _trace_to_text(self, trace: ExecutionTrace) -> str:
        parts = [f"Objetivo: {trace.objective}"]
        parts.append(f"Resultado: {trace.outcome.value}")
        if trace.error:
            parts.append(f"Error: {trace.error}")
        if trace.correction:
            parts.append(f"Correccion: {trace.correction}")
        for s in trace.steps[:10]:
            tool = s.get("tool", "")
            action = s.get("action", "")
            status = ""
            res = s.get("result") or {}
            if isinstance(res, dict):
                status = res.get("status", "")
            parts.append(f"Paso: {action} [{tool}] -> {status}")
        return " | ".join(parts)

    def get_trace(self, trace_id: str) -> Optional[ExecutionTrace]:
        return self._traces.get(trace_id)

    def list_traces(
        self,
        outcome: Optional[str] = None,
        task_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        with self._lock:
            traces = list(self._traces.values())
        if outcome:
            traces = [t for t in traces if t.outcome.value == outcome]
        if task_id:
            traces = [t for t in traces if t.task_id == task_id]
        traces.sort(key=lambda t: t.created_at, reverse=True)
        return [t.to_dict() for t in traces[:limit]]

    def count(self) -> int:
        return len(self._traces)

    def search_experiences(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        try:
            result = self._engine.search(query, max_results=max_results, min_relevance=0.2)
            experiences = []
            for mem in result.get("results", []):
                meta = mem.get("metadata") or {}
                if meta.get("kind") != "agent_trace":
                    continue
                experiences.append({
                    "memory_id": mem.get("memory_id"),
                    "text": mem.get("text"),
                    "score": mem.get("relevance_score", 0.0),
                    "outcome": meta.get("outcome"),
                    "objective": meta.get("objective"),
                    "error": meta.get("error"),
                    "correction": meta.get("correction"),
                    "trace_id": meta.get("trace_id"),
                })
            return experiences
        except Exception as exc:
            logger.debug("experience search failed: %s", exc)
            return []

    def build_few_shot_context(self, query: str, max_results: int = 3) -> str:
        experiences = self.search_experiences(query, max_results=max_results)
        if not experiences:
            return ""
        lines: List[str] = ["Experiencias previas similares:"]
        for i, exp in enumerate(experiences, 1):
            lines.append(f"{i}. Objetivo: {exp.get('objective', '')}")
            if exp.get("outcome"):
                lines.append(f"   Resultado: {exp['outcome']}")
            if exp.get("error"):
                lines.append(f"   Error: {exp['error']}")
            if exp.get("correction"):
                lines.append(f"   Correccion: {exp['correction']}")
        return "\n".join(lines)

    def get_status(self) -> Dict[str, Any]:
        outcomes: Dict[str, int] = {}
        for t in self._traces.values():
            outcomes[t.outcome.value] = outcomes.get(t.outcome.value, 0) + 1
        return {
            "total_traces": len(self._traces),
            "outcomes": outcomes,
            "trace_dir": str(self._trace_dir),
        }


_agent_memory: Optional[AgentMemoryStore] = None


def get_agent_memory() -> AgentMemoryStore:
    global _agent_memory
    if _agent_memory is None:
        _agent_memory = AgentMemoryStore()
    return _agent_memory


def reset_agent_memory() -> None:
    global _agent_memory
    _agent_memory = None