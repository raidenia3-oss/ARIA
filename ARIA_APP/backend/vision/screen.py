"""ARIA Screen Intelligence — capture, OCR, and basic analysis."""

from __future__ import annotations

import base64
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple


@dataclass
class ScreenCapture:
    path: str
    width: int
    height: int
    captured_at: float
    base64: str = ""


class ScreenIntelligence:
    def __init__(self, screenshots_dir: Optional[str] = None) -> None:
        if screenshots_dir is None:
            base = os.path.dirname(__file__)
            screenshots_dir = os.path.abspath(os.path.join(base, "../../logs/screenshots"))
        self.screenshots_dir = screenshots_dir
        os.makedirs(self.screenshots_dir, exist_ok=True)
        self._last_capture: Optional[ScreenCapture] = None

    def capture(self, region: Optional[Tuple[int, int, int, int]] = None) -> Dict[str, Any]:
        try:
            import pyautogui  # type: ignore

            screenshot = pyautogui.screenshot(region=region)
            ts = int(time.time() * 1000)
            path = os.path.join(self.screenshots_dir, f"screen-{ts}.png")
            screenshot.save(path)
            with open(path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("utf-8", errors="ignore")
            capture = ScreenCapture(
                path=path,
                width=screenshot.width,
                height=screenshot.height,
                captured_at=time.time(),
                base64=b64,
            )
            self._last_capture = capture
            return {
                "status": "ok",
                "path": path,
                "width": screenshot.width,
                "height": screenshot.height,
                "base64": b64[:200] + "...",
                "captured_at": capture.captured_at,
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def analyze(self, image_path: Optional[str] = None) -> Dict[str, Any]:
        target = image_path or (self._last_capture.path if self._last_capture else None)
        if not target or not os.path.exists(target):
            return {"status": "error", "error": "no capture available"}
        try:
            text = self._ocr(target)
            return {
                "status": "ok",
                "image": target,
                "ocr_text": text[:1000],
                "text_length": len(text),
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def last(self) -> Dict[str, Any]:
        if not self._last_capture:
            return {"status": "error", "error": "no capture yet"}
        return {
            "status": "ok",
            "path": self._last_capture.path,
            "width": self._last_capture.width,
            "height": self._last_capture.height,
            "captured_at": self._last_capture.captured_at,
        }

    def _ocr(self, image_path: str) -> str:
        try:
            import pytesseract  # type: ignore
            from PIL import Image  # type: ignore

            img = Image.open(image_path)
            return pytesseract.image_to_string(img, lang="spa+eng")
        except Exception:
            return ""
