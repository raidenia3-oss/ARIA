"""BLOQUE 91 - AURA Local Autonomous Code Refactoring & Dynamic Hot-Patching Engine.

Motor 100% local de refactorización autónoma de código y hot-patching dinámico.
Complementa el Bloque 70 (autoevolución) con capacidades específicas de:

- Análisis estático con AST para detección de code smells
- Síntesis de refactorizaciones seguras (rename, extract method, simplify)
- Hot-patching dinámico en caliente (reload de módulos sin reiniciar)
- Auditoría de todos los cambios con hash y rollback

Almacenamiento: data/refactoring91/{patches, backups, logs, metrics/}
"""

from backend.refactoring.engine import (
    DynamicRefactorizer,
    RefactoringEngine,
    HotPatchController,
    CodeAuditor,
    RefactoringType,
    PatchProposal,
    PatchStatus,
    get_engine,
    reset_engine,
    set_engine,
    enable_autostart,
    router,
)
from backend.refactoring.models import (
    RefactoringMetrics,
    RefactoringFinding,
    HotPatchRecord,
    ModuleState,
)

__all__ = [
    # Engine
    "RefactoringEngine",
    "DynamicRefactorizer",
    "HotPatchController",
    "CodeAuditor",
    "get_engine",
    "reset_engine",
    "set_engine",
    "enable_autostart",
    "router",
    # Types & Enums
    "RefactoringType",
    "PatchProposal",
    "PatchStatus",
    # Models
    "RefactoringMetrics",
    "RefactoringFinding",
    "HotPatchRecord",
    "ModuleState",
]

from pkgutil import extend_path
__path__ = extend_path(__path__, __name__)
