# -*- coding: utf-8 -*-
from __future__ import annotations
import logging
from typing import Any, Dict
from backend.core.decision_engine import DecisionEngine
logger = logging.getLogger('ARIA.Cognition')
class AriaCognition:
    def __init__(self): self.decision = DecisionEngine()
    def attach(self,b=None): self.decision.attach(b)
    def detach(self): self.decision.detach()
    def think(self,prompt:str,context:Dict[str,Any]|None=None,session_id:str=''):
        ctx=dict(context or {}); ctx.setdefault('mode','aria_cognition')
        return self.decision.decide(prompt,ctx,session_id=session_id)
