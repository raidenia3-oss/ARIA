"""Character Relationship Graph & Faction Matrix (BLOQUE 43).

Motor local de mapeo de redes de relaciones y matrices de facciones.
Permite rastrear dinámicamente alianzas, rivalidades, vínculos familiares
y lealtades políticas entre personajes. Integra con Jan para evitar
contradicciones narrativas.

Almacenamiento: JSON en disco bajo <store_dir>/graphs/work_<id>.graph.json
"""

from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from backend.story_memory.story_storage import StoryStorage
from backend.story_memory.character_bible import CharacterBible


class RelationshipType(Enum):
    """Tipos de relación entre personajes."""
    ALLY = "ally"                    # Alianza explícita
    FRIEND = "friend"                # Amistad
    FAMILY = "family"                # Vínculo familiar
    MENTOR = "mentor"                # Mentor/aprendiz
    RIVAL = "rival"                  # Rivalidad
    ENEMY = "enemy"                  # Enemistad declarada
    LOYAL_TO = "loyal_to"            # Lealtad jerárquica
    BETRAYED = "betrayed"            # Traición pasada
    ROMANTIC = "romantic"            # Vínculo romántico
    SUBORDINATE = "subordinate"      # Subordinación
    NEUTRAL = "neutral"              # Neutral


class FactionType(Enum):
    """Tipos de facción."""
    POLITICAL = "political"          # Partido/facción política
    MILITARY = "military"            # Ejército/orden militar
    RELIGIOUS = "religious"          # Orden religiosa
    CRIMINAL = "criminal"            # Organización criminal
    FAMILY_CLAN = "family_clan"      # Clan familiar
    GUILD = "guild"                  # Gremio/asociación
    SECRET_SOCIETY = "secret_society"  # Sociedad secreta
    INDEPENDENT = "independent"      # Sin facción


@dataclass
class RelationshipEdge:
    """Arista de relación entre dos personajes."""
    source_id: str
    target_id: str
    rel_type: RelationshipType
    weight: float = 1.0              # -1.0 (hostil) a 1.0 (aliado fuerte)
    bidirectional: bool = False      # Si la relación es mutua
    established_at: float = field(default_factory=time.time)
    last_updated: float = field(default_factory=time.time)
    evidence: List[str] = field(default_factory=list)  # Referencias a canon/scenas
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "rel_type": self.rel_type.value,
            "weight": self.weight,
            "bidirectional": self.bidirectional,
            "established_at": self.established_at,
            "last_updated": self.last_updated,
            "evidence": self.evidence,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RelationshipEdge":
        return cls(
            source_id=data["source_id"],
            target_id=data["target_id"],
            rel_type=RelationshipType(data["rel_type"]),
            weight=data.get("weight", 1.0),
            bidirectional=data.get("bidirectional", False),
            established_at=data.get("established_at", time.time()),
            last_updated=data.get("last_updated", time.time()),
            evidence=data.get("evidence", []),
            metadata=data.get("metadata", {}),
        )


@dataclass
class Faction:
    """Facción u organización en el mundo narrativo."""
    faction_id: str
    name: str
    faction_type: FactionType
    description: str = ""
    leader_id: Optional[str] = None
    members: Set[str] = field(default_factory=set)  # char_ids
    allies: Set[str] = field(default_factory=set)   # faction_ids
    enemies: Set[str] = field(default_factory=set)  # faction_ids
    territory: List[str] = field(default_factory=list)
    ideology: List[str] = field(default_factory=list)
    resources: Dict[str, float] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "faction_id": self.faction_id,
            "name": self.name,
            "faction_type": self.faction_type.value,
            "description": self.description,
            "leader_id": self.leader_id,
            "members": list(self.members),
            "allies": list(self.allies),
            "enemies": list(self.enemies),
            "territory": self.territory,
            "ideology": self.ideology,
            "resources": self.resources,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Faction":
        f = cls(
            faction_id=data["faction_id"],
            name=data["name"],
            faction_type=FactionType(data["faction_type"]),
            description=data.get("description", ""),
            leader_id=data.get("leader_id"),
            members=set(data.get("members", [])),
            allies=set(data.get("allies", [])),
            enemies=set(data.get("enemies", [])),
            territory=data.get("territory", []),
            ideology=data.get("ideology", []),
            resources=data.get("resources", {}),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
            metadata=data.get("metadata", {}),
        )
        return f


