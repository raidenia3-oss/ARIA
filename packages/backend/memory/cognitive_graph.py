"""BLOQUE 88 - Cognitive Graph Engine (parte 1/3)."""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

GRAPH_DIR = "backend/cognitive_graph_state"
GRAPH_FILE = "knowledge_graph.json"
MAX_NODES = 20000
MAX_EDGES = 40000
PRUNE_MIN_ACCESS = 3
PRUNE_AGE_DAYS = 90.0
CONSOLIDATE_INTERVAL_S = 3600.0
ENTITY_PATTERNS = (
    re.compile(r"\b(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b"),
    re.compile(r"\b[A-Za-z_][A-Za-z0-9_]{2,}\b"),
)
RELATION_KEYWORDS = (
    ("related_to", ("relacionado", "related", "similar", "como")),
    ("causes", ("causa", "provoca", "genera", "produce")),
    ("depends_on", ("depende", "necesita", "requiere", "usa")),
    ("part_of", ("parte", "modulo", "componente", "sub")),
    ("contradicts", ("contradice", "opone", "conflicta")),
    ("enables", ("permite", "habilita", "permite")),
)


def _now() -> float:
    return time.time()


def _stable_id(text: str, prefix: str = "n") -> str:
    h = hashlib.sha256(text.strip().lower().encode("utf-8")).hexdigest()[:10]
    return f"{prefix}_{h}"


def _ensure_dir(path: str) -> Path:
    p = Path(path)
    if not p.is_absolute():
        p = Path.cwd() / p
    p.mkdir(parents=True, exist_ok=True)
    return p


@dataclass
class CognitiveNode:
    node_id: str = ""
    label: str = ""
    kind: str = "concept"
    summary: str = ""
    source: str = "interaction"
    confidence: float = 0.5
    access_count: int = 0
    created_at: float = 0.0
    updated_at: float = 0.0
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    offline_only: bool = True

    def __post_init__(self) -> None:
        if not self.node_id:
            self.node_id = _stable_id(self.label or str(uuid.uuid4()), prefix="n")
        if not self.created_at:
            self.created_at = _now()
        if not self.updated_at:
            self.updated_at = self.created_at

    def touch(self) -> None:
        self.access_count += 1
        self.updated_at = _now()

    def to_dict(self) -> Dict[str, Any]:
        return {"node_id": self.node_id, "label": self.label, "kind": self.kind,
                "summary": self.summary, "source": self.source,
                "confidence": round(self.confidence, 3), "access_count": self.access_count,
                "created_at": self.created_at, "updated_at": self.updated_at,
                "tags": list(self.tags), "metadata": self.metadata,
                "offline_only": self.offline_only}


@dataclass
class CognitiveEdge:
    edge_id: str = ""
    src: str = ""
    dst: str = ""
    relation: str = "related_to"
    weight: float = 0.5
    evidence: str = ""
    created_at: float = 0.0
    offline_only: bool = True

    def __post_init__(self) -> None:
        if not self.edge_id:
            self.edge_id = _stable_id(f"{self.src}:{self.relation}:{self.dst}", prefix="e")
        if not self.created_at:
            self.created_at = _now()

    def to_dict(self) -> Dict[str, Any]:
        return {"edge_id": self.edge_id, "src": self.src, "dst": self.dst,
                "relation": self.relation, "weight": round(self.weight, 3),
                "evidence": self.evidence, "created_at": self.created_at,
                "offline_only": self.offline_only}


@dataclass
class MemorySummary:
    summary_id: str = ""
    title: str = ""
    text: str = ""
    source: str = "interaction"
    cluster: List[str] = field(default_factory=list)
    created_at: float = 0.0
    offline_only: bool = True

    def __post_init__(self) -> None:
        if not self.summary_id:
            self.summary_id = uuid.uuid4().hex[:12]
        if not self.created_at:
            self.created_at = _now()

    def to_dict(self) -> Dict[str, Any]:
        return {"summary_id": self.summary_id, "title": self.title, "text": self.text,
                "source": self.source, "cluster": list(self.cluster),
                "created_at": self.created_at, "offline_only": self.offline_only}
