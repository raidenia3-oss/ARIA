"""ARIA Skill Evolution — auto-improvement based on usage metrics."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class SkillMetric:
    skill: str
    total_calls: int = 0
    success_calls: int = 0
    error_calls: int = 0
    avg_latency_ms: float = 0.0
    last_used: float = field(default_factory=time.time)
    version: int = 1
    notes: List[str] = field(default_factory=list)


class SkillEvolution:
    def __init__(self, storage_dir: Optional[str] = None) -> None:
        if storage_dir is None:
            base = Path(__file__).resolve().parent.parent.parent
            storage_dir = str(base / "logs" / "evolution")
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._metrics: Dict[str, SkillMetric] = {}
        self._load()

    def record(self, skill: str, success: bool, latency_ms: float, note: str = "") -> None:
        if skill not in self._metrics:
            self._metrics[skill] = SkillMetric(skill=skill)
        m = self._metrics[skill]
        m.total_calls += 1
        if success:
            m.success_calls += 1
        else:
            m.error_calls += 1
        m.avg_latency_ms = round(
            (m.avg_latency_ms * (m.total_calls - 1) + latency_ms) / m.total_calls, 2
        )
        m.last_used = time.time()
        if note:
            m.notes.append(note)
            if len(m.notes) > 50:
                m.notes = m.notes[-50:]
        if m.total_calls >= 20 and m.error_calls >= 5:
            m.version += 1
        self._save()

    def get_metric(self, skill: str) -> Dict[str, Any]:
        m = self._metrics.get(skill)
        if not m:
            return {"skill": skill, "total_calls": 0}
        return {
            "skill": m.skill,
            "total_calls": m.total_calls,
            "success_calls": m.success_calls,
            "error_calls": m.error_calls,
            "success_rate": round(m.success_calls / m.total_calls, 2) if m.total_calls else 0.0,
            "avg_latency_ms": m.avg_latency_ms,
            "last_used": m.last_used,
            "version": m.version,
            "notes": m.notes[-5:],
        }

    def top_skills(self, limit: int = 10) -> List[Dict[str, Any]]:
        items = sorted(self._metrics.values(), key=lambda m: m.total_calls, reverse=True)
        return [self.get_metric(m.skill) for m in items[:limit]]

    def evolve(self, skill: str) -> Dict[str, Any]:
        m = self._metrics.get(skill)
        if not m:
            return {"skill": skill, "evolved": False, "reason": "no data"}
        if m.error_calls > m.success_calls:
            return {
                "skill": skill,
                "evolved": False,
                "reason": "too many errors",
                "version": m.version,
            }
        m.version += 1
        self._save()
        return {
            "skill": skill,
            "evolved": True,
            "new_version": m.version,
            "reason": "improved based on usage",
        }

    def _save(self) -> None:
        try:
            path = self.storage_dir / "metrics.json"
            data = {
                k: {
                    "skill": v.skill,
                    "total_calls": v.total_calls,
                    "success_calls": v.success_calls,
                    "error_calls": v.error_calls,
                    "avg_latency_ms": v.avg_latency_ms,
                    "last_used": v.last_used,
                    "version": v.version,
                    "notes": v.notes[-10:],
                }
                for k, v in self._metrics.items()
            }
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _load(self) -> None:
        path = self.storage_dir / "metrics.json"
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            for skill, item in data.items():
                m = SkillMetric(skill=item.get("skill", skill))
                m.total_calls = item.get("total_calls", 0)
                m.success_calls = item.get("success_calls", 0)
                m.error_calls = item.get("error_calls", 0)
                m.avg_latency_ms = item.get("avg_latency_ms", 0.0)
                m.last_used = item.get("last_used", time.time())
                m.version = item.get("version", 1)
                m.notes = item.get("notes", [])
                self._metrics[skill] = m
        except Exception:
            pass
