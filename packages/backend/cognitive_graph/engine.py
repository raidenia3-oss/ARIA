"""BLOQUE 88 - engine base (init/ingest/consolidate)."""
from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from backend.cognitive_graph.entities import (
    CognitiveEdge, CognitiveNode, extract_entities,
)

STORE_SUBDIR = "backend/cognitive_graph_state"
GRAPH_FILE = "graph.json"
MAX_NODES = 5000
MAX_EDGES = 20000


def _sdir(store_dir: Optional[str] = None) -> Path:
    d = Path(store_dir or os.getenv("AURA_COGNITIVE_DIR", STORE_SUBDIR))
    if not d.is_absolute():
        d = Path.cwd() / d
    d.mkdir(parents=True, exist_ok=True)
    return d


class CognitiveGraphEngine:
    def __init__(self, store_dir: Optional[str] = None) -> None:
        self._lock = threading.Lock()
        self._store = _sdir(store_dir)
        self._nodes: Dict[str, CognitiveNode] = {}
        self._by_label: Dict[str, str] = {}
        self._edges: Dict[str, CognitiveEdge] = {}
        self._summaries: List[Dict[str, Any]] = []
        self._watchers: List[Callable[[Dict[str, Any]], None]] = []
        self._load()

    def on_event(self, cb: Callable[[Dict[str, Any]], None]) -> None:
        with self._lock:
            self._watchers.append(cb)

    def ingest(self, text: str, kind: str = "concept") -> Dict[str, Any]:
        labels = extract_entities(text)
        if not labels:
            return {"nodes": 0, "edges": 0, "labels": [], "offline_only": True}
        with self._lock:
            ids: List[str] = []
            for label in labels:
                key = label.lower()
                nid = self._by_label.get(key)
                if nid and nid in self._nodes:
                    n = self._nodes[nid]
                    n.mentions += 1
                    n.weight = min(10.0, n.weight + 0.5)
                    n.last_seen = time.time()
                else:
                    n = CognitiveNode(label=label, kind=kind)
                    self._nodes[n.node_id] = n
                    self._by_label[key] = n.node_id
                ids.append(self._by_label[key])
            nedges = 0
            for i in range(len(ids)):
                for j in range(i + 1, len(ids)):
                    e = CognitiveEdge(source_id=ids[i], target_id=ids[j])
                    self._edges[e.edge_id] = e
                    nedges += 1
            self._prune()
            self._save()
        return {"nodes": len(labels), "edges": nedges, "labels": labels,
                "offline_only": True}

    def consolidate(self, history: List[str], label: str = "") -> Dict[str, Any]:
        texts = [t for t in (history or []) if t and t.strip()]
        if not texts:
            return {"consolidated": False, "reason": "empty history"}
        freq: Dict[str, int] = {}
        for t in texts[:200]:
            for lb in extract_entities(t):
                freq[lb] = freq.get(lb, 0) + 1
        concepts = [k for k, _ in sorted(
            freq.items(), key=lambda kv: kv[1], reverse=True)[:15]]
        summary = {"summary_id": f"s_{int(time.time()*1000):x}"[-12:],
                   "label": label, "texts": len(texts), "concepts": concepts,
                   "ts": time.time(), "offline_only": True}
        for c in concepts:
            self.ingest(c, kind="summary")
        with self._lock:
            self._summaries.append(summary)
            self._summaries = self._summaries[-200:]
            self._save()
        return {"consolidated": True, **summary}