class CognitiveGraphEngine:
    """Grafo semantico local, consolidador de memoria y poda (100% offline)."""

    def __init__(self, graph_dir: Optional[str] = None) -> None:
        self._lock = threading.RLock()
        self._dir = Path(graph_dir) if graph_dir else _ensure_dir(GRAPH_DIR)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._path = self._dir / GRAPH_FILE
        self._nodes: Dict[str, CognitiveNode] = {}
        self._edges: Dict[str, CognitiveEdge] = {}
        self._adj: Dict[str, Set[str]] = defaultdict(set)
        self._summaries: List[MemorySummary] = []
        self._watchers: List[Callable[[Dict[str, Any]], None]] = []
        self._last_consolidate = 0.0
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            for nd in data.get("nodes", []):
                n = CognitiveNode(**nd)
                self._nodes[n.node_id] = n
            for ed in data.get("edges", []):
                e = CognitiveEdge(**ed)
                self._edges[e.edge_id] = e
                self._adj[e.src].add(e.edge_id)
                self._adj[e.dst].add(e.edge_id)
            self._summaries = [MemorySummary(**s) for s in data.get("summaries", [])]
        except Exception:
            pass

    def _save(self) -> None:
        payload = {
            "nodes": [n.to_dict() for n in self._nodes.values()],
            "edges": [e.to_dict() for e in self._edges.values()],
            "summaries": [s.to_dict() for s in self._summaries],
            "offline_only": True,
        }
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self._path)

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

    def _extract_entities(self, text: str) -> List[str]:
        found: List[str] = []
        seen: Set[str] = set()
        for pat in ENTITY_PATTERNS:
            for m in pat.findall(text or ""):
                w = m.strip()
                if len(w) >= 3 and w.lower() not in seen:
                    seen.add(w.lower())
                    found.append(w)
        return found[:20]

    def _classify_relation(self, text: str) -> str:
        low = (text or "").lower()
        for rel, kws in RELATION_KEYWORDS:
            for kw in kws:
                if kw in low:
                    return rel
        return "related_to"

    def ingest(self, text: str, source: str = "interaction",
               kind: str = "concept", summary: str = "",
               metadata: Optional[Dict[str, Any]] = None) -> List[CognitiveNode]:
        """Sintetiza entidades y crea/actualiza nodos en el grafo local."""
        entities = self._extract_entities(text)
        created: List[CognitiveNode] = []
        rel = self._classify_relation(text)
        with self._lock:
            prev: Optional[str] = None
            for ent in entities:
                nid = _stable_id(ent, prefix="n")
                node = self._nodes.get(nid)
                if node is None:
                    node = CognitiveNode(label=ent, kind=kind, source=source,
                                         summary=summary or text[:200],
                                         metadata=metadata or {})
                    self._nodes[nid] = node
                    created.append(node)
                node.touch()
                if prev is not None and prev != nid:
                    eid = _stable_id(f"{prev}:{rel}:{nid}", prefix="e")
                    edge = self._edges.get(eid)
                    if edge is None:
                        edge = CognitiveEdge(src=prev, dst=nid, relation=rel,
                                             evidence=text[:200])
                        self._edges[eid] = edge
                        self._adj[prev].add(eid)
                        self._adj[nid].add(eid)
                    else:
                        edge.weight = min(1.0, edge.weight + 0.1)
                prev = nid
            if len(self._nodes) > MAX_NODES:
                self._prune()
            if len(self._edges) > MAX_EDGES:
                self._prune_edges()
            self._save()
        self._emit({"type": "ingested", "source": source, "nodes": len(created),
                    "entities": len(entities), "offline_only": True})
        return created

    def _prune(self) -> None:
        """Poda local: elimina nodos con bajo acceso y gran edad."""
        cutoff = _now() - PRUNE_AGE_DAYS * 86400.0
        victims = [nid for nid, n in self._nodes.items()
                   if n.access_count < PRUNE_MIN_ACCESS and n.created_at < cutoff]
        for nid in victims:
            self._remove_node(nid)

    def _prune_edges(self) -> None:
        weak = sorted(self._edges.values(), key=lambda e: e.weight)[:max(0, len(self._edges) - MAX_EDGES)]
        for e in weak:
            self._edges.pop(e.edge_id, None)
            self._adj[e.src].discard(e.edge_id)
            self._adj[e.dst].discard(e.edge_id)

    def _remove_node(self, nid: str) -> None:
        self._nodes.pop(nid, None)
        for eid in list(self._adj.get(nid, [])):
            self._edges.pop(eid, None)
        self._adj.pop(nid, None)
        for s in self._adj:
            s.discard(nid)

    def consolidate(self, force: bool = False) -> List[MemorySummary]:
        """Consolidador de memoria a largo plazo: resume clusters en MemorySummary."""
        now = _now()
        if not force and now - self._last_consolidate < CONSOLIDATE_INTERVAL_S:
            return []
        with self._lock:
            clusters: List[List[CognitiveNode]] = []
            visited: Set[str] = set()
            for nid, node in self._nodes.items():
                if nid in visited:
                    continue
                stack = [nid]
                comp: List[CognitiveNode] = []
                while stack:
                    cur = stack.pop()
                    if cur in visited or cur not in self._nodes:
                        continue
                    visited.add(cur)
                    comp.append(self._nodes[cur])
                    for eid in self._adj.get(cur, []):
                        edge = self._edges.get(eid)
                        if edge is None:
                            continue
                        other = edge.dst if edge.src == cur else edge.src
                        if other not in visited:
                            stack.append(other)
                if comp:
                    clusters.append(comp)
            new_summaries: List[MemorySummary] = []
            for comp in clusters:
                labels = [n.label for n in comp]
                text = " | ".join(n.summary for n in comp if n.summary)[:600]
                ms = MemorySummary(title="cluster:" + ",".join(labels[:6]),
                                   text=text or " ".join(labels),
                                   source="consolidated",
                                   cluster=[n.node_id for n in comp])
                new_summaries.append(ms)
            self._summaries = new_summaries[-500:]
            self._last_consolidate = now
            self._save()
        self._emit({"type": "consolidated", "clusters": len(new_summaries),
                    "nodes": len(self._nodes), "offline_only": True})
        return new_summaries

    def search(self, query: str, limit: int = 20) -> List[CognitiveNode]:
        q = (query or "").lower()
        out: List[CognitiveNode] = []
        with self._lock:
            for n in self._nodes.values():
                if q in n.label.lower() or q in n.summary.lower() or q in " ".join(n.tags).lower():
                    out.append(n)
        out.sort(key=lambda n: n.access_count, reverse=True)
        return out[:max(1, limit)]

    def neighbors(self, node_id: str, limit: int = 20) -> List[Tuple[CognitiveEdge, CognitiveNode]]:
        with self._lock:
            node = self._nodes.get(node_id)
            if node is None:
                return []
            out: List[Tuple[CognitiveEdge, CognitiveNode]] = []
            for eid in self._adj.get(node_id, []):
                edge = self._edges.get(eid)
                if edge is None:
                    continue
                other_id = edge.dst if edge.src == node_id else edge.src
                other = self._nodes.get(other_id)
                if other is not None:
                    out.append((edge, other))
        out.sort(key=lambda t: t[0].weight, reverse=True)
        return out[:max(1, limit)]

    def clusters(self) -> List[List[str]]:
        with self._lock:
            visited: Set[str] = set()
            out: List[List[str]] = []
            for nid in self._nodes:
                if nid in visited:
                    continue
                stack = [nid]
                comp: List[str] = []
                while stack:
                    cur = stack.pop()
                    if cur in visited or cur not in self._nodes:
                        continue
                    visited.add(cur)
                    comp.append(cur)
                    for eid in self._adj.get(cur, []):
                        edge = self._edges.get(eid)
                        if edge is None:
                            continue
                        other = edge.dst if edge.src == cur else edge.src
                        if other not in visited:
                            stack.append(other)
                if comp:
                    out.append(comp)
            return out

    def get(self, node_id: str) -> Optional[CognitiveNode]:
        with self._lock:
            return self._nodes.get(node_id)

    def summaries(self, limit: int = 50) -> List[MemorySummary]:
        with self._lock:
            return self._summaries[-limit:]

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            rels: Dict[str, int] = defaultdict(int)
            for e in self._edges.values():
                rels[e.relation] += 1
            return {"nodes": len(self._nodes), "edges": len(self._edges),
                    "summaries": len(self._summaries), "clusters": len(self.clusters()),
                    "relations": dict(rels), "offline_only": True}

    def reset(self) -> None:
        with self._lock:
            self._nodes.clear()
            self._edges.clear()
            self._adj.clear()
            self._summaries.clear()
            self._last_consolidate = 0.0
            if self._path.exists():
                self._path.unlink()
        self._emit({"type": "reset", "offline_only": True})


_global_graph: Optional[CognitiveGraphEngine] = None
_graph_lock = threading.Lock()


def get_cognitive_graph() -> CognitiveGraphEngine:
    global _global_graph
    with _graph_lock:
        if _global_graph is None:
            _global_graph = CognitiveGraphEngine()
        return _global_graph


def reset_cognitive_graph() -> None:
    global _global_graph
    with _graph_lock:
        _global_graph = None


__all__ = [
    "CognitiveEdge",
    "CognitiveGraphEngine",
    "CognitiveNode",
    "MemorySummary",
    "get_cognitive_graph",
    "reset_cognitive_graph",
]