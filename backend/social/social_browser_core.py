# -*- coding: utf-8 -*-
"""Core browser logic - viewport-only frame capture, no downloads.
Reutiliza enfoque: captura frames renderizados (screenshot/element) en memoria.
"""
from __future__ import annotations

import asyncio
import base64
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger('ARIA.SocialBrowserCore')

PLAYWRIGHT_AVAILABLE = False
try:
    from playwright.async_api import async_playwright  # type: ignore
    PLAYWRIGHT_AVAILABLE = True
except Exception:
    PLAYWRIGHT_AVAILABLE = False

def _to_b64(data: bytes) -> str:
    return base64.b64encode(data).decode('utf-8')

async def capture_frames_viewport(
    url: str,
    max_frames: int = 15,
    interval_ms: int = 500,
    timeout_ms: int = 30000,
    viewport: Optional[Dict[str, int]] = None,
    user_agent: Optional[str] = None,
    wait_video_ms: int = 1500,
    headless: bool = True,
) -> List[Dict[str, Any]]:
    """Captura frames renderizados SOLO viewport (sin descargar MP4)."""
    frames: List[Dict[str, Any]] = []
    if not PLAYWRIGHT_AVAILABLE:
        logger.warning('Playwright no disponible. Devuelve frames vacios (modo stub).')
        return frames
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context(
            viewport=viewport or {'width': 390, 'height': 844},
            user_agent=user_agent or 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1',
            locale='es-ES',
            timezone_id='Europe/Madrid',
        )
        page = await context.new_page()
        try:
            await page.goto(url, wait_until='domcontentloaded', timeout=timeout_ms)
            await page.wait_for_timeout(wait_video_ms)
            start = asyncio.get_event_loop().time()
            for i in range(max_frames):
                try:
                    shot = await page.screenshot(type='jpeg', quality=85, full_page=False)
                except Exception:
                    shot = await page.screenshot(type='jpeg', full_page=False)
                t = asyncio.get_event_loop().time() - start
                frames.append({'t': round(t, 2), 'image_b64': _to_b64(shot), 'mime': 'image/jpeg'})
                await page.wait_for_timeout(interval_ms)
        except Exception as e:
            logger.debug('capture_frames_viewport error: %s', e)
        finally:
            await browser.close()
    return frames
