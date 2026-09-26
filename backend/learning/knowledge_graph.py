# -*- coding: utf-8 -*-
"""AURA OS — Knowledge Graph.

Connects concepts from research, detects knowledge gaps,
and provides semantic search across all learned domains.
"""
from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("AURA.KnowledgeGraph")


@dataclass
class KGNode:
    node_id: str
    label: str
    node_type: str
    properties: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    access_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "label": self.label,
            "type": self.node_type,
            "properties": self.properties,
            "created_at": self.created_at,
            "access_count": self.access_count,
        }


@dataclass
class KGEdge:
    edge_id: str
    source: str
    target: str
    relation: str
    weight: float = 1.0
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "edge_id": self.edge_id,
            "source": self.source,
            "target": self.target,
            "relation": self.relation,
            "weight": self.weight,
            "created_at": self.created_at,
        }


class KnowledgeGraph:
    """Directed graph connecting concepts, topics, sources, and findings."""

    STORAGE_FILE = Path("data/learning/knowledge_graph.json")

    def __init__(self) -> None:
        self.nodes: Dict[str, KGNode] = {}
        self.edges: Dict[str, KGEdge] = {}
        self._adjacency: Dict[str, List[str]] = {}
        self._reverse_adj: Dict[str, List[str]] = {}
        self.STORAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
        self._load()

    def add_node(self, node_id: str, label: str, node_type: str, properties: Dict[str, Any] = None) -> KGNode:
        properties = properties or {}
        if node_id in self.nodes:
            node = self.nodes[node_id]
            node.label = label
            node.properties.update(properties)
            node.access_count += 1
        else:
            node = KGNode(node_id=node_id, label=label, node_type=node_type, properties=properties)
            self.nodes[node_id] = node
            self._adjacency[node_id] = []
            self._reverse_adj[node_id] = []
        self._save()
        return node

    def add_edge(self, source: str, target: str, relation: str, weight: float = 1.0) -> KGEdge:
        if source not in self.nodes or target not in self.nodes:
            raise ValueError(f"Source or target node missing: {source} -> {target}")
        edge_id = f"EDGE-{int(time.time())}-{len(self.edges)}"
        edge = KGEdge(edge_id=edge_id, source=source, target=target, relation=relation, weight=weight)
        self.edges[edge_id] = edge
        if target not in self._adjacency[source]:
            self._adjacency[source].append(target)
        if source not in self._reverse_adj[target]:
            self._reverse_adj[target].append(source)
        self._save()
        return edge

    def get_neighbors(self, node_id: str, relation: str = None, direction: str = "out") -> List[KGNode]:
        if node_id not in self.nodes:
            return []
        if direction == "out":
            neighbors = self._adjacency.get(node_id, [])
        elif direction == "in":
            neighbors = self._reverse_adj.get(node_id, [])
        else:
            neighbors = list(set(self._adjacency.get(node_id, [])) | set(self._reverse_adj.get(node_id, [])))
        result = []
        for nid in neighbors:
            if nid in self.nodes:
                edge_weight = self._get_edge_weight(node_id, nid, relation)
                node = self.nodes[nid]
                node.access_count += 1
                result.append((node, edge_weight))
        result.sort(key=lambda x: x[1], reverse=True)
        return [n for n, _ in result]

    def _get_edge_weight(self, source: str, target: str, relation: str = None) -> float:
        for edge in self.edges.values():
            if edge.source == source and edge.target == target:
                if relation is None or edge.relation == relation:
                    return edge.weight
        return 0.0

    def find_path(self, start: str, end: str, max_hops: int = 5) -> Optional[List[str]]:
        if start not in self.nodes or end not in self.nodes:
            return None
        visited = {start}
        queue: List[Tuple[str, List[str]]] = [(start, [start])]
        while queue:
            current, path = queue.pop(0)
            if len(path) > max_hops:
                continue
            for neighbor in self._adjacency.get(current, []):
                if neighbor == end:
                    return path + [neighbor]
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))
        return None

    def detect_gaps(self, domain: str) -> List[Dict[str, Any]]:
        domain_nodes = [n for n in self.nodes.values() if n.node_type == domain or domain.lower() in n.label.lower()]
        gaps: List[Dict[str, Any]] = []
        for node in domain_nodes:
            neighbors = self.get_neighbors(node.node_id)
            if len(neighbors) < 2:
                gaps.append({
                    "node": node.node_id,
                    "label": node.label,
                    "reason": "Low connectivity — few related concepts",
                    "neighbor_count": len(neighbors),
                })
        sparse = [n for n in self.nodes.values() if n.access_count < 3]
        for node in sparse[:5]:
            gaps.append({
                "node": node.node_id,
                "label": node.label,
                "reason": "Rarely accessed — may need attention",
                "access_count": node.access_count,
            })
        return gaps

    def search(self, query: str, max_results: int = 10) -> List[KGNode]:
        terms = query.lower().split()
        scores: List[Tuple[KGNode, float]] = []
        for node in self.nodes.values():
            score = 0.0
            for term in terms:
                if term in node.label.lower():
                    score += 2.0
                for prop_val in node.properties.values():
                    if isinstance(prop_val, str) and term in prop_val.lower():
                        score += 1.0
            neighbor_labels = " ".join(n.label.lower() for n in self.get_neighbors(node.node_id))
            for term in terms:
                if term in neighbor_labels:
                    score += 0.5
            if score > 0:
                scores.append((node, score))
        scores.sort(key=lambda x: x[1], reverse=True)
        return [n for n, _ in scores[:max_results]]

    def get_cluster(self, node_id: str, depth: int = 2) -> List[KGNode]:
        if node_id not in self.nodes:
            return []
        visited = {node_id}
        frontier = [node_id]
        for _ in range(depth):
            next_frontier: List[str] = []
            for fid in frontier:
                for neighbor in self._adjacency.get(fid, []):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        next_frontier.append(neighbor)
            frontier = next_frontier
        return [self.nodes[nid] for nid in visited if nid in self.nodes]

    def get_stats(self) -> Dict[str, Any]:
        type_counts: Dict[str, int] = {}
        for node in self.nodes.values():
            type_counts[node.node_type] = type_counts.get(node.node_type, 0) + 1
        return {
            "total_nodes": len(self.nodes),
            "total_edges": len(self.edges),
            "types": type_counts,
            "density": round(len(self.edges) / max(1, len(self.nodes) * (len(self.nodes) - 1) / 2), 4),
            "largest_cluster": len(self.get_cluster(next(iter(self.nodes), ""), depth=3)) if self.nodes else 0,
        }

    def export_graph(self) -> Dict[str, Any]:
        return {
            "nodes": [n.to_dict() for n in self.nodes.values()],
            "edges": [e.to_dict() for e in self.edges.values()],
        }

    def save(self) -> None:
        self._save()

    def _save(self) -> None:
        try:
            data = {"nodes": [n.to_dict() for n in self.nodes.values()], "edges": [e.to_dict() for e in self.edges.values()]}
            self.STORAGE_FILE.write_text(json.dumps(data, indent=2, default=str))
        except Exception as exc:
            logger.debug("KG save failed: %s", exc)

    def _load(self) -> None:
        try:
            if not self.STORAGE_FILE.exists():
                return
            data = json.loads(self.STORAGE_FILE.read_text())
            for n in data.get("nodes", []):
                node = KGNode(
                    node_id=n["node_id"], label=n["label"], node_type=n["node_type"],
                    properties=n.get("properties", {}), created_at=n.get("created_at", time.time()),
                    access_count=n.get("access_count", 0),
                )
                self.nodes[node.node_id] = node
                self._adjacency[node.node_id] = []
                self._reverse_adj[node.node_id] = []
            for e in data.get("edges", []):
                edge = KGEdge(
                    edge_id=e["edge_id"], source=e["source"], target=e["target"],
                    relation=e["relation"], weight=e.get("weight", 1.0),
                    created_at=e.get("created_at", time.time()),
                )
                self.edges[edge.edge_id] = edge
                if edge.target not in self._adjacency.get(edge.source, []):
                    self._adjacency.setdefault(edge.source, []).append(edge.target)
                if edge.source not in self._reverse_adj.get(edge.target, []):
                    self._reverse_adj.setdefault(edge.target, []).append(edge.source)
        except Exception:
            pass


knowledge_graph = KnowledgeGraph()