@dataclass
class RelationshipGraph:
    """Grafo de relaciones completo para una obra."""
    work_id: str
    nodes: Dict[str, Dict[str, Any]] = field(default_factory=dict)  # char_id -> char data
    edges: Dict[str, RelationshipEdge] = field(default_factory=dict)  # "source:target" -> edge
    factions: Dict[str, Faction] = field(default_factory=dict)       # faction_id -> faction
    character_factions: Dict[str, str] = field(default_factory=dict)  # char_id -> faction_id
    updated_at: float = field(default_factory=time.time)

    def _edge_key(self, source: str, target: str) -> str:
        return f"{source}:{target}"

    def add_node(self, char_id: str, char_data: Dict[str, Any]) -> None:
        self.nodes[char_id] = char_data
        self.updated_at = time.time()

    def remove_node(self, char_id: str) -> None:
        self.nodes.pop(char_id, None)
        # Remove edges involving this character
        to_remove = [k for k in self.edges if k.startswith(f"{char_id}:") or k.endswith(f":{char_id}")]
        for k in to_remove:
            self.edges.pop(k, None)
        self.character_factions.pop(char_id, None)
        self.updated_at = time.time()

    def add_edge(self, edge: RelationshipEdge) -> None:
        key = self._edge_key(edge.source_id, edge.target_id)
        self.edges[key] = edge
        if edge.bidirectional:
            rev_edge = RelationshipEdge(
                source_id=edge.target_id,
                target_id=edge.source_id,
                rel_type=edge.rel_type,
                weight=edge.weight,
                bidirectional=False,  # Avoid infinite loop
                established_at=edge.established_at,
                last_updated=edge.last_updated,
                evidence=edge.evidence.copy(),
                metadata=edge.metadata.copy(),
            )
            self.edges[self._edge_key(rev_edge.source_id, rev_edge.target_id)] = rev_edge
        self.updated_at = time.time()

    def remove_edge(self, source: str, target: str) -> bool:
        key = self._edge_key(source, target)
        if key in self.edges:
            edge = self.edges.pop(key)
            if edge.bidirectional:
                self.edges.pop(self._edge_key(target, source), None)
            self.updated_at = time.time()
            return True
        return False

    def get_edge(self, source: str, target: str) -> Optional[RelationshipEdge]:
        return self.edges.get(self._edge_key(source, target))

    def get_relationships(self, char_id: str, outgoing: bool = True) -> List[RelationshipEdge]:
        """Obtiene todas las relaciones de un personaje."""
        results = []
        for key, edge in self.edges.items():
            if outgoing and edge.source_id == char_id:
                results.append(edge)
            elif not outgoing and edge.target_id == char_id:
                results.append(edge)
        return results

    def get_relationship_between(self, char_a: str, char_b: str) -> Tuple[Optional[RelationshipEdge], Optional[RelationshipEdge]]:
        """Obtiene la relación en ambas direcciones."""
        return (
            self.get_edge(char_a, char_b),
            self.get_edge(char_b, char_a),
        )

    def add_faction(self, faction: Faction) -> None:
        self.factions[faction.faction_id] = faction
        self.updated_at = time.time()

    def remove_faction(self, faction_id: str) -> bool:
        if faction_id in self.factions:
            # Remove members from this faction
            for char_id in list(self.character_factions.keys()):
                if self.character_factions[char_id] == faction_id:
                    self.character_factions.pop(char_id)
            self.factions.pop(faction_id)
            self.updated_at = time.time()
            return True
        return False

    def assign_character_to_faction(self, char_id: str, faction_id: str) -> bool:
        if faction_id not in self.factions:
            return False
        self.character_factions[char_id] = faction_id
        self.factions[faction_id].members.add(char_id)
        self.factions[faction_id].updated_at = time.time()
        self.updated_at = time.time()
        return True

    def remove_character_from_faction(self, char_id: str) -> bool:
        faction_id = self.character_factions.pop(char_id, None)
        if faction_id and faction_id in self.factions:
            self.factions[faction_id].members.discard(char_id)
            self.factions[faction_id].updated_at = time.time()
            self.updated_at = time.time()
            return True
        return False

    def get_character_faction(self, char_id: str) -> Optional[Faction]:
        faction_id = self.character_factions.get(char_id)
        if faction_id:
            return self.factions.get(faction_id)
        return None

    def get_faction_members(self, faction_id: str) -> List[str]:
        faction = self.factions.get(faction_id)
        if faction:
            return list(faction.members)
        return []

    def get_relationship_matrix(self) -> Dict[str, Dict[str, float]]:
        """Genera matriz de afinidad entre todos los personajes."""
        char_ids = list(self.nodes.keys())
        matrix = {cid: {cid2: 0.0 for cid2 in char_ids} for cid in char_ids}
        for edge in self.edges.values():
            if edge.source_id in matrix and edge.target_id in matrix:
                matrix[edge.source_id][edge.target_id] = edge.weight
        return matrix

    def get_faction_matrix(self) -> Dict[str, Dict[str, float]]:
        """Genera matriz de relaciones entre facciones."""
        faction_ids = list(self.factions.keys())
        matrix = {fid: {fid2: 0.0 for fid2 in faction_ids} for fid in faction_ids}
        for fid, faction in self.factions.items():
            for ally in faction.allies:
                if ally in matrix[fid]:
                    matrix[fid][ally] = 1.0
            for enemy in faction.enemies:
                if enemy in matrix[fid]:
                    matrix[fid][enemy] = -1.0
        return matrix

    def find_shortest_path(self, start: str, end: str, max_depth: int = 5) -> Optional[List[str]]:
        """Encuentra camino más corto entre dos personajes (BFS)."""
        if start not in self.nodes or end not in self.nodes:
            return None
        if start == end:
            return [start]

        queue = [(start, [start])]
        visited = {start}

        while queue:
            current, path = queue.pop(0)
            if len(path) > max_depth:
                continue

            for edge in self.get_relationships(current, outgoing=True):
                neighbor = edge.target_id
                if neighbor == end:
                    return path + [neighbor]
                if neighbor not in visited and neighbor in self.nodes:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))

        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "work_id": self.work_id,
            "nodes": self.nodes,
            "edges": {k: v.to_dict() for k, v in self.edges.items()},
            "factions": {k: v.to_dict() for k, v in self.factions.items()},
            "character_factions": self.character_factions,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RelationshipGraph":
        g = cls(work_id=data["work_id"])
        g.nodes = data.get("nodes", {})
        g.edges = {k: RelationshipEdge.from_dict(v) for k, v in data.get("edges", {}).items()}
        g.factions = {k: Faction.from_dict(v) for k, v in data.get("factions", {}).items()}
        g.character_factions = data.get("character_factions", {})
        g.updated_at = data.get("updated_at", time.time())
        return g


