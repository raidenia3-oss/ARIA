"""BLOQUE 88 - engine query/clusters/persist/singleton."""
from __future__ import annotations

import json
import threading
from typing import Any, Dict, List, Optional

from backend.cognitive_graph.engine import (
    GRAPH_FILE, MAX_EDGES, MAX_NODES, CognitiveGraphEngine,
)
from backend.cognitive_graph.entities import CognitiveEdge, CognitiveNode


def _query(self, term: str = "", limit: int = 20) -> Dict[str, Any]:
    q = (term or "").lower().strip()
    with self._lock:
        nodes = list(self._nodes.values())
        edges = list(self._edges.values())
    if q:
        nodes = [n for n in nodes if q in n.label.lower()]
        ids = {n.node_id for n in nodes}
        edges = [e for e in edges if e.source_id in ids or e.target_id in ids]
    nodes.sort(key=lambda n: (n.weight, n.mentions), reverse=True)
    nodes = nodes[: max(1, min(limit, 200))]
    ids = {n.node_id for n in nodes}
    edges = [e for e in edges if e.source_id in ids and e.target_id in ids][:200]
    return {"count": len(nodes), "nodes": [n.to_dict() for n in nodes],
            "edges": [e.to_dict() for e in edges], "offline_only": True}


def _clusters(self) -> Dict[str, Any]:
    with self._lock:
        nodes = list(self._nodes.values())
        edges = list(self._edges.values())
    parent: Dict[str, str] = {n.node_id: n.node_id for n in nodes}

    def find(x: str) -> str:
        while parent.get(x, x) != x:
            x = parent[x]
        return parent.get(x, x)

    for e in edges:
        a, b = find(e.source_id), find(e.target_id)
        if a != b:
            parent[b] = a
    groups: Dict[str, List[str]] = {}
    for n in nodes:
        groups.setdefault(find(n.node_id), []).append(n.label)
    ordered = sorted(groups.values(), key=len, reverse=True)[:50]
    return {"count": len(ordered),
            "clusters": [{"size": len(c), "members": c[:20]} for c in ordered],
            "offline_only": True}


def _summaries(self, limit: int = 50) -> List[Dict[str, Any]]:
    with self._lock:
        return list(self._summaries[-limit:])


def _reset(self) -> None:
    with self._lock:
        self._nodes.clear()
        self._by_label.clear()
        self._edges.clear()
        self._summaries.clear()
    try:
        (self._store / GRAPH_FILE).unlink(missing_ok=True)
    except Exception:
        pass


def _prune(self) -> None:
    if len(self._nodes) > MAX_NODES:
        r = sorted(self._nodes.values(), key=lambda n: (n.weight, n.mentions))
        for n in r[: len(self._nodes) - MAX_NODES]:
            del self._nodes[n.node_id]
            self._by_label.pop(n.label.lower(), None)
    if len(self._edges) > MAX_EDGES:
        r2 = sorted(self._edges.values(), key=lambda e: e.ts)
        for e in r2[: len(self._edges) - MAX_EDGES]:
            del self._edges[e.edge_id]


def _save(self) -> None:
    try:
        doc = {"nodes": [n.to_dict() for n in self._nodes.values()],
               "edges": [e.to_dict() for e in self._edges.values()],
               "summaries": self._summaries[-200:]}
        (self._store / GRAPH_FILE).write_text(
            json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def _load(self) -> None:
    try:
        p = self._store / GRAPH_FILE
        if not p.exists():
            return
        data = json.loads(p.read_text(encoding="utf-8"))
        for nd in data.get("nodes", [])[:MAX_NODES]:
            n = CognitiveNode(node_id=nd.get("node_id", ""),
                              label=nd.get("label", ""),
                              kind=nd.get("kind", "concept"))
            n.weight = float(nd.get("weight", 1.0))
            n.mentions = int(nd.get("mentions", 1))
            if n.label:
                self._nodes[n.node_id] = n
                self._by_label[n.label.lower()] = n.node_id
        for ed in data.get("edges", [])[:MAX_EDGES]:
            e = CognitiveEdge(edge_id=ed.get("edge_id", ""),
                              source_id=ed.get("source_id", ""),
                              target_id=ed.get("target_id", ""))
            self._edges[e.edge_id] = e
        self._summaries = data.get("summaries", [])[-200:]
    except Exception:
        pass


CognitiveGraphEngine.query = _query  # type: ignore
CognitiveGraphEngine.clusters = _clusters  # type: ignore
CognitiveGraphEngine.summaries = _summaries  # type: ignore
CognitiveGraphEngine.reset = _reset  # type: ignore
CognitiveGraphEngine._prune = _prune  # type: ignore
CognitiveGraphEngine._save = _save  # type: ignore
CognitiveGraphEngine._load = _load  # type: ignore


_G: Optional[CognitiveGraphEngine] = None
_L = threading.Lock()


def get_cognitive_engine(store_dir: Optional[str] = None) -> CognitiveGraphEngine:
    global _G
    with _L:
        if _G is None:
            _G = CognitiveGraphEngine(store_dir=store_dir)
        return _G


def reset_cognitive_engine() -> None:
    global _G
    with _L:
        _G = None
