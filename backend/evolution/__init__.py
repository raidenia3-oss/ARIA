"""BLOQUE 70 - AURA Local Self-Evolution & Dynamic Code Patching Engine."""

from backend.evolution.patcher import (
    AuditFinding,
    CodeAuditor,
    EvolutionPatchEngine,
    HotReloadController,
    PatchProposal,
    PatchSynthesizer,
    SandboxTester,
    get_engine,
    reset_engine,
    set_engine,
)
from backend.evolution.models import (
    PatchStatus,
    PatchType,
    VersionSnapshot,
)

__all__ = [
    "AuditFinding",
    "CodeAuditor",
    "EvolutionPatchEngine",
    "HotReloadController",
    "PatchProposal",
    "PatchSynthesizer",
    "SandboxTester",
    "get_engine",
    "reset_engine",
    "set_engine",
    "PatchStatus",
    "PatchType",
    "VersionSnapshot",
]

from pkgutil import extend_path
__path__ = extend_path(__path__, __name__)
