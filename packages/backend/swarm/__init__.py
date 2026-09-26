"""BLOQUE 93 - Motor de especializaci\u00f3n de roles de enjambre y mercado de habilidades."""

from backend.swarm.specialization import (
    DynamicSkillMarketplace,
    LocalSwarmRoleRegistry,
    RoleSpecializationEngine,
    get_swarm_engine,
    reset_swarm_engine,
)
from backend.swarm.models import (
    CapabilityProfile,
    RoleAssignment,
    RoleType,
    SkillCategory,
    SkillModule,
)

__all__ = [
    "DynamicSkillMarketplace",
    "LocalSwarmRoleRegistry",
    "RoleSpecializationEngine",
    "get_swarm_engine",
    "reset_swarm_engine",
    "CapabilityProfile",
    "RoleAssignment",
    "RoleType",
    "SkillCategory",
    "SkillModule",
]

from pkgutil import extend_path
__path__ = extend_path(__path__, __name__)
