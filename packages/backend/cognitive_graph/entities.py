"""BLOQUE 88 - Cognitive graph synthesizer (parte 1/2, 100% local).

Extrae entidades/relaciones de textos (interacciones, docs RAG, misiones)
con regex local (sin NLP cloud) y las estructura en nodos/aristas.
"""
from __future__ import annotations

import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List

_WORD = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ][\w\-]{2,}")
_CAP = re.compile(r"\b[A-ZÁÉÍÓÚÜÑ][\w\-]{2,}(?:\s+[A-ZÁÉÍÓÚÜÑ][\w\-]{2,}){0,2}")
_STOP = frozenset({"Para", "Como", "Cuando", "Donde", "Porque", "Este", "Esta",
                   "Estos", "Estas", "Para", "The", "This", "That", "With", "From"})
MAX_ENTITIES_PER_TEXT = 20
MAX_TEXT = 4000


@dataclass
class CognitiveNode:
    node_id: str = ""
    label: str = ""
    kind: str = "concept"
    weight: float = 1.0
    mentions: int = 1
    first_seen: float = 0.0
    last_seen: float = 0.0

    def __post_init__(self) -> None:
        if not self.node_id:
            self.node_id = uuid.uuid4().hex[:12]
        if not self.first_seen:
            self.first_seen = time.time()
        if not self.last_seen:
            self.last_seen = self.first_seen

    def to_dict(self) -> Dict[str, Any]:
        return {"node_id": self.node_id, "label": self.label, "kind": self.kind,
                "weight": round(self.weight, 3), "mentions": self.mentions,
                "first_seen": self.first_seen, "last_seen": self.last_seen,
                "offline_only": True}


@dataclass
class CognitiveEdge:
    edge_id: str = ""
    source_id: str = ""
    target_id: str = ""
    relation: str = "co_occurs"
    weight: float = 1.0
    ts: float = 0.0

    def __post_init__(self) -> None:
        if not self.edge_id:
            self.edge_id = uuid.uuid4().hex[:12]
        if not self.ts:
            self.ts = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {"edge_id": self.edge_id, "source_id": self.source_id,
                "target_id": self.target_id, "relation": self.relation,
                "weight": round(self.weight, 3), "ts": self.ts,
                "offline_only": True}


def extract_entities(text: str) -> List[str]:
    found: List[str] = []
    seen = set()
    for m in _CAP.finditer((text or "")[:MAX_TEXT]):
        label = " ".join(m.group(0).split())
        if label in seen or label.split()[0] in _STOP:
            continue
        seen.add(label)
        found.append(label)
        if len(found) >= MAX_ENTITIES_PER_TEXT:
            break
    return found


__all__ = ["CognitiveNode", "CognitiveEdge", "extract_entities",
           "MAX_ENTITIES_PER_TEXT"]
