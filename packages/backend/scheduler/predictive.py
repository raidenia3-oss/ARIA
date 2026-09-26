"""BLOQUE 84 - backend.scheduler.predictive shim (100% local/offline).

Re-exporta el motor canonico de backend.predictive.intent con alias
compatibles con el contrato esperado por backend.scheduler/__init__.py:
IntentPrediction, PredictiveConfig, PredictiveEngine, ProactiveTask,
ProactiveTaskScheduler, TriggerRule, get/reset_predictive_engine.

Sin dependencias cloud, sin secretos, desacoplado de fusion/runner
(solo se consume via observe() con snapshots ya calculados).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from backend.predictive.intent import (
    AUTO_THRESHOLD,
    CONFIRM_THRESHOLD,
    IntentAnalyzer,
    IntentHypothesis,
    PredictiveEngine as _CoreEngine,
    ProactiveTask,
    TaskGatekeeper,
    get_predictive_engine as _get_core,
    reset_predictive_engine as _reset_core,
)

# Alias de compatibilidad: una prediccion de intencion es una hipotesis.
IntentPrediction = IntentHypothesis

# Scheduler proactivo = gatekeeper local con umbrales estrictos.
ProactiveTaskScheduler = TaskGatekeeper

# Re-export del motor canonico.
PredictiveEngine = _CoreEngine


@dataclass
class PredictiveConfig:
    """Umbrales estrictos de confianza predictiva (solo local)."""

    confirm_threshold: float = CONFIRM_THRESHOLD
    auto_threshold: float = AUTO_THRESHOLD

    def __post_init__(self) -> None:
        assert 0 < self.confirm_threshold < self.auto_threshold < 1.0, (
            "umbrales invalidos: 0 < confirm < auto < 1.0"
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "confirm_threshold": self.confirm_threshold,
            "auto_threshold": self.auto_threshold,
            "offline_only": True,
        }


@dataclass
class TriggerRule:
    """Regla declarativa: que intencion dispara que accion y con que impacto."""

    intent: str = ""
    action: str = ""
    impact: str = "low"
    min_confidence: float = CONFIRM_THRESHOLD
    signals: List[str] = field(default_factory=list)

    def matches(self, hyp: IntentHypothesis) -> bool:
        return (
            hyp.intent == self.intent
            and hyp.confidence >= self.min_confidence
            and hyp.impact == self.impact
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent": self.intent,
            "action": self.action,
            "impact": self.impact,
            "min_confidence": self.min_confidence,
            "signals": list(self.signals),
            "offline_only": True,
        }


def get_predictive_engine() -> _CoreEngine:
    return _get_core()


def reset_predictive_engine() -> None:
    _reset_core()


__all__ = [
    "AUTO_THRESHOLD",
    "CONFIRM_THRESHOLD",
    "IntentAnalyzer",
    "IntentPrediction",
    "IntentHypothesis",
    "PredictiveConfig",
    "PredictiveEngine",
    "ProactiveTask",
    "ProactiveTaskScheduler",
    "TaskGatekeeper",
    "TriggerRule",
    "get_predictive_engine",
    "reset_predictive_engine",
]
