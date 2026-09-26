"""Humanization utilities for browser automation."""

from __future__ import annotations

import asyncio
import random
import time
from typing import Optional


async def smart_delay(min_seconds: float = 1.0, max_seconds: float = 3.0) -> None:
    delay = random.uniform(min_seconds, max_seconds)
    await asyncio.sleep(delay)


async def human_type(page, selector: str, text: str) -> None:
    await smart_delay(0.1, 0.3)
    for char in text:
        await page.type(selector, char)
        await asyncio.sleep(random.uniform(0.05, 0.15))


async def human_click(page, selector: str) -> None:
    await smart_delay(0.2, 0.5)
    await page.click(selector)
    await smart_delay(0.3, 0.8)
