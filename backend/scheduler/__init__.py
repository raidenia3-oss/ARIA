"""BLOQUE 84 - Predictive Intent and Proactive Autonomous Task Scheduler (100% local)."""
from backend.scheduler.predictive import (
    IntentPrediction,
    PredictiveConfig,
    PredictiveEngine,
    ProactiveTask,
    ProactiveTaskScheduler,
    TriggerRule,
    get_predictive_engine,
    reset_predictive_engine,
)
from backend.scheduler.predictive_routes import router as predictive_router

__all__ = [
    "IntentPrediction",
    "PredictiveConfig",
    "PredictiveEngine",
    "ProactiveTask",
    "ProactiveTaskScheduler",
    "TriggerRule",
    "get_predictive_engine",
    "reset_predictive_engine",
    "predictive_router",
]

from pkgutil import extend_path
__path__ = extend_path(__path__, __name__)
