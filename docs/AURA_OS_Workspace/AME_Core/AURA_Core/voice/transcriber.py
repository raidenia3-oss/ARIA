import os
import time
import logging
from typing import Optional

import requests

logger = logging.getLogger("AURA_Voice")


class Transcriber:
    def __init__(self, lm_studio_url: Optional[str] = None):
        self.lm_studio_url = lm_studio_url or os.getenv(
            "AURA_LM_STUDIO_URL", "http://127.0.0.1:1234"
        )

    def transcribe(self, wav_bytes: bytes, language: str = "es") -> str:
        if not wav_bytes:
            return ""
        try:
            t0 = time.time()
            resp = requests.post(
                f"{self.lm_studio_url}/v1/audio/transcriptions",
                files={"file": ("audio.wav", wav_bytes, "audio/wav")},
                data={"model": "whisper", "language": language},
                timeout=30,
            )
            resp.raise_for_status()
            text = (resp.json().get("text") or "").strip()
            logger.info(
                " Transcripcion recibida (%d chars, %.2fs)",
                len(text),
                time.time() - t0,
            )
            return text
        except Exception as exc:
            logger.error(" Transcripcion fallida: %s", exc)
            return ""
