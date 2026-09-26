"""BLOQUE 92 - AURA Local Hierarchical Task Decomposition & Long-Horizon Goal Planning Engine."""
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from backend.planner.models import (
    GoalNode,
    GoalStatus,
    Milestone,
    MilestoneStatus,
    PlanEvent,
)

DATA_DIR = Path(os.getenv("AURA_PLANNER_DIR", os.path.join(os.getcwd(), "data", "planner")))
for _sub in ("goals", "plans", "logs"):
    (DATA_DIR / _sub).mkdir(parents=True, exist_ok=True)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _now_ts() -> float:
    return time.time()


def _gen_id(prefix: str = "gl") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"



def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _now_ts() -> float:
    return time.time()


def _gen_id(prefix: str = "gl") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _topological_sort(goals: Dict[str, GoalNode]) -> List[str]:
    """Orden topologico para ejecutar goals respetando dependencias (DAG)."""
    in_degree: Dict[str, int] = defaultdict(int)
    adj: Dict[str, List[str]] = defaultdict(list)
    for gid, g in goals.items():
        for dep in g.dependencies:
            adj[dep].append(gid)
            in_degree[gid] += 1
        if gid not in in_degree:
            in_degree[gid] = 0
    queue = [gid for gid, deg in in_degree.items() if deg == 0]
    result = []
    while queue:
        node = queue.pop(0)
        result.append(node)
        for neighbor in adj[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)
    if len(result) != len(goals):
        return []
    return result


def _detect_cycles(goals: Dict[str, GoalNode]) -> List[List[str]]:
    """Detecta ciclos usando DFS."""
    WHITE, GRAY, BLACK = 0, 1, 2
    color: Dict[str, int] = {gid: WHITE for gid in goals}
    cycles = []

    def dfs(node: str, path: List[str]) -> None:
        if node not in goals:
            return
        color[node] = GRAY
        path.append(node)
        for dep in goals[node].dependencies:
            if dep not in goals:
                continue
            if color[dep] == GRAY:
                cycle_start = path.index(dep)
                cycles.append(path[cycle_start:] + [dep])
            elif color[dep] == WHITE:
                dfs(dep, path)
        path.pop()
        color[node] = BLACK

    for gid in goals:
        if color[gid] == WHITE:
            dfs(gid, [])
    return cycles


