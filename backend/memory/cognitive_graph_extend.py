# -*- coding: utf-8 -*-
"""AURA OS - Cognitive Graph Extend (adapter over CognitiveGraphEngine).

Provides the interface expected by PatternDetector:
  - get_graph_extend() -> CognitiveGraphExtend
  - reset_graph_extend()

CognitiveGraphExtend wraps backend.memory.cognitive_graph.CognitiveGraphEngine
and exposes add_node / add_edge / add_awareness.
"""
from __future__ import annotations

import threading
import time
import uuid
from typing import Any, Dict, List, Optional

from backend.memory.cognitive_graph import (
    CognitiveGraphEngine,
    get_cognitive_graph,
    reset_cognitive_graph,
)


class CognitiveGraphExtend:
    """Adapter exposing add_node / add_edge over CognitiveGraphEngine."""

    def __init__(self, engine: Optional[CognitiveGraphEngine] = None) -> None:
        self._engine = engine or get_cognitive_graph()
        self._lock = threading.RLock()

    @property
    def engine(self) -> CognitiveGraphEngine:
        return self._engine

    def add_node(self, node_id: str, label: str = "",
                 attributes: Optional[Dict[str, Any]] = None,
                 kind: str = "concept") -> bool:
        """Add or update a node in the underlying graph."""
        attrs = dict(attributes or {})
        if label:
            attrs.setdefault("label", label)
        summary = attrs.pop("summary", f"{label} ({node_id})")
        try:
            nodes = self._engine.ingest(
                text=summary,
                source="pattern_detector",
                kind=kind,
                summary=summary,
                metadata=attrs,
            )
            # Ensure the requested node_id exists by aliasing if needed
            with self._engine._lock:
                if node_id not in self._engine._nodes:
                    for n in nodes:
                        self._engine._nodes[node_id] = n
                        break
            return True
        except Exception:
            return False

    def add_edge(self, source: str, target: str,
                 relationship: str = "related_to",
                 strength: float = 0.5) -> bool:
        """Add an edge between two nodes."""
        try:
            with self._engine._lock:
                src = source if source in self._engine._nodes else None
                dst = target if target in self._engine._nodes else None
                if src is None or dst is None:
                    return False
                from backend.memory.cognitive_graph import _stable_id, CognitiveEdge
                eid = _stable_id(f"{src}:{relationship}:{dst}", prefix="e")
                if eid not in self._engine._edges:
                    edge = CognitiveEdge(src=src, dst=dst, relation=relationship,
                                         strength=float(strength))
                    self._engine._edges[eid] = edge
                    self._engine._adj[src].add(eid)
                    self._engine._adj[dst].add(eid)
                else:
                    self._engine._edges[eid].touch()
                self._engine._save()
            return True
        except Exception:
            return False

    def add_awareness(self, node_id: str, context: Dict[str, Any]) -> bool:
        """Attach metadata to a node."""
        try:
            with self._engine._lock:
                node = self._engine._nodes.get(node_id)
                if node is None:
                    return False
                node.metadata.update(context)
                node.touch()
                self._engine._save()
            return True
        except Exception:
            return False

    def query(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search nodes by text."""
        try:
            nodes = self._engine.search(query, limit=limit)
            return [n.to_dict() for n in nodes]
        except Exception:
            return []

    def stats(self) -> Dict[str, Any]:
        return self._engine.stats()


_extend: Optional[CognitiveGraphExtend] = None
_extend_lock = threading.Lock()


def get_graph_extend() -> CognitiveGraphExtend:
    """Singleton accessor for CognitiveGraphExtend."""
    global _extend
    if _extend is None:
        with _extend_lock:
            if _extend is None:
                _extend = CognitiveGraphExtend()
    return _extend


def reset_graph_extend() -> None:
    """Reset the singleton (useful for tests)."""
    global _extend
    with _extend_lock:
        _extend = None
