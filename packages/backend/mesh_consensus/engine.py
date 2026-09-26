"""BLOQUE 89 - Consensus engine + negotiation broker (local)."""
from __future__ import annotations

import threading
import time
import uuid
from typing import Any, Callable, Dict, List, Optional

from backend.mesh_consensus.core import (
    DEFAULT_TTL_S, MAX_ROUNDS, QUORUM_RATIO, ConsensusRound,
)


class SwarmConsensusEngine:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._rounds: Dict[str, ConsensusRound] = {}
        self._tasks: Dict[str, Dict[str, Any]] = {}
        self._watchers: List[Callable[[Dict[str, Any]], None]] = []

    def on_event(self, cb: Callable[[Dict[str, Any]], None]) -> None:
        with self._lock:
            self._watchers.append(cb)

    def _emit(self, evt: Dict[str, Any]) -> None:
        with self._lock:
            cbs = list(self._watchers)
        for cb in cbs:
            try:
                cb(evt)
            except Exception:
                pass

    def open_round(self, topic: str, proposal: str,
                   voters: List[str], ttl_s: float = DEFAULT_TTL_S) -> ConsensusRound:
        if not topic.strip() or not proposal.strip():
            raise ValueError("topic/proposal vacios")
        if not voters:
            raise ValueError("se requiere al menos 1 votante")
        rnd = ConsensusRound(topic=topic.strip(), proposal=proposal.strip(),
                             voters=list(dict.fromkeys(voters))[:50], ttl_s=ttl_s)
        with self._lock:
            self._rounds[rnd.round_id] = rnd
            if len(self._rounds) > MAX_ROUNDS:
                old = sorted(self._rounds.values(), key=lambda r: r.created_at)
                for r in old[: len(self._rounds) - MAX_ROUNDS]:
                    del self._rounds[r.round_id]
        self._emit({"type": "round_opened", **rnd.to_dict()})
        return rnd

    def vote(self, round_id: str, voter: str, choice: str) -> Dict[str, Any]:
        with self._lock:
            rnd = self._rounds.get(round_id)
        if rnd is None:
            return {"voted": False, "reason": "not found"}
        if rnd.status != "open":
            return {"voted": False, "reason": f"round {rnd.status}"}
        if voter not in rnd.voters:
            return {"voted": False, "reason": "not a voter"}
        if choice not in ("yes", "no", "abstain"):
            return {"voted": False, "reason": "choice invalido"}
        if time.time() - rnd.created_at > rnd.ttl_s:
            rnd.status = "expired"
            rnd.closed_at = time.time()
            return {"voted": False, "reason": "expired"}
        rnd.votes[voter] = choice
        return self._tally(rnd)

    def _tally(self, rnd: ConsensusRound) -> Dict[str, Any]:
        yes = sum(1 for v in rnd.votes.values() if v == "yes")
        no = sum(1 for v in rnd.votes.values() if v == "no")
        n = max(1, len(rnd.voters))
        if yes / n >= QUORUM_RATIO:
            rnd.status = "decided"
            rnd.result = "accepted"
            rnd.closed_at = time.time()
            self._emit({"type": "round_decided", **rnd.to_dict()})
        elif no / n >= QUORUM_RATIO or len(rnd.votes) >= len(rnd.voters):
            rnd.status = "decided"
            rnd.result = "rejected" if no / n >= QUORUM_RATIO else "deadlock"
            rnd.closed_at = time.time()
            self._emit({"type": "round_decided", **rnd.to_dict()})
        return {"voted": True, **rnd.to_dict()}

    def publish_task(self, title: str, payload: Optional[Dict[str, Any]] = None,
                     requester: str = "local") -> Dict[str, Any]:
        if not title.strip():
            raise ValueError("title vacio")
        task = {"task_id": uuid.uuid4().hex[:12], "title": title.strip(),
                "payload": payload or {}, "requester": requester,
                "bids": [], "assignee": "", "status": "open",
                "created_at": time.time(), "offline_only": True}
        with self._lock:
            self._tasks[task["task_id"]] = task
        self._emit({"type": "task_published", **task})
        return task

    def bid(self, task_id: str, node_id: str, capacity: float) -> Dict[str, Any]:
        with self._lock:
            task = self._tasks.get(task_id)
        if task is None:
            return {"bid": False, "reason": "not found"}
        if task["status"] != "open":
            return {"bid": False, "reason": f"task {task['status']}"}
        cap = max(0.0, min(1.0, float(capacity)))
        task["bids"] = [b for b in task["bids"] if b["node_id"] != node_id]
        task["bids"].append({"node_id": node_id, "capacity": cap,
                             "ts": time.time()})
        task["bids"].sort(key=lambda b: b["capacity"], reverse=True)
        best = task["bids"][0]
        task["assignee"] = best["node_id"]
        return {"bid": True, "task_id": task_id, "assignee": best["node_id"],
                "bids": len(task["bids"]), "offline_only": True}

    def rounds(self, limit: int = 50) -> List[ConsensusRound]:
        with self._lock:
            items = sorted(self._rounds.values(),
                           key=lambda r: r.created_at, reverse=True)
            return items[:limit]

    def tasks(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            items = sorted(self._tasks.values(),
                           key=lambda t: t["created_at"], reverse=True)
            return items[:limit]

    def reset(self) -> None:
        with self._lock:
            self._rounds.clear()
            self._tasks.clear()


_G: Optional[SwarmConsensusEngine] = None
_L = threading.Lock()


def get_consensus_engine() -> SwarmConsensusEngine:
    global _G
    with _L:
        if _G is None:
            _G = SwarmConsensusEngine()
        return _G


def reset_consensus_engine() -> None:
    global _G
    with _L:
        _G = None
