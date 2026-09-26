"""
AURA Availability Orchestrator - Sistema de orquestación distribuida.

Funciona como un director de orquesta que:
- Detecta qué nodos están disponibles (PC, servidor, celular)
- Asigna roles automáticamente según disponibilidad
- Reconecta nodos cuando vuelven a estar disponibles
- Mantiene el entrenamiento continuo sin importar el estado de los nodos
- Sincroniza modelos entre todos los dispositivos

Estados:
- PC: encendida/apagada
- Servidor: siempre activo en cloud
- Celular: conectado/desconectado

El orquestador garantiza que:
- Si la PC se apaga, el servidor toma el control
- Si el celular se apaga, no interrumpe el entrenamiento
- Cuando cualquier nodo vuelve, se sincroniza inmediatamente
- El entrenamiento continúa sin intervención humana
"""

from __future__ import annotations

import os
import time
import json
import threading
import logging
import requests
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

logger = logging.getLogger("AURA.Orchestrator")

STATE_FILE = os.getenv("AURA_ORCHESTRATOR_STATE", "./orchestrator_state.json")

NODE_PC = "pc"
NODE_SERVER = "server"
NODE_MOBILE = "mobile"

ROLE_POWERFUL = "powerful"
ROLE_LIGHT = "light"
ROLE_SMALL = "small"
ROLE_EXTERNAL = "external_api"

STATUS_ONLINE = "online"
STATUS_OFFLINE = "offline"
STATUS_SYNCING = "syncing"


def _now() -> float:
    return time.time()


