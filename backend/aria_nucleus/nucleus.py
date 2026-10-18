# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any, Dict, Optional

from backend.core.event_bus import get_event_bus
from backend.core.models import Decision
from backend.aria_nucleus.kernel import aria_kernel, AriaMode, AriaState
from backend.aria_nucleus.perception import AriaPerception
from backend.aria_nucleus.cognition import AriaCognition
from backend.aria_nucleus.execution import AriaExecution
from backend.aria_nucleus.memory import AriaMemory

logger = logging.getLogger('ARIA.Nucleus')

class AriaNucleus:
    def __init__(self) -> None:
        self.kernel = aria_kernel
        self.perception = AriaPerception()
        self.cognition = AriaCognition()
        self.execution = AriaExecution()
        self.memory = AriaMemory()
        self.bus = get_event_bus()
        self._running = False
        self._loop_task: Optional[asyncio.Task] = None

    def start(self) -> None:
        self.cognition.attach(self.bus)
        self._running = True
        self.kernel.set_state(AriaState.IDLE)
        self.bus.emit_simple('action', {'stage': 'aria_nucleus_start', 'session_id': self.kernel.context.session_id}, agent='aria')

    def stop(self) -> None:
        self.cognition.detach()
        self._running = False
        if self._loop_task and not self._loop_task.done():
            try:
                self._loop_task.cancel()
            except Exception:
                pass

    async def understand(self, input_: str, **kw) -> Dict[str, Any]:
        self.kernel.set_state(AriaState.OBSERVING)
        self.kernel.metrics.observations += 1
        return await self.perception.understand(input_, **kw)

    async def think(self, prompt: str, context: Dict[str, Any] | None = None) -> Dict[str, Any]:
        self.kernel.set_state(AriaState.THINKING)
        self.kernel.metrics.thoughts += 1
        res = self.cognition.think(prompt, context or {}, session_id=self.kernel.context.session_id)
        return res

    async def act(self, prompt: str, context: Dict[str, Any] | None = None) -> Dict[str, Any]:
        d = await self.think(prompt, context)
        dec = Decision.model_validate(d['decision'])
        self.kernel.set_state(AriaState.ACTING)
        self.kernel.metrics.actions += 1
        exec_res = await self.execution.act(dec, self.kernel.context.session_id)
        self.kernel.set_state(AriaState.EVALUATING)
        return {'thought': d, 'execution': exec_res}

    async def process(self, input_: str, **kw) -> Dict[str, Any]:
        t = input_.lower()
        if t.startswith('http://') or t.startswith('https://'):
            return await self.perception.understand(input_, **kw)
        return await self.act(input_, kw.get('context'))

    def status(self) -> Dict[str, Any]:
        return {'kernel': self.kernel.status(), 'running': self._running}

    async def _autonomous_loop(self, interval: float = 30.0) -> None:
        while self._running and self.kernel.mode in (AriaMode.AUTONOMOUS, AriaMode.HYBRID, AriaMode.CREATIVE, AriaMode.ANALYTIC):
            try:
                await asyncio.sleep(interval)
            except Exception:
                break

    def start_autonomous(self, interval: float = 30.0) -> None:
        self.kernel.set_mode(AriaMode.AUTONOMOUS)
        if not self._loop_task or self._loop_task.done():
            self._loop_task = asyncio.create_task(self._autonomous_loop(interval))

aria_nucleus = AriaNucleus()
