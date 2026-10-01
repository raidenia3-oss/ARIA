"""APEX agent role definitions — 12 specialized roles with visual identity.

Each role carries a name, hex color, icon, description and capability list so
the status dashboard can render an orbit of color-coded nodes around a central
NEXUS coordinator, exactly as shown in the APEX reference video.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List


class AgentRole(str, Enum):
    """12 agent roles from the APEX reference video."""

    ARCHITECT = "architect"
    DEVOPS = "devops"
    SECURITY = "security"
    CODE_REVIEW = "code_review"
    REFACTOR = "refactor"
    TEST_GEN = "test_gen"
    MONITOR = "monitor"
    INCIDENT = "incident"
    LEARNING = "learning"
    MEMORY = "memory"
    PATTERN = "pattern"
    SUGGESTION = "suggestion"

    @classmethod
    def from_string(cls, value: str) -> "AgentRole":
        """Best-effort lookup; returns ``ARCHITECT`` for unknown values so a
        malformed role never crashes the registry."""
        try:
            return cls(value)
        except ValueError:
            return cls.ARCHITECT


@dataclass
class RoleSpec:
    """Visual + behavioral specification for one agent role."""

    name: str
    role: AgentRole
    color: str  # Hex color
    icon: str   # Unicode / emoji
    description: str
    capabilities: List[str] = field(default_factory=list)


ROLE_SPECS: Dict[AgentRole, RoleSpec] = {
    AgentRole.ARCHITECT: RoleSpec(
        name="Architect",
        role=AgentRole.ARCHITECT,
        color="#FFD700",  # Gold
        icon="🏗️",
        description="System design and architecture decisions",
        capabilities=["design", "planning", "structure"],
    ),
    AgentRole.DEVOPS: RoleSpec(
        name="DevOps",
        role=AgentRole.DEVOPS,
        color="#FF6B6B",  # Red
        icon="⚙️",
        description="Infrastructure and deployment",
        capabilities=["deploy", "monitor", "scale"],
    ),
    AgentRole.SECURITY: RoleSpec(
        name="Security",
        role=AgentRole.SECURITY,
        color="#8B008B",  # Purple
        icon="🔒",
        description="Security audits and vulnerability checks",
        capabilities=["audit", "scan", "harden"],
    ),
    AgentRole.CODE_REVIEW: RoleSpec(
        name="Code Review",
        role=AgentRole.CODE_REVIEW,
        color="#00CED1",  # Cyan
        icon="👁️",
        description="Code review and quality assurance",
        capabilities=["review", "lint", "test"],
    ),
    AgentRole.REFACTOR: RoleSpec(
        name="Refactor",
        role=AgentRole.REFACTOR,
        color="#32CD32",  # Green
        icon="🔄",
        description="Code refactoring and optimization",
        capabilities=["optimize", "simplify", "improve"],
    ),
    AgentRole.TEST_GEN: RoleSpec(
        name="Test Gen",
        role=AgentRole.TEST_GEN,
        color="#FF8C00",  # Orange
        icon="🧪",
        description="Automated test generation",
        capabilities=["generate", "test", "coverage"],
    ),
    AgentRole.MONITOR: RoleSpec(
        name="Monitor",
        role=AgentRole.MONITOR,
        color="#1E90FF",  # Dodger Blue
        icon="📊",
        description="System monitoring and metrics",
        capabilities=["monitor", "alert", "report"],
    ),
    AgentRole.INCIDENT: RoleSpec(
        name="Incident",
        role=AgentRole.INCIDENT,
        color="#FF4500",  # Orange Red
        icon="🚨",
        description="Incident response and recovery",
        capabilities=["respond", "recover", "debug"],
    ),
    AgentRole.LEARNING: RoleSpec(
        name="Learning",
        role=AgentRole.LEARNING,
        color="#9370DB",  # Medium Purple
        icon="📚",
        description="Continuous learning and adaptation",
        capabilities=["learn", "improve", "adapt"],
    ),
    AgentRole.MEMORY: RoleSpec(
        name="Memory",
        role=AgentRole.MEMORY,
        color="#20B2AA",  # Light Sea Green
        icon="💾",
        description="Memory management and context",
        capabilities=["store", "retrieve", "manage"],
    ),
    AgentRole.PATTERN: RoleSpec(
        name="Pattern",
        role=AgentRole.PATTERN,
        color="#DC143C",  # Crimson
        icon="🔍",
        description="Pattern recognition and analysis",
        capabilities=["detect", "analyze", "predict"],
    ),
    AgentRole.SUGGESTION: RoleSpec(
        name="Suggestion",
        role=AgentRole.SUGGESTION,
        color="#FFB6C1",  # Light Pink
        icon="💡",
        description="Suggestions and recommendations",
        capabilities=["suggest", "recommend", "advise"],
    ),
}


def get_role_spec(role: AgentRole) -> RoleSpec:
    """Get the spec for a role, falling back to ARCHITECT for unknowns."""
    return ROLE_SPECS.get(role, ROLE_SPECS[AgentRole.ARCHITECT])


def get_all_roles() -> List[RoleSpec]:
    """Return every role spec in enum order."""
    return [ROLE_SPECS[r] for r in AgentRole]


def role_to_dict(role: AgentRole) -> dict:
    """Serialize a role spec to a plain dict for JSON responses."""
    spec = get_role_spec(role)
    return {
        "role": role.value,
        "name": spec.name,
        "color": spec.color,
        "icon": spec.icon,
        "description": spec.description,
        "capabilities": list(spec.capabilities),
    }


# Alias so callers can refer to the APEX role enum without colliding with the
# `AgentRole` already defined in `backend.agent_swarm` (the 5-role swarm enum).
APEXAgentRole = AgentRole