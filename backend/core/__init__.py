# Inicialización del módulo core de AURA OS
# -*- coding: utf-8 -*-
"""
AURA OS — Chunk 1: Core (receiver hub, context analyzer, decision engine,
event bus y modelos Pydantic v2).

Exporta los símbolos públicos del núcleo y sus singletons.
"""
from backend.core.event_bus import (
    CoreEvent,
    EventBus,
    EventType,
    get_event_bus,
    reset_event_bus,
)
from backend.core.models import (
    ActionResult,
    CoreStatus,
    Decision,
    DecisionStep,
    DecisionType,
    InputType,
    ProcessingResult,
    UnifiedInput,
)
from backend.core.receiver_hub import (
    ReceiverHub,
    get_receiver_hub,
    reset_receiver_hub,
)
from backend.core.context_analyzer import (
    ContextAnalyzer,
    get_context_analyzer,
    reset_context_analyzer,
)
from backend.core.decision_engine import (
    DecisionEngine,
    get_decision_engine,
    reset_decision_engine,
)

__all__ = [
    # event bus
    "CoreEvent",
    "EventBus",
    "EventType",
    "get_event_bus",
    "reset_event_bus",
    # models
    "ActionResult",
    "CoreStatus",
    "Decision",
    "DecisionStep",
    "DecisionType",
    "InputType",
    "ProcessingResult",
    "UnifiedInput",
    # receiver hub
    "ReceiverHub",
    "get_receiver_hub",
    "reset_receiver_hub",
    # context analyzer
    "ContextAnalyzer",
    "get_context_analyzer",
    "reset_context_analyzer",
    # decision engine
    "DecisionEngine",
    "get_decision_engine",
    "reset_decision_engine",
]

from pkgutil import extend_path
__path__ = extend_path(__path__, __name__)