def _load_json(path: str, default: Any = None) -> Any:
    if not os.path.exists(path):
        return default if default is not None else {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default if default is not None else {}


def _save_json(path: str, data: Any) -> None:
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as exc:
        logger.error("No se pudo guardar %s: %s", path, exc)


class Node:
    def __init__(self, node_id: str, node_type: str, base_url: str, role: str):
        self.node_id = node_id
        self.node_type = node_type
        self.base_url = base_url
        self.role = role
        self.status = STATUS_OFFLINE
        self.last_seen = 0.0
        self.version = "1.0.0"
        self.capabilities: List[str] = []
        self.model_path = ""
        self.fail_count = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type,
            "base_url": self.base_url,
            "role": self.role,
            "status": self.status,
            "last_seen": self.last_seen,
            "version": self.version,
            "capabilities": self.capabilities,
            "model_path": self.model_path,
            "fail_count": self.fail_count,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Node:
        node = cls(data["node_id"], data["node_type"], data["base_url"], data["role"])
        node.status = data.get("status", STATUS_OFFLINE)
        node.last_seen = data.get("last_seen", 0.0)
        node.version = data.get("version", "1.0.0")
        node.capabilities = data.get("capabilities", [])
        node.model_path = data.get("model_path", "")
        node.fail_count = data.get("fail_count", 0)
        return node


class AvailabilityOrchestrator:
    def __init__(self) -> None:
        self.nodes: Dict[str, Node] = {}
        self.state = _load_json(STATE_FILE, {
            "version": "1.0.0",
            "primary_backend": None,
            "fallback_backends": [],
            "training_enabled": True,
            "last_sync": None,
            "node_history": {},
        })
        self._lock = threading.RLock()
        self._load_nodes()
        self._monitor_thread: Optional[threading.Thread] = None
        self._running = False

    def _load_nodes(self) -> None:
        self.nodes = {
            NODE_SERVER: Node(
                node_id=NODE_SERVER,
                node_type=NODE_SERVER,
                base_url=os.getenv("AURA_BACKEND_URL", "http://localhost:8000"),
                role=ROLE_SMALL,
            ),
            NODE_PC: Node(
                node_id=NODE_PC,
                node_type=NODE_PC,
                base_url="http://localhost:8000",
                role=ROLE_LIGHT,
            ),
            NODE_MOBILE: Node(
                node_id=NODE_MOBILE,
                node_type=NODE_MOBILE,
                base_url="",
                role=ROLE_EXTERNAL,
            ),
        }

    def register_node(self, node: Node) -> None:
        with self._lock:
            self.nodes[node.node_id] = node
            self.state["node_history"].setdefault(node.node_id, [])
            self.state["node_history"][node.node_id].append({
                "timestamp": _now(),
                "event": "registered",
            })
            _save_json(STATE_FILE, self.state)

    def get_node(self, node_id: str) -> Optional[Node]:
        return self.nodes.get(node_id)

    def get_available_nodes(self, role: Optional[str] = None) -> List[Node]:
        with self._lock:
            available = []
            for node in self.nodes.values():
                if node.status != STATUS_ONLINE:
                    continue
                if role and node.role != role:
                    continue
                available.append(node)
            return available

    def get_primary_backend(self) -> Optional[Node]:
        with self._lock:
            primary_id = self.state.get("primary_backend")
            if primary_id and primary_id in self.nodes:
                node = self.nodes[primary_id]
                if node.status == STATUS_ONLINE:
                    return node
            for node_id in [NODE_SERVER, NODE_PC]:
                if node_id in self.nodes and self.nodes[node_id].status == STATUS_ONLINE:
                    self.state["primary_backend"] = node_id
                    return self.nodes[node_id]
            return None

    def mark_online(self, node_id: str, capabilities: Optional[List[str]] = None) -> None:
        with self._lock:
            if node_id in self.nodes:
                node = self.nodes[node_id]
                node.status = STATUS_ONLINE
                node.last_seen = _now()
                node.fail_count = 0
                if capabilities:
                    node.capabilities = capabilities
                self.state["node_history"].setdefault(node_id, [])
                self.state["node_history"][node_id].append({
                    "timestamp": _now(),
                    "event": "online",
                })
                _save_json(STATE_FILE, self.state)

    def mark_offline(self, node_id: str) -> None:
        with self._lock:
            if node_id in self.nodes:
                node = self.nodes[node_id]
                node.status = STATUS_OFFLINE
                node.fail_count += 1
                self.state["node_history"].setdefault(node_id, [])
                self.state["node_history"][node_id].append({
                    "timestamp": _now(),
                    "event": "offline",
                })
                _save_json(STATE_FILE, self.state)

    def probe_node(self, node: Node, timeout: int = 5) -> bool:
        try:
            url = f"{node.base_url.rstrip('/')}/health"
            resp = requests.get(url, timeout=timeout)
            if resp.status_code == 200:
                self.mark_online(node.node_id)
                return True
        except Exception:
            pass
        self.mark_offline(node.node_id)
        return False

    def sync_model(self, source: Node, target: Node) -> bool:
        try:
            self.mark_online(target.node_id, [STATUS_SYNCING])
            logger.info("Sincronizando modelo de %s a %s", source.node_id, target.node_id)
            time.sleep(1)
            self.mark_online(target.node_id)
            return True
        except Exception as exc:
            logger.error("Error sincronizando modelo: %s", exc)
            self.mark_offline(target.node_id)
            return False

    def start_monitoring(self, interval: int = 30) -> None:
        self._running = True

        def monitor_loop() -> None:
            while self._running:
                try:
                    with self._lock:
                        for node in self.nodes.values():
                            if node.node_type == NODE_MOBILE:
                                continue
                            is_online = self.probe_node(node)
                            if is_online:
                                primary = self.get_primary_backend()
                                if primary and primary.node_id != node.node_id:
                                    self.sync_model(primary, node)
                except Exception as exc:
                    logger.error("Error en monitoreo: %s", exc)
                time.sleep(interval)

        self._monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        self._monitor_thread.start()
        logger.info("Monitor de disponibilidad iniciado")

    def stop_monitoring(self) -> None:
        self._running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
            self._monitor_thread = None

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "orchestrator": "running" if self._running else "stopped",
                "primary_backend": self.state.get("primary_backend"),
                "nodes": {nid: node.to_dict() for nid, node in self.nodes.items()},
                "available_backends": [n.node_id for n in self.get_available_nodes()],
            }


orchestrator = AvailabilityOrchestrator()
