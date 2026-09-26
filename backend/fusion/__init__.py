"""BLOQUE 83 - Fusion package re-exports (100% local, offline)."""
from backend.fusion.sensory import (
    ContextEvaluator,
    ContextSnapshot,
    FusionEngine,
    SensorEvent,
    SensoryBus,
    get_fusion_engine,
    reset_fusion_engine,
)

__all__ = [
    "ContextEvaluator",
    "ContextSnapshot",
    "FusionEngine",
    "SensorEvent",
    "SensoryBus",
    "get_fusion_engine",
    "reset_fusion_engine",
]

from pkgutil import extend_path
__path__ = extend_path(__path__, __name__)
