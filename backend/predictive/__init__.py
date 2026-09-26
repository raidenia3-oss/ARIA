"""BLOQUE 84 - Predictive package re-exports (100% local, offline)."""
from backend.predictive.intent import (
    CONFIRM_THRESHOLD,
    AUTO_THRESHOLD,
    IntentHypothesis,
    IntentAnalyzer,
    ProactiveTask,
    TaskGatekeeper,
    PredictiveEngine,
    get_predictive_engine,
    reset_predictive_engine,
)
__all__ = ["CONFIRM_THRESHOLD", "AUTO_THRESHOLD", "IntentHypothesis", "IntentAnalyzer",
           "ProactiveTask", "TaskGatekeeper", "PredictiveEngine",
           "get_predictive_engine", "reset_predictive_engine"]

from pkgutil import extend_path
__path__ = extend_path(__path__, __name__)
