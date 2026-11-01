# -*- coding: utf-8 -*-
"""Detecta formato de contenido social (reels, shorts, story, live, post)."""
from __future__ import annotations

import logging
from typing import Dict

logger = logging.getLogger('ARIA.SocialFormat')

FORMATS = ['reels', 'shorts', 'story', 'video', 'photo', 'carousel', 'live', 'post']

class SocialFormatDetector:
    def detect(self, url: str, title: str = '') -> Dict[str, str]:
        u = url.lower()
        if 'stories' in u or '/stories/' in u: return {'format': 'story', 'type': 'vertical'}
        if 'reels' in u: return {'format': 'reels', 'type': 'vertical'}
        if 'shorts' in u or 'youtu.be' in u: return {'format': 'shorts', 'type': 'vertical'}
        if 'live' in u: return {'format': 'live', 'type': 'mixed'}
        if 'video' in u: return {'format': 'video', 'type': 'horizontal'}
        return {'format': 'post', 'type': 'mixed'}

detector = SocialFormatDetector()