class GraphManager:
    """Gestor de grafos de relaciones y facciones por obra."""

    def __init__(self, store_dir: Optional[str] = None) -> None:
        self.store_dir = Path(
            store_dir or os.getenv("AURA_STORY_DIR", os.path.join(os.getcwd(), "story_memory"))
        )
        self.graph_dir = self.store_dir / "graphs"
        self.graph_dir.mkdir(parents=True, exist_ok=True)
        self.storage = StoryStorage(store_dir=str(self.store_dir))
        self._graphs: Dict[str, RelationshipGraph] = {}
        self._lock = threading.RLock()

    def _graph_path(self, work_id: str) -> Path:
        safe = "".join(c if c.isalnum() or c in "_-" else "_" for c in work_id)
        return self.graph_dir / f"work_{safe}.graph.json"

    def _load_graph(self, work_id: str) -> RelationshipGraph:
        with self._lock:
            if work_id in self._graphs:
                return self._graphs[work_id]

            path = self._graph_path(work_id)
            if path.exists():
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    graph = RelationshipGraph.from_dict(data)
                except Exception:
                    graph = RelationshipGraph(work_id=work_id)
            else:
                graph = RelationshipGraph(work_id=work_id)

            self._graphs[work_id] = graph
            return graph

    def _save_graph(self, work_id: str) -> None:
        with self._lock:
            graph = self._graphs.get(work_id)
            if not graph:
                return
            path = self._graph_path(work_id)
            tmp = path.with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(graph.to_dict(), f, ensure_ascii=False, indent=2)
            tmp.replace(path)

    def get_or_create_graph(self, work_id: str) -> RelationshipGraph:
        """Obtiene o crea el grafo para una obra, sincronizando con CharacterBible solo al crear."""
        path = self._graph_path(work_id)
        graph_existed = path.exists()
        graph = self._load_graph(work_id)

        # Sync with CharacterBible only if graph was newly created (not loaded from disk)
        if not graph_existed and self.storage.work_exists(work_id):
            cb = CharacterBible()
            for char in cb.list(work_id):
                char_id = char.get("char_id")
                if char_id:
                    graph.add_node(char_id, char)
                    # Sync existing relationships from character data
                    relationships = char.get("relationships", {})
                    for target_char, rel_desc in relationships.items():
                        # Try to find target by name or char_id
                        target = cb.get_by_name(work_id, target_char)
                        if target:
                            target_id = target.get("char_id")
                            if target_id:
                                rel_type = self._infer_relationship_type(rel_desc)
                                edge = RelationshipEdge(
                                    source_id=char_id,
                                    target_id=target_id,
                                    rel_type=rel_type,
                                    weight=self._weight_from_type(rel_type),
                                    evidence=[f"character_bible:{char_id}"],
                                )
                                graph.add_edge(edge)

        return graph

    def _infer_relationship_type(self, description: str) -> RelationshipType:
        desc = description.lower()
        if any(k in desc for k in ["aliad", "aliado", "alianza", "apoya", "apoyo"]):
            return RelationshipType.ALLY
        if any(k in desc for k in ["amig", "amigo", "amiga", "confía", "confia"]):
            return RelationshipType.FRIEND
        if any(k in desc for k in ["familia", "hermano", "hermana", "padre", "madre", "hijo"]):
            return RelationshipType.FAMILY
        if any(k in desc for k in ["mentor", "maestro", "enseña", "guía", "guia"]):
            return RelationshipType.MENTOR
        if any(k in desc for k in ["rival", "compiten", "competencia", "opone"]):
            return RelationshipType.RIVAL
        if any(k in desc for k in ["enemig", "enemigo", "odia", "guerra", "conflicto"]):
            return RelationshipType.ENEMY
        if any(k in desc for k in ["leal", "lealtad", "sirve", "sirviente", "vasallo"]):
            return RelationshipType.LOYAL_TO
        if any(k in desc for k in ["traicion", "traicionó", "traiciono", "traiciona"]):
            return RelationshipType.BETRAYED
        if any(k in desc for k in ["amor", "novio", "novia", "esposo", "esposa", "pareja", "romántic"]):
            return RelationshipType.ROMANTIC
        if any(k in desc for k in ["subordinado", "sirve a", "bajo las órdenes", "bajo ordenes"]):
            return RelationshipType.SUBORDINATE
        return RelationshipType.NEUTRAL

    def _weight_from_type(self, rel_type: RelationshipType) -> float:
        weights = {
            RelationshipType.ALLY: 0.8,
            RelationshipType.FRIEND: 0.6,
            RelationshipType.FAMILY: 0.7,
            RelationshipType.MENTOR: 0.5,
            RelationshipType.RIVAL: -0.4,
            RelationshipType.ENEMY: -0.9,
            RelationshipType.LOYAL_TO: 0.7,
            RelationshipType.BETRAYED: -0.8,
            RelationshipType.ROMANTIC: 0.7,
            RelationshipType.SUBORDINATE: 0.3,
            RelationshipType.NEUTRAL: 0.0,
        }
        return weights.get(rel_type, 0.0)

    def save_graph(self, work_id: str) -> Dict[str, Any]:
        graph = self.get_or_create_graph(work_id)
        self._save_graph(work_id)
        return {"status": "saved", "work_id": work_id}

    # --- Relationship Operations ---

    def add_relationship(
        self,
        work_id: str,
        source_id: str,
        target_id: str,
        rel_type: RelationshipType,
        weight: Optional[float] = None,
        bidirectional: bool = False,
        evidence: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        graph = self.get_or_create_graph(work_id)
        if source_id not in graph.nodes or target_id not in graph.nodes:
            return {"status": "error", "error": "character_not_found"}

        edge = RelationshipEdge(
            source_id=source_id,
            target_id=target_id,
            rel_type=rel_type,
            weight=weight if weight is not None else self._weight_from_type(rel_type),
            bidirectional=bidirectional,
            evidence=evidence or [],
            metadata=metadata or {},
        )
        graph.add_edge(edge)
        self._save_graph(work_id)
        return {"status": "added", "edge": edge.to_dict()}

    def update_relationship(
        self,
        work_id: str,
        source_id: str,
        target_id: str,
        rel_type: Optional[RelationshipType] = None,
        weight: Optional[float] = None,
        evidence: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        graph = self.get_or_create_graph(work_id)
        edge = graph.get_edge(source_id, target_id)
        if not edge:
            return {"status": "error", "error": "relationship_not_found"}

        if rel_type is not None:
            edge.rel_type = rel_type
        if weight is not None:
            edge.weight = weight
        if evidence is not None:
            edge.evidence = evidence
        if metadata is not None:
            edge.metadata.update(metadata)
        edge.last_updated = time.time()
        self._save_graph(work_id)
        return {"status": "updated", "edge": edge.to_dict()}

    def remove_relationship(self, work_id: str, source_id: str, target_id: str) -> Dict[str, Any]:
        graph = self.get_or_create_graph(work_id)
        if graph.remove_edge(source_id, target_id):
            self._save_graph(work_id)
            return {"status": "removed"}
        return {"status": "error", "error": "relationship_not_found"}

    def get_relationships(self, work_id: str, char_id: str) -> Dict[str, Any]:
        graph = self.get_or_create_graph(work_id)
        if char_id not in graph.nodes:
            return {"status": "error", "error": "character_not_found"}

        outgoing = graph.get_relationships(char_id, outgoing=True)
        incoming = graph.get_relationships(char_id, outgoing=False)

        return {
            "status": "ok",
            "character_id": char_id,
            "outgoing": [e.to_dict() for e in outgoing],
            "incoming": [e.to_dict() for e in incoming],
        }

    def get_all_relationships(self, work_id: str) -> Dict[str, Any]:
        graph = self.get_or_create_graph(work_id)
        return {
            "status": "ok",
            "work_id": work_id,
            "relationships": [e.to_dict() for e in graph.edges.values()],
        }

    # --- Faction Operations ---

    def create_faction(
        self,
        work_id: str,
        faction_id: str,
        name: str,
        faction_type: FactionType,
        description: str = "",
        leader_id: Optional[str] = None,
        ideology: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        graph = self.get_or_create_graph(work_id)
        if faction_id in graph.factions:
            return {"status": "error", "error": "faction_exists"}

        faction = Faction(
            faction_id=faction_id,
            name=name,
            faction_type=faction_type,
            description=description,
            leader_id=leader_id,
            ideology=ideology or [],
        )
        if leader_id and leader_id in graph.nodes:
            faction.members.add(leader_id)
            graph.character_factions[leader_id] = faction_id

        graph.add_faction(faction)
        self._save_graph(work_id)
        return {"status": "created", "faction": faction.to_dict()}

    def update_faction(
        self,
        work_id: str,
        faction_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        leader_id: Optional[str] = None,
        allies: Optional[List[str]] = None,
        enemies: Optional[List[str]] = None,
        territory: Optional[List[str]] = None,
        ideology: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        graph = self.get_or_create_graph(work_id)
        faction = graph.factions.get(faction_id)
        if not faction:
            return {"status": "error", "error": "faction_not_found"}

        if name is not None:
            faction.name = name
        if description is not None:
            faction.description = description
        if leader_id is not None:
            if leader_id in graph.nodes:
                faction.leader_id = leader_id
            else:
                return {"status": "error", "error": "leader_not_found"}
        if allies is not None:
            faction.allies = set(allies)
        if enemies is not None:
            faction.enemies = set(enemies)
        if territory is not None:
            faction.territory = territory
        if ideology is not None:
            faction.ideology = ideology

        faction.updated_at = time.time()
        self._save_graph(work_id)
        return {"status": "updated", "faction": faction.to_dict()}

    def delete_faction(self, work_id: str, faction_id: str) -> Dict[str, Any]:
        graph = self.get_or_create_graph(work_id)
        if graph.remove_faction(faction_id):
            self._save_graph(work_id)
            return {"status": "deleted"}
        return {"status": "error", "error": "faction_not_found"}

    def add_character_to_faction(self, work_id: str, char_id: str, faction_id: str) -> Dict[str, Any]:
        graph = self.get_or_create_graph(work_id)
        if char_id not in graph.nodes:
            return {"status": "error", "error": "character_not_found"}
        if faction_id not in graph.factions:
            return {"status": "error", "error": "faction_not_found"}

        # Remove from current faction if any
        graph.remove_character_from_faction(char_id)

        if graph.assign_character_to_faction(char_id, faction_id):
            self._save_graph(work_id)
            return {"status": "assigned", "character_id": char_id, "faction_id": faction_id}
        return {"status": "error", "error": "assignment_failed"}

    def remove_character_from_faction(self, work_id: str, char_id: str) -> Dict[str, Any]:
        graph = self.get_or_create_graph(work_id)
        if graph.remove_character_from_faction(char_id):
            self._save_graph(work_id)
            return {"status": "removed", "character_id": char_id}
        return {"status": "error", "error": "character_not_in_faction"}

    def get_faction(self, work_id: str, faction_id: str) -> Dict[str, Any]:
        graph = self.get_or_create_graph(work_id)
        faction = graph.factions.get(faction_id)
        if not faction:
            return {"status": "error", "error": "faction_not_found"}
        return {"status": "ok", "faction": faction.to_dict()}

    def list_factions(self, work_id: str) -> Dict[str, Any]:
        graph = self.get_or_create_graph(work_id)
        return {
            "status": "ok",
            "work_id": work_id,
            "factions": [f.to_dict() for f in graph.factions.values()],
        }

    # --- Analysis & Conflict Checking ---

    def check_relationship_conflict(
        self,
        work_id: str,
        char_id: str,
        proposed_action: str,
        target_char_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Verifica si una acción propuesta contradice relaciones establecidas."""
        graph = self.get_or_create_graph(work_id)
        if char_id not in graph.nodes:
            return {"status": "error", "error": "character_not_found"}

        conflicts = []
        warnings = []

        # Check outgoing relationships
        for edge in graph.get_relationships(char_id, outgoing=True):
            target = edge.target_id
            if target_char_id and target != target_char_id:
                continue

            conflict = self._analyze_action_vs_relationship(proposed_action, edge)
            if conflict:
                if conflict["severity"] == "high":
                    conflicts.append(conflict)
                else:
                    warnings.append(conflict)

        # Check faction loyalty
        char_faction = graph.get_character_faction(char_id)
        if char_faction and target_char_id:
            target_faction = graph.get_character_faction(target_char_id)
            if target_faction and target_faction.faction_id != char_faction.faction_id:
                if target_faction.faction_id in char_faction.enemies:
                    conflicts.append({
                        "type": "faction_conflict",
                        "message": f"{char_id} pertenece a {char_faction.name}, enemiga de {target_faction.name}",
                        "severity": "high",
                        "source_faction": char_faction.faction_id,
                        "target_faction": target_faction.faction_id,
                    })

        return {
            "status": "ok",
            "character_id": char_id,
            "proposed_action": proposed_action,
            "conflicts": conflicts,
            "warnings": warnings,
            "has_conflicts": len(conflicts) > 0,
        }

    def _analyze_action_vs_relationship(self, action: str, edge: RelationshipEdge) -> Optional[Dict[str, Any]]:
        action_lower = action.lower()

        # Betrayal keywords
        betrayal_keywords = ["traicion", "traiciona", "traicionar", "vende", "entrega", "delata", "apuñala", "apunal"]
        # Hostile keywords
        hostile_keywords = ["ataca", "mata", "hiela", "lastima", "daña", "insulta", "amenaza", "declara guerra"]
        # Friendly/supportive keywords
        support_keywords = ["ayuda", "protege", "defiende", "salva", "cura", "apoya", "respald"]

        if edge.rel_type in (RelationshipType.ALLY, RelationshipType.FRIEND, RelationshipType.FAMILY,
                            RelationshipType.MENTOR, RelationshipType.LOYAL_TO, RelationshipType.ROMANTIC):
            if any(k in action_lower for k in betrayal_keywords):
                return {
                    "type": "betrayal",
                    "message": f"Acción contradice {edge.rel_type.value} con {edge.target_id}: {action}",
                    "severity": "high",
                    "relationship": edge.to_dict(),
                }
            if any(k in action_lower for k in hostile_keywords):
                return {
                    "type": "hostile_to_ally",
                    "message": f"Acción hostil hacia {edge.rel_type.value} {edge.target_id}: {action}",
                    "severity": "high",
                    "relationship": edge.to_dict(),
                }

        if edge.rel_type in (RelationshipType.ENEMY, RelationshipType.RIVAL, RelationshipType.BETRAYED):
            if any(k in action_lower for k in support_keywords):
                return {
                    "type": "support_to_enemy",
                    "message": f"Acción de apoyo a {edge.rel_type.value} {edge.target_id}: {action}",
                    "severity": "high",
                    "relationship": edge.to_dict(),
                }

        return None

    def get_relationship_summary(self, work_id: str, char_id: str) -> Dict[str, Any]:
        """Resumen narrativo de relaciones para inyección en prompts."""
        graph = self.get_or_create_graph(work_id)
        if char_id not in graph.nodes:
            return {"status": "error", "error": "character_not_found"}

        outgoing = graph.get_relationships(char_id, outgoing=True)
        incoming = graph.get_relationships(char_id, outgoing=False)
        faction = graph.get_character_faction(char_id)

        summary_parts = []
        if outgoing:
            rels = []
            for e in outgoing:
                target_name = graph.nodes.get(e.target_id, {}).get("name", e.target_id)
                rels.append(f"{target_name} ({e.rel_type.value}, peso={e.weight:.1f})")
            summary_parts.append(f"Relaciones activas: {', '.join(rels)}")

        if incoming:
            rels = []
            for e in incoming:
                source_name = graph.nodes.get(e.source_id, {}).get("name", e.source_id)
                rels.append(f"{source_name} → {char_id} ({e.rel_type.value})")
            summary_parts.append(f"Relaciones recibidas: {', '.join(rels)}")

        if faction:
            summary_parts.append(f"Facción: {faction.name} ({faction.faction_type.value})")
            if faction.allies:
                summary_parts.append(f"Aliados de facción: {', '.join(faction.allies)}")
            if faction.enemies:
                summary_parts.append(f"Enemigos de facción: {', '.join(faction.enemies)}")

        return {
            "status": "ok",
            "character_id": char_id,
            "summary": " | ".join(summary_parts) if summary_parts else "Sin relaciones registradas",
            "faction": faction.to_dict() if faction else None,
            "outgoing_count": len(outgoing),
            "incoming_count": len(incoming),
        }

    def export_graph_data(self, work_id: str) -> Dict[str, Any]:
        """Exporta datos completos del grafo para visualización."""
        graph = self.get_or_create_graph(work_id)
        return {
            "status": "ok",
            "work_id": work_id,
            "nodes": [
                {"id": cid, "label": data.get("name", cid), "data": data}
                for cid, data in graph.nodes.items()
            ],
            "edges": [e.to_dict() for e in graph.edges.values()],
            "factions": [f.to_dict() for f in graph.factions.values()],
            "character_factions": graph.character_factions,
            "relationship_matrix": graph.get_relationship_matrix(),
            "faction_matrix": graph.get_faction_matrix(),
        }

    def import_graph(self, work_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Importa datos del grafo desde un backup (formato export_graph_data)."""
        try:
            graph = self.get_or_create_graph(work_id)
            
            # Clear existing data
            graph.nodes.clear()
            graph.edges.clear()
            graph.factions.clear()
            graph.character_factions.clear()
            
            # Import nodes
            for node in data.get("nodes", []):
                node_id = node.get("id")
                node_data = node.get("data", {})
                if node_id:
                    graph.add_node(node_id, node_data)
            
            # Import edges
            for edge_data in data.get("edges", []):
                edge = RelationshipEdge.from_dict(edge_data)
                graph.edges[graph._edge_key(edge.source_id, edge.target_id)] = edge
            
            # Import factions
            for faction_data in data.get("factions", []):
                faction = Faction.from_dict(faction_data)
                graph.factions[faction.faction_id] = faction
            
            # Import character_factions
            graph.character_factions = data.get("character_factions", {})
            
            # Save to disk
            self._save_graph(work_id)
            return {"status": "ok", "work_id": work_id, "imported": True}
        except Exception as e:
            return {"status": "error", "error": str(e)}


_graph_manager: Optional[GraphManager] = None
_lock_init = threading.Lock()


def get_graph_manager(store_dir: Optional[str] = None) -> GraphManager:
    global _graph_manager
    if _graph_manager is None:
        with _lock_init:
            if _graph_manager is None:
                _graph_manager = GraphManager(store_dir=store_dir)
    return _graph_manager


def reset_graph_manager() -> None:
    global _graph_manager
    with _lock_init:
        _graph_manager = None