class HierarchicalGoalDecomposer:
    """Motor 100% local de descomposicion jerarquica de intenciones."""

    def __init__(self) -> None:
        self.goals: Dict[str, GoalNode] = {}
        self.events: List[PlanEvent] = []
        self._lock = threading.RLock()
        self._load()

    def _load(self) -> None:
        path = DATA_DIR / "goals" / "goals.json"
        if not path.exists():
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for g in data.get("goals", []):
                g = dict(g)
                g["milestones"] = [Milestone(**m) for m in g.get("milestones", [])]
                self.goals[g["goal_id"]] = GoalNode(**g)
            self.events = [PlanEvent(**e) for e in data.get("events", [])]
        except Exception:
            pass

    def _save(self) -> None:
        try:
            path = DATA_DIR / "goals" / "goals.json"
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"goals": [g.to_dict() for g in self.goals.values()],
                           "events": [e.to_dict() for e in self.events]}, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _emit(self, goal_id: str, kind: str, message: str, **kw: Any) -> None:
        ev = PlanEvent(event_id=_gen_id("ev"), goal_id=goal_id, kind=kind, message=message, metadata=kw)
        self.events.append(ev)
        self._save()

    def decompose(self, title: str, description: str = "", parent_id: Optional[str] = None,
                  milestones: Optional[List[Dict[str, Any]]] = None,
                  priority: int = 0, deadline: Optional[str] = None) -> GoalNode:
        with self._lock:
            gid = _gen_id("goal")
            ms: List[Milestone] = []
            if milestones:
                for i, m in enumerate(milestones or []):
                    ms.append(Milestone(milestone_id=_gen_id("ms"),
                                        title=m.get("title", "Milestone " + str(i)),
                                        description=m.get("description", ""),
                                        depends_on=m.get("depends_on", []),
                                        goal_id=gid))
            g = GoalNode(goal_id=gid, title=title, description=description, parent_id=parent_id,
                         priority=priority, milestones=ms, deadline=deadline)
            self.goals[gid] = g
            if parent_id and parent_id in self.goals:
                self.goals[parent_id].children.append(gid)
            self._save()
            self._emit(gid, "goal_created", title)
            return g

    def get_goal(self, goal_id: str) -> Optional[GoalNode]:
        return self.goals.get(goal_id)

    def list_goals(self, root_only: bool = False) -> List[GoalNode]:
        with self._lock:
            goals = list(self.goals.values())
            if root_only:
                goals = [g for g in goals if g.parent_id is None]
            return goals

    def update_milestone(self, goal_id: str, milestone_id: str, progress: Optional[float] = None,
                          status: Optional[MilestoneStatus] = None) -> Optional[Milestone]:
        with self._lock:
            g = self.goals.get(goal_id)
            if not g:
                return None
            for m in g.milestones:
                if m.milestone_id == milestone_id:
                    if progress is not None:
                        m.progress = max(0.0, min(100.0, progress))
                    if status is not None:
                        m.status = status
                        if status == MilestoneStatus.DONE:
                            m.progress = 100.0
                            m.completed_at = _utcnow_iso()
                    m.updated_at = _utcnow_iso()
                    self._save()
                    self._emit(goal_id, "milestone_update", m.title, progress=m.progress, status=m.status.value)
                    self._recompute_goal_status(goal_id)
                    return m
            return None

    def _recompute_goal_status(self, goal_id: str) -> None:
        g = self.goals.get(goal_id)
        if not g:
            return
        ms = g.milestones
        if not ms:
            return
        done = sum(1 for m in ms if m.status == MilestoneStatus.DONE)
        blocked = sum(1 for m in ms if m.status == MilestoneStatus.BLOCKED)
        if done == len(ms):
            g.status = GoalStatus.DONE
        elif blocked > 0 and done + blocked == len(ms):
            g.status = GoalStatus.BLOCKED
        else:
            g.status = GoalStatus.IN_PROGRESS
        g.updated_at = _utcnow_iso()

    def check_cycles(self, goal_id: str, target_id: str) -> bool:
        """Devuelve True si target_id es ancestro de goal_id (agregar dependencia goal_id->target_id crearia ciclo)."""
        with self._lock:
            visited = set()
            cur = goal_id
            while cur:
                if cur == target_id:
                    return True
                if cur in visited:
                    return False
                visited.add(cur)
                node = self.goals.get(cur)
                if not node or not node.parent_id:
                    return False
                cur = node.parent_id
            return False

    def replan(self, goal_id: str, reason: str) -> Dict[str, Any]:
        with self._lock:
            g = self.goals.get(goal_id)
            if not g:
                return {"replanned": False, "reason": "goal not found"}
            self._emit(goal_id, "replan", reason)
            return {"replanned": True, "goal_id": goal_id, "reason": reason,
                    "new_status": g.status.value}

    def status(self) -> Dict[str, Any]:
        with self._lock:
            return {"goals_total": len(self.goals),
                    "goals_done": sum(1 for g in self.goals.values() if g.status == GoalStatus.DONE),
                    "goals_in_progress": sum(1 for g in self.goals.values() if g.status == GoalStatus.IN_PROGRESS),
                    "goals_blocked": sum(1 for g in self.goals.values() if g.status == GoalStatus.BLOCKED),
                    "events": len(self.events),
                    "cycles": _detect_cycles(self.goals)}

    def reset(self) -> None:
        with self._lock:
            self.goals = {}
            self.events = []
            path = DATA_DIR / "goals" / "goals.json"
            if path.exists():
                path.unlink()


_global = None


def get_planner():
    global _global
    if _global is None:
        _global = HierarchicalGoalDecomposer()
    return _global


def reset_planner():
    global _global
    if _global is not None:
        _global.reset()
    _global = None
