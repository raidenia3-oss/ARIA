# Knowledge Graph JSON-Based — Fase 18
# Estructura: {"nodes": {id: {id,label,type,attrs}}, "edges": {id: {src,dst,rel,attrs}}}

import json
import os
from typing import Any, Dict, List, Optional


class KnowledgeGraph:
    def __init__(self, path: str = "AURA_Core/memory/knowledge_graph.json") -> None:
        self.path = path
        self.nodes: Dict[str, Dict[str, Any]] = {}
        self.edges: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.nodes = data.get("nodes", {})
                self.edges = data.get("edges", {})
            except Exception:
                self.nodes, self.edges = {}, {}

    def save(self) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump({"nodes": self.nodes, "edges": self.edges}, f, ensure_ascii=False, indent=2)

    def add_node(
        self,
        node_id: str,
        label: str,
        node_type: str,
        attrs: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        node = {"id": node_id, "label": label, "type": node_type, "attrs": attrs or {}}
        self.nodes[node_id] = node
        return node

    def add_relation(
        self,
        src: str,
        dst: str,
        rel: str,
        attrs: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if src not in self.nodes or dst not in self.nodes:
            raise ValueError("Source or destination node missing")
        edge_id = f"{src}->{dst}::{rel}"
        edge = {"id": edge_id, "src": src, "dst": dst, "rel": rel, "attrs": attrs or {}}
        self.edges[edge_id] = edge
        return edge

    def query_graph_context(self, node_name: str, max_depth: int = 2) -> Dict[str, Any]:
        visited_edges = set()

        def dfs(current: str, depth: int) -> List[Dict[str, Any]]:
            if depth <= 0:
                return []
            out: List[Dict[str, Any]] = []
            for edge in self.edges.values():
                if edge["src"] == current and edge["id"] not in visited_edges:
                    visited_edges.add(edge["id"])
                    out.append(edge)
                    out.extend(dfs(edge["dst"], depth - 1))
            return out

        related = dfs(node_name, max_depth)
        return {"node": node_name, "relations": related}

    def list_types(self) -> List[str]:
        return list({n["type"] for n in self.nodes.values()})

    def index_chat_message(self, message: str) -> None:
        """Indexa entidades del mensaje al grafo y conecta ideas clave."""
        entities = {
            "Usuario": ["yo"],
            "AME_Mobile": ["ame", "app", "android"],
            "RollerCoin_Bot": ["rollercoin", "bot", "miner"],
            "Godot_RPG": ["godot", "juego", "endless", "rpg"],
            "JARVIS_HUD": ["jarvis", "hud", "visualizador"],
            "Metricas_Rendimiento": ["hashrate", "rendimiento", "métrica"],
            "Telemetria": ["telemetría", "telemetria", "datos"],
        }
        lowered = message.lower()
        matched: List[str] = []
        for node_id, keywords in entities.items():
            if any(k in lowered for k in keywords):
                matched.append(node_id)
        if not matched:
            return
        for dst in matched:
            if "Usuario" in matched and dst != "Usuario":
                self.add_relation("Usuario", dst, "MENCIONA")
                self.save()


def bootstrap_ecosystem(kg: KnowledgeGraph) -> None:
    kg.add_node("Usuario", "Usuario", "entidad", {"rol": "owner"})
    kg.add_node("AME_Mobile", "AME_Móvil", "servicio", {"plataforma": "Android"})
    kg.add_node("RollerCoin_Bot", "RollerCoin Bot", "servicio", {"stack": "Python"})
    kg.add_node("Godot_RPG", "Juego Godot", "servicio", {"motor": "Godot"})
    kg.add_node("JARVIS_HUD", "JARVIS HUD", "visualizador", {"tipo": "HUD"})
    kg.add_node("Metricas_Rendimiento", "Métricas Rendimiento", "dato")
    kg.add_node("Telemetria", "Telemetría", "dato")

    kg.add_relation("Usuario", "AME_Mobile", "UTILIZA")
    kg.add_relation("Usuario", "RollerCoin_Bot", "EJECUTA")
    kg.add_relation("Usuario", "Godot_RPG", "JUEGA_A")
    kg.add_relation("AME_Mobile", "Telemetria", "ALIMENTA_DE_DATOS")
    kg.add_relation("RollerCoin_Bot", "Metricas_Rendimiento", "PRODUCE")
    kg.add_relation("Metricas_Rendimiento", "JARVIS_HUD", "VISUALIZADO_EN")
    kg.add_relation("Telemetria", "JARVIS_HUD", "MONITOREA")
    kg.save()
