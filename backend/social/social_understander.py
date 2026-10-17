# -*- coding: utf-8 -*-
"""Mejora comprensión: fusiona formato + análisis + contexto."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from backend.social.social_format_detector import detector
from backend.social import agent_social_video

logger = logging.getLogger('ARIA.SocialUnderstander')

class SocialUnderstander:
    async def understand(self, url: str, max_frames: int = 8, **kw) -> Dict[str, Any]:
        fmt = detector.detect(url)
        res = await agent_social_video.social_video_agent.see_and_understand(url, max_frames=max_frames, **kw)
        res['format'] = fmt
        return res

social_understander = SocialUnderstander()
