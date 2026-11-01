# -*- coding: utf-8 -*-
"""SEVEN UNIVERSES — universe definitions and registry.

Each universe is a scoped execution context: a set of agents, a resource
budget and a color identity. Tasks are routed to universes by the
UniverseRegistry, and the NEXUS coordinator is the only cross-universe
channel (no direct A->B).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class Universe(str, Enum):
    """The 7 universes from the SEVEN UNIVERSES reference video."""

    ADMIN = "admin"
    CODING = "coding"
    MEDIA = "media"
    KNOWLEDGE = "knowledge"
    INTEGRATION = "integration"
    UIUX = "ui_ux"
    NEXUS = "nexus"

    @classmethod
    def from_string(cls, value: str) -> "Universe":
        try:
            return cls(value)
        except ValueError:
            return cls.NEXUS


@dataclass
class UniverseSpec:
    """Visual + behavioral specification for one universe."""

    universe: Universe
    name: str
    color: str
    icon: str
    description: str
    capabilities: List[str] = field(default_factory=list)
    max_concurrent: int = 4
    cpu_share: float = 0.25


UNIVERSE_SPECS: Dict[Universe, UniverseSpec] = {
    Universe.ADMIN: UniverseSpec(
        universe=Universe.ADMIN,
        name="Admin",
        color="#FF3333",
        icon="🛡️",
        description="System administration and configuration",
        capabilities=["config", "users", "permissions", "audit"],
        max_concurrent=2,
        cpu_share=0.10,
    ),
    Universe.CODING: UniverseSpec(
        universe=Universe.CODING,
        name="Coding",
        color="#00FF99",
        icon="💻",
        description="Code generation, review and testing",
        capabilities=["generate", "review", "test", "refactor"],
        max_concurrent=8,
        cpu_share=0.35,
    ),
    Universe.MEDIA: UniverseSpec(
        universe=Universe.MEDIA,
        name="Media",
        color="#00FFFF",
        icon="🎬",
        description="Video, audio and image processing",
        capabilities=["video", "audio", "image", "render"],
        max_concurrent=4,
        cpu_share=0.20,
    ),
    Universe.KNOWLEDGE: UniverseSpec(
        universe=Universe.KNOWLEDGE,
        name="Knowledge",
        color="#BB00FF",
        icon="📚",
        description="Research, memory and semantic search",
        capabilities=["search", "recall", "summarize", "embed"],
        max_concurrent=4,
        cpu_share=0.15,
    ),
    Universe.INTEGRATION: UniverseSpec(
        universe=Universe.INTEGRATION,
        name="Integration",
        color="#FFAA00",
        icon="🔌",
        description="External API, cloud and device sync",
        capabilities=["api", "cloud", "device", "webhook"],
        max_concurrent=6,
        cpu_share=0.20,
    ),
    Universe.UIUX: UniverseSpec(
        universe=Universe.UIUX,
        name="UI/UX",
        color="#FF0099",
        icon="🎨",
        description="Interface design and user experience",
        capabilities=["design", "layout", "animation", "theme"],
        max_concurrent=3,
        cpu_share=0.10,
    ),
    Universe.NEXUS: UniverseSpec(
        universe=Universe.NEXUS,
        name="NEXUS",
        color="#FFFFFF",
        icon="⭐",
        description="Central coordinator — the only cross-universe channel",
        capabilities=["route", "coordinate", "aggregate", "dispatch"],
        max_concurrent=2,
        cpu_share=0.10,
    ),
}


def universe_to_dict(spec: UniverseSpec) -> Dict:
    return {
        "universe": spec.universe.value,
        "name": spec.name,
        "color": spec.color,
        "icon": spec.icon,
        "description": spec.description,
        "capabilities": list(spec.capabilities),
        "max_concurrent": spec.max_concurrent,
        "cpu_share": spec.cpu_share,
    }


class UniverseRegistry:
    """Routes tasks to universes and tracks per-universe load.

    Cross-universe communication is forbidden: any agent that wants to talk
    to another universe must go through NEXUS. This is enforced by
    :meth:`route`, which returns ``None`` for direct cross-universe routes.
    """

    def __init__(self) -> None:
        self._load: Dict[Universe, int] = {u: 0 for u in Universe}
        self._blocked_routes: int = 0

    def list_universes(self) -> List[Dict]:
        return [universe_to_dict(UNIVERSE_SPECS[u]) for u in Universe]

    def get_spec(self, universe: Universe) -> Optional[UniverseSpec]:
        return UNIVERSE_SPECS.get(universe)

    def can_accept(self, universe: Universe) -> bool:
        spec = UNIVERSE_SPECS.get(universe)
        if spec is None:
            return False
        return self._load.get(universe, 0) < spec.max_concurrent

    def route(self, source: Universe, target: Universe, task: str = "") -> Optional[Universe]:
        """Route a task, enforcing the NEXUS-only cross-universe rule.

        Returns the target universe when the route is allowed, or ``None``
        when it is blocked. Direct A->B routes are blocked and counted so the
        dashboard can show how many times the policy was enforced.
        """
        if source == target:
            return target
        if source != Universe.NEXUS and target != Universe.NEXUS:
            self._blocked_routes += 1
            return None
        if not self.can_accept(target):
            return None
        return target

    def register_task(self, universe: Universe) -> bool:
        if not self.can_accept(universe):
            return False
        self._load[universe] = self._load.get(universe, 0) + 1
        return True

    def release_task(self, universe: Universe) -> None:
        self._load[universe] = max(0, self._load.get(universe, 0) - 1)

    def load_snapshot(self) -> Dict[str, Any]:
        return {
            "load": {u.value: self._load.get(u, 0) for u in Universe},
            "blocked_routes": self._blocked_routes,
            "total_universes": len(Universe),
        }


def get_universe_spec(universe: Universe) -> Optional[UniverseSpec]:
    return UNIVERSE_SPECS.get(universe)