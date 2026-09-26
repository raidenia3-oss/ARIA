"""Vision Engine for AURA - Multimodal frame and screenshot analysis.

- Preferred: Ollama Vision models (moondream, llava) via HTTP.
- Fallback: OpenCV/PIL lightweight analysis.
- Injects visual context into the Swarm orchestrator.
"""

from __future__ import annotations

import base64
import io
import json
import logging
import os
import time
from typing import Any, Dict, Optional

import numpy as np

try:
    from PIL import Image
except Exception:
    Image = None

try:
    import cv2
except Exception:
    cv2 = None

logger = logging.getLogger("AURAVisionEngine")

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_VISION_MODEL = os.getenv("OLLAMA_VISION_MODEL", "moondream")
VISION_ANALYSIS_INTERVAL = 2.0


def _decode_image(data: Any) -> Optional[Any]:
    try:
        if isinstance(data, str):
            if data.startswith("data:"):
                data = data.split(",", 1)[-1]
            raw = base64.b64decode(data)
        elif isinstance(data, (bytes, bytearray)):
            raw = bytes(data)
        else:
            return None
        if Image is not None:
            return Image.open(io.BytesIO(raw))
        if cv2 is not None:
            arr = np.frombuffer(raw, dtype=np.uint8)
            return cv2.imdecode(arr, cv2.IMREAD_COLOR)
    except Exception:
        return None


def _encode_image_to_base64(image: Any, fmt: str = "JPEG") -> str:
    try:
        buf = io.BytesIO()
        if Image is not None and isinstance(image, Image.Image):
            image.save(buf, format=fmt)
            return base64.b64encode(buf.getvalue()).decode("utf-8")
        if cv2 is not None and isinstance(image, np.ndarray):
            _, raw = cv2.imencode(f".{fmt.lower()}", image)
            return base64.b64encode(raw).decode("utf-8")
    except Exception:
        pass
    return ""


class VisionEngine:
    def __init__(self, orchestrator: Any = None) -> None:
        self.orchestrator = orchestrator
        self._last_analysis: Dict[str, Any] = {}
        self._last_analysis_time = 0.0

    def analyze_frame(self, image_b64: str, session_id: str = "") -> Dict[str, Any]:
        image = _decode_image(image_b64)
        if image is None:
            return {"error": "invalid_image"}

        description = ""
        model_used = "none"
        try:
            description = self._ollama_vision(image)
            model_used = "ollama:" + OLLAMA_VISION_MODEL
        except Exception as exc:
            logger.debug("Ollama vision failed: %s", exc)
            description = self._fallback_analysis(image)
            model_used = "fallback:opencv/pil"

        result = {
            "session_id": session_id,
            "model": model_used,
            "description": description,
            "timestamp": time.time(),
        }
        self._last_analysis = result
        self._last_analysis_time = time.time()
        self._inject_into_orchestrator(result)
        return result

    def analyze_screenshot(self, image_b64: str, session_id: str = "") -> Dict[str, Any]:
        return self.analyze_frame(image_b64, session_id=session_id)

    def _ollama_vision(self, image: Any) -> str:
        if OLLAMA_HOST.startswith("http://localhost") or OLLAMA_HOST.startswith("http://127.0.0.1"):
            try:
                import requests as req
                prompt = "Describe briefly what is shown in this image in Spanish."
                img_b64 = _encode_image_to_base64(image)
                if not img_b64:
                    return ""
                payload = {
                    "model": OLLAMA_VISION_MODEL,
                    "prompt": prompt,
                    "images": [img_b64],
                    "stream": False,
                }
                resp = req.post(f"{OLLAMA_HOST}/api/generate", json=payload, timeout=30)
                if resp.status_code == 200:
                    data = resp.json()
                    return str(data.get("response", "")).strip()
            except Exception as exc:
                logger.debug("Ollama vision request failed: %s", exc)
        return ""

    def _fallback_analysis(self, image: Any) -> str:
        try:
            if cv2 is not None and isinstance(image, np.ndarray):
                h, w = image.shape[:2]
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
                brightness = float(np.mean(gray))
                std = float(np.std(gray))
                blur = cv2.Laplacian(gray, cv2.CV_64F).var()
                return f"Frame {w}x{h}, brillo={brightness:.1f}, contraste={std:.1f}, nitidez={blur:.1f}"
            if Image is not None and isinstance(image, Image.Image):
                w, h = image.size
                gray = image.convert("L")
                arr = np.asarray(gray)
                brightness = float(np.mean(arr))
                std = float(np.std(arr))
                return f"Frame {w}x{h}, brillo={brightness:.1f}, contraste={std:.1f}"
        except Exception:
            pass
        return "Frame recibido, análisis no disponible."

    def _inject_into_orchestrator(self, vision_result: Dict[str, Any]) -> None:
        if not self.orchestrator:
            return
        try:
            if hasattr(self.orchestrator, "set_vision_context"):
                self.orchestrator.set_vision_context(vision_result)
        except Exception:
            pass

    def get_status(self) -> Dict[str, Any]:
        return {
            "model": OLLAMA_VISION_MODEL,
            "last_analysis": self._last_analysis,
            "last_analysis_time": self._last_analysis_time,
        }
