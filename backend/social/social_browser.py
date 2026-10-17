# -*- coding: utf-8 -*-
"""ARIA Social Browser - Navegacion universal sin descargar nada.

Playwright para navegar. Captura SOLO frames renderizados (viewport).
Nunca descarga MP4 u otros binarios. Todo en memoria (base64).
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Callable

logger = logging.getLogger('ARIA.SocialBrowser')

PLATFORMS = {
    'instagram': ['instagram.com', 'www.instagram.com'],
    'tiktok': ['tiktok.com', 'www.tiktok.com'],
    'youtube': ['youtube.com', 'youtu.be', 'www.youtube.com'],
    'x': ['x.com', 'twitter.com', 'www.x.com', 'www.twitter.com'],
    'facebook': ['facebook.com', 'fb.watch', 'www.facebook.com'],
    'linkedin': ['linkedin.com', 'www.linkedin.com'],
    'threads': ['threads.net', 'www.threads.net'],
    'bluesky': ['bsky.app', 'www.bsky.app'],
    'pinterest': ['pinterest.com', 'www.pinterest.com'],
    'reddit': ['reddit.com', 'www.reddit.com'],
    'snapchat': ['snapchat.com', 'www.snapchat.com'],
}

@dataclass
class Frame:
    t: float
    image_b64: str
    mime: str = 'image/jpeg'

@dataclass
class BrowseResult:
    url: str
    platform: str
    title: str
    description: str
    frames: List[Frame]
    audio_transcript_hint: Optional[str] = None
    metadata: Dict[str, Any] = None
    ts: str = datetime.utcnow().isoformat() + 'Z'

def guess_platform(url: str) -> str:
    u = url.lower()
    for plat, hosts in PLATFORMS.items():
        for h in hosts:
            if h in u:
                return plat
    return 'generic'
