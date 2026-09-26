"""BLOQUE 103 - Local Comprehensive E2E Integration Testing & Swarm Stress-Test.

Paquete 100% local y soberano: suite de integracion E2E de ecosistema
completo + runner de estres/concurrente del enjambre. Sin cloud, sin
telemetria externa, sin secretos en texto plano.
"""
from __future__ import annotations

from backend.testing.engine import MatrixEngine, MAX_AGENTS, MAX_OPS_PER_AGENT
from backend.testing.models import (
    ALL_CHAIN_STEPS,
    ChainStep,
    MatrixReport,
    StepResult,
    StressReport,
    SuiteStatus,
)
from backend.testing.steps import STEP_FNS

__all__ = [
    "MatrixEngine", "MAX_AGENTS", "MAX_OPS_PER_AGENT",
    "ALL_CHAIN_STEPS", "ChainStep", "MatrixReport",
    "StepResult", "StressReport", "SuiteStatus", "STEP_FNS",
]

from pkgutil import extend_path
__path__ = extend_path(__path__, __name__)
