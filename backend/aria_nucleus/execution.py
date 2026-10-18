# -*- coding: utf-8 -*-
from __future__ import annotations
import logging
from typing import Any, Dict
from backend.core.orchestrator import get_orchestrator
logger = logging.getLogger('ARIA.Execution')
class AriaExecution:
    def __init__(self): self.orch = get_orchestrator()
    async def act(self,decision,session_id:str): return await self.orch.execute_decision(decision,session_id)
    def status(self): return {'steps': len(getattr(self.orch,'_steps',{}))}
