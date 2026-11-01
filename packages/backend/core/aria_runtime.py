# -*- coding: utf-8 -*-
"""ARIA Runtime - runtime unificado, autónomo."""
from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any, Dict

from backend.core.ar_core import aria_core
from backend.core.event_bus import get_event_bus
from backend.social.social_understander import social_understander

logger = logging.getLogger('ARIA.Runtime')

class AriaRuntime:
    def __init__(self) -> None:
        self.core = aria_core
        self.bus = get_event_bus()
        self._id = uuid.uuid4().hex[:10]
        self._started = False

    async def start(self) -> None:
        if self._started:
            return
        self.core.start()
        self.bus.emit_simple('action', {'stage': 'aria_runtime_start', 'id': self._id}, agent='aria_runtime')
        self._started = True

    async def stop(self) -> None:
        if not self._started:
            return
        self.core.stop()
        self._started = False

    async def understand(self, text_or_url: str, **kw) -> Dict[str, Any]:
        t = text_or_url.lower()
        if t.startswith('http://') or t.startswith('https://'):
            return await social_understander.understand(text_or_url, **kw)
        ctx = kw.get('context') or {}
        return await self.core.act(text_or_url, ctx)

    def status(self) -> Dict[str, Any]:
        return {'started': self._started, 'id': self._id, 'core': self.core.status()}

aria_runtime = AriaRuntime()
