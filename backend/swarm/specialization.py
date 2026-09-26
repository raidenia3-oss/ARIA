"""BLOQUE 93 - Motor local de especializaci\u00f3n de roles de enjambre y mercado de habilidades."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import threading
import time
import uuid
from typing import Any, Dict, List, Optional

from backend.swarm.models import (
    CapabilityProfile,
    RoleAssignment,
    RoleType,
    SkillCategory,
    SkillModule,
)

STATE_DIR = os.path.join("data", "swarm93")
os.makedirs(STATE_DIR, exist_ok=True)
STATE_FILE = os.path.join(STATE_DIR, "marketplace.json")


def _uid(prefix: str = "r") -> str:
    return prefix + "_" + uuid.uuid4().hex[:12]


def _sign(payload: Dict[str, Any], key: Optional[str] = None) -> str:
    key = key or os.getenv("AURA_SWARM_KEY", "local-sovereign-key")
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(key.encode("utf-8") + raw).hexdigest()


class LocalSwarmRoleRegistry:
    """Registro local de perfiles de competencia por nodo."""

    def __init__(self) -> None:
        self.profiles: Dict[str, CapabilityProfile] = {}
        self._lock = threading.RLock()

    def register(self, node_id: str, roles: Optional[List[str]] = None,
                  skills: Optional[List[str]] = None,
                  hardware: Optional[Dict[str, Any]] = None,
                  software: Optional[List[str]] = None) -> CapabilityProfile:
        with self._lock:
            p = self.profiles.get(node_id)
            if p is None:
                p = CapabilityProfile(node_id=node_id)
                self.profiles[node_id] = p
            if roles:
                for r in roles:
                    if r not in p.roles:
                        p.roles.append(r)
            if skills:
                for s in skills:
                    if s not in p.skills:
                        p.skills.append(s)
            if hardware:
                p.hardware.update(hardware)
            if software:
                for s in software:
                    if s not in p.software:
                        p.software.append(s)
            p.last_seen = time.time()
            return p

    def touch(self, node_id: str) -> None:
        with self._lock:
            p = self.profiles.get(node_id)
            if p:
                p.last_seen = time.time()

    def update_load(self, node_id: str, load: float) -> None:
        with self._lock:
            p = self.profiles.get(node_id)
            if p:
                p.load = max(0.0, min(1.0, float(load)))

    def find_by_role(self, role: str, max_load: float = 0.8) -> List[CapabilityProfile]:
        with self._lock:
            return [p for p in self.profiles.values()
                    if role in p.roles and p.load <= max_load]

    def find_by_skill(self, skill: str) -> List[CapabilityProfile]:
        with self._lock:
            return [p for p in self.profiles.values() if skill in p.skills]

    def list_all(self) -> List[CapabilityProfile]:
        with self._lock:
            return list(self.profiles.values())

    def to_dict(self) -> Dict[str, Any]:
        with self._lock:
            return {nid: p.to_dict() for nid, p in self.profiles.items()}


class DynamicSkillMarketplace:
    """Broker local de publicacion, descubrimiento y transferencia de habilidades."""

    def __init__(self) -> None:
        self.skills: Dict[str, SkillModule] = {}
        self._lock = threading.RLock()

    def publish(self, name: str, category: str, description: str = "",
                version: str = "1.0.0", owner: str = "local",
                payload: Optional[Dict[str, Any]] = None,
                requires: Optional[List[str]] = None) -> SkillModule:
        with self._lock:
            sig_payload = {"name": name, "category": category, "version": version, "owner": owner}
            sig = _sign(sig_payload)
            m = SkillModule(skill_id=_uid("skill"), name=name, category=category,
                            description=description, version=version, owner=owner,
                            signature=sig, payload=payload or {},
                            requires=requires or [])
            self.skills[m.skill_id] = m
            return m

    def discover(self, category: Optional[str] = None, query: str = "") -> List[SkillModule]:
        with self._lock:
            items = list(self.skills.values())
            if category:
                items = [s for s in items if s.category == category]
            if query:
                ql = query.lower()
                items = [s for s in items
                         if ql in s.name.lower() or ql in s.description.lower()]
            return items

    def download(self, skill_id: str) -> Optional[SkillModule]:
        with self._lock:
            m = self.skills.get(skill_id)
            if m:
                m.downloads += 1
            return m

    def rate(self, skill_id: str, rating: float) -> Optional[SkillModule]:
        with self._lock:
            m = self.skills.get(skill_id)
            if m:
                m.rating = max(0.0, min(5.0, float(rating)))
            return m

    def to_dict(self) -> Dict[str, Any]:
        with self._lock:
            return {sid: m.to_dict() for sid, m in self.skills.items()}


class RoleSpecializationEngine:
    """Asigna roles especializados a nodos segun capacidades y carga."""

    def __init__(self, registry: Optional[LocalSwarmRoleRegistry] = None,
                 marketplace: Optional[DynamicSkillMarketplace] = None) -> None:
        self.registry = registry or LocalSwarmRoleRegistry()
        self.marketplace = marketplace or DynamicSkillMarketplace()
        self.assignments: Dict[str, RoleAssignment] = {}
        self._lock = threading.RLock()

    def assign_role(self, task_id: str, node_id: str, role: str,
                     metadata: Optional[Dict[str, Any]] = None) -> Optional[RoleAssignment]:
        with self._lock:
            p = self.registry.profiles.get(node_id)
            if p is None:
                return None
            if role not in p.roles:
                return None
            a = RoleAssignment(assignment_id=_uid("assign"), task_id=task_id,
                                node_id=node_id, role=role, metadata=metadata or {})
            self.assignments[a.assignment_id] = a
            return a

    def list_assignments(self, node_id: Optional[str] = None) -> List[RoleAssignment]:
        with self._lock:
            items = list(self.assignments.values())
            if node_id:
                items = [a for a in items if a.node_id == node_id]
            return items

    def status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "nodes": len(self.registry.profiles),
                "skills": len(self.marketplace.skills),
                "assignments": len(self.assignments),
                "roles_active": len({a.role for a in self.assignments.values()}),
            }


_global: Optional[RoleSpecializationEngine] = None
_L = threading.Lock()


def get_swarm_engine() -> RoleSpecializationEngine:
    global _global
    with _L:
        if _global is None:
            _global = RoleSpecializationEngine()
        return _global


def reset_swarm_engine() -> None:
    global _global
    with _L:
        _global = None
