# -*- coding: utf-8 -*-
"""ARIA Kernel - Núcleo del personaje ARIA (Gran Sabio)"""
from __future__ import annotations
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional

logger = logging.getLogger('ARIA.Kernel')

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')

class AriaMode(str, Enum):
    REACTIVE = 'reactive'
    AUTONOMOUS = 'autonomous'
    HYBRID = 'hybrid'
    CREATIVE = 'creative'
    ANALYTIC = 'analytic'

class AriaState(str, Enum):
    IDLE = 'idle'
    OBSERVING = 'observing'
    THINKING = 'thinking'
    ACTING = 'acting'
    EVALUATING = 'evaluating'
    PAUSED = 'paused'
    ERROR = 'error'
    RESONATING = 'resonating'

@dataclass
class AriaContext:
    session_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    goal: Optional[str] = None
    focus: Optional[str] = None
    environment: Dict[str, Any] = field(default_factory=dict)
    active_task: Optional[str] = None
    last_observation: Optional[Dict[str, Any]] = None
    last_action: Optional[Dict[str, Any]] = None
    memory_context: Dict[str, Any] = field(default_factory=dict)
    perception_context: Dict[str, Any] = field(default_factory=dict)

@dataclass
class AriaMetrics:
    thoughts: int = 0
    actions: int = 0
    observations: int = 0
    errors: int = 0
    uptime_start: float = field(default_factory=time.time)
    last_heartbeat: float = field(default_factory=time.time)

    @property
    def uptime_s(self) -> float:
        return time.time() - self.uptime_start

class AriaKernel:
    def __init__(self) -> None:
        self.identity = 'ARIA'
        self.description = 'Ambient Runtime Intelligence Assistant - The Grand Sage Core'
        self.mode = AriaMode.HYBRID
        self.state = AriaState.IDLE
        self.context = AriaContext()
        self.metrics = AriaMetrics()

    def set_mode(self, mode: AriaMode) -> None:
        self.mode = mode

    def set_state(self, state: AriaState) -> None:
        self.state = state
        self.metrics.last_heartbeat = time.time()

    def heartbeat(self) -> Dict[str, Any]:
        self.metrics.last_heartbeat = time.time()
        return {
            'identity': self.identity,
            'mode': self.mode.value,
            'state': self.state.value,
            'uptime_s': round(self.metrics.uptime_s, 2),
            'thoughts': self.metrics.thoughts,
            'actions': self.metrics.actions,
            'observations': self.metrics.observations,
            'errors': self.metrics.errors,
            'session_id': self.context.session_id,
            'ts': _now_iso(),
        }

    def status(self) -> Dict[str, Any]:
        return self.heartbeat()

aria_kernel = AriaKernel()
