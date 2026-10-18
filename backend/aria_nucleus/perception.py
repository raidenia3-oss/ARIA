# -*- coding: utf-8 -*-
from __future__ import annotations
import logging
from typing import Any, Dict
from backend.services.vision_engine import VisionEngine
from backend.social.social_understander import social_understander
from backend.social.social_format_detector import detector

logger = logging.getLogger('ARIA.Perception')

class AriaPerception:
    def __init__(self) -> None:
        self.vision = VisionEngine()
    async def understand(self, input_: str, **kw) -> Dict[str, Any]:
        t = input_.lower()
        if t.startswith('http://') or t.startswith('https://'):
            res = await social_understander.understand(input_, **kw)
            res['perception_mode'] = 'social_unified'
            return res
        fmt = detector.detect(input_)
        return {'ok': True, 'type': 'text', 'input': input_, 'format': fmt, 'perception_mode': 'text'}
    def status(self): return {'ok': True}
