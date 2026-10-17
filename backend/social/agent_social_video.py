# -*- coding: utf-8 -*-
"""Agent para ARIA - entender video/redes sociales sin descargar."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger('ARIA.SocialVideoAgent')

class SocialVideoAgent:
    def __init__(self) -> None:
        self.enabled = True

    async def see_and_understand(self, url: str, **kw) -> Dict[str, Any]:
        try:
            from backend.social import social_browser
            from backend.social.video_stream_analyzer import social_video_analyzer

            browse = await social_browser.browse_and_analyze(url=url, **kw)
            frames_b64 = [{'t': f.t, 'image_b64': f.image_b64, 'mime': f.mime} for f in browse.frames]

            analysis = await social_video_analyzer.analyze_from_frames(
                url=url,
                frames_b64=frames_b64,
            )
            return {
                'ok': True,
                'platform': browse.platform,
                'frames': len(frames_b64),
                'analysis': analysis.__dict__,
                'method': 'viewport-frame-sampling-no-download',
            }
        except Exception as e:
            logger.exception('see_and_understand failed')
            return {'ok': False, 'error': str(e)}

social_video_agent = SocialVideoAgent()
