# -*- coding: utf-8 -*-
"""Inicialización del módulo backend de AURA OS."""
from __future__ import annotations

from pkgutil import extend_path
__path__ = extend_path(__path__, __name__)

from backend.core.event_bus import get_event_bus
from backend.core.receiver_hub import get_receiver_hub
from backend.core.context_analyzer import get_context_analyzer
from backend.core.decision_engine import get_decision_engine
from backend.core.models import EventType


def init_aura_core() -> None:
    """Inicializa el núcleo de AURA OS.

    El núcleo unificado (UnifiedOrchestrator) es el encargado de orquestar
    ReceiverHub → ContextAnalyzer → DecisionEngine → ParallelExecutor.
    El EventBus es push-driven y no requiere suscripción de handle_event
    para el flujo principal.
    """
    event_bus = get_event_bus()
    event_bus.start()

    # Singletons se crean al instanciarse (lazy, seguros)
    get_receiver_hub()
    get_context_analyzer()
    get_decision_engine()


init_aura_core()