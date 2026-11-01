# -*- coding: utf-8 -*-
"""Transcriptor ligero para contexto audio (sin descargar video)."""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger('ARIA.AudioTranscriber')

class AudioTranscriber:
    def __init__(self) -> None:
        self.enabled = False

    async def transcribe_from_url(self, url: str, **kw) -> Optional[str]:
        return None

audio_transcriber = AudioTranscriber()
