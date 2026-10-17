# -*- coding: utf-8 -*-
"""Core browser logic - viewport-only frame capture, no downloads.
"""
from __future__ import annotations

import asyncio
import base64
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger('ARIA.SocialBrowserCore')

def _to_b64(data: bytes) -> str:
    return base64.b64encode(data).decode('utf-8')
