# -*- coding: utf-8 -*-
"""ARIA Core - Núcleo unificado ARIA (brain+runtime)
Reutiliza DecisionEngine + Orchestrator + EventBus
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Any, Dict, Optional

from backend.core.decision_engine import DecisionEngine, DecisionType
from backend.core.orchestrator import Orchestrator, get_orchestrator
from backend.core.event_bus import CoreEvent, EventType, get_event_bus
from backend.core.models import Decision

logger = logging.getLogger('ARIA.Core')

class AriaCore:
    def __init__(self) -> None:
        self.bus = get_event_bus()
        self.decision = DecisionEngine()
        self.orch = get_orchestrator()
        self._running = False
        self._session_id = uuid.uuid4().hex[:12]

    def start(self) -> None:
        self.decision.attach(self.bus)
        self._running = True
        self.bus.emit_simple('action', {'stage':'aria_core_start', 'session_id': self._session_id}, agent='aria_core')

    def stop(self) -> None:
        self.decision.detach()
        self._running = False

    async def think(self, prompt: str, context: Dict[str, Any] | None = None) -> Dict[str, Any]:
        res = self.decision.decide(prompt, context or {}, session_id=self._session_id)
        return res

    async def act(self, prompt: str, context: Dict[str, Any] | None = None) -> Dict[str, Any]:
        d = await self.think(prompt, context)
        dec = Decision.model_validate(d['decision'])
        exec_res = await self.orch.execute_decision(dec, session_id=self._session_id)
        return {'thought': d, 'execution': exec_res}

    def status(self) -> Dict[str, Any]:
        return {'running': self._running, 'session_id': self._session_id, 'orch_steps': len(self.orch._steps)}

aria_core = AriaCore()
