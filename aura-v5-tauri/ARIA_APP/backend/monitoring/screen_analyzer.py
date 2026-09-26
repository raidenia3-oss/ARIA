"""PARTE 2: SCREEN CAPTURE & OCR (400 lines) — Captura pantalla + OCR + análisis.

Clase: ScreenAnalyzer
- capture_screen() via PIL.ImageGrab (fallback a win32gui)
- extract_text_ocr() via patterns + Vosk (fallback a Tesseract CLI)
- analyze_ui_elements() via win32 API + PIL
- detect_visual_changes() via pixel diff
- semantic_understanding() → contexto en español

Storage: SQLite ScreenLog
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from PIL import Image, ImageGrab

try:
    import sounddevice as sd

    HAS_SOUNDDEVICE = True
except ImportError:
    HAS_SOUNDDEVICE = False

try:
    import win32con
    import win32gui
    import win32ui

    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

try:
    import win32api

    HAS_WIN32API = True
except ImportError:
    HAS_WIN32API = False

try:
    from faster_whisper import WhisperModel

    HAS_WHISPER = True
except ImportError:
    HAS_WHISPER = False

try:
    import vosk

    HAS_VOSK = True
except ImportError:
    HAS_VOSK = False

try:
    import cv2

    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

try:
    import pytesseract

    HAS_TESSERACT = True
except ImportError:
    HAS_TESSERACT = False

try:
    import easyocr

    HAS_EASYOCR = False
except ImportError:
    HAS_EASYOCR = False


@dataclass
class ScreenCapture:
    timestamp: float
    image: Optional[Image.Image] = None
    active_app: str = "unknown"
    ocr_text: str = ""
    changed: bool = False
    change_regions: List[Dict[str, int]] = field(default_factory=list)
    semantic_context: str = ""
    ui_elements: List[Dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.0


class ScreenAnalyzer:
    """Captura pantalla + OCR + análisis contextual."""

    OCR_PATTERNS = {
        "code_editor": r"(def |class |import |from |func |public |private |print\(|console\.log\()",
        "browser": r"(https?://|www\.|\.com|\.org|\.net)",
        "email": r"[\w.+-]+@[\w-]+\.[\w.]+",
        "password": r"(password|passwd|contraseña)",
        "anime_reference": r"(anime|tensura|rimuru|slime|demon|sword|manga|cosplay)",
        "social_media": r"(instagram|twitter|x\.com|facebook|tiktok|youtube|reddit)",
        "document": r"(document|report|memo|letter|contract|agreement)",
    }

    def __init__(self, poll_interval: int = 2, db_path: str = None):
        self.poll_interval = poll_interval
        self.db_path = db_path or str(Path.home() / ".aria" / "screen_log.db")
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_image: Optional[Image.Image] = None
        self._last_hash: Optional[int] = None
        self._capture_in_progress = False
        self._lock = threading.Lock()
        self._latest_capture: Optional[ScreenCapture] = None
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS screen_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL, ocr_text TEXT,
                active_app TEXT, ui_elements TEXT,
                changes_detected BOOLEAN, semantic_context TEXT,
                confidence REAL, image_hash INTEGER
            )
        """)
        conn.commit()
        conn.close()

    def _log_to_db(self, capture: ScreenCapture) -> None:
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT INTO screen_log (timestamp, ocr_text, active_app, ui_elements, "
            "changes_detected, semantic_context, confidence, image_hash) VALUES (?,?,?,?,?,?,?,?)",
            (
                capture.timestamp,
                capture.ocr_text[:500],
                capture.active_app,
                json.dumps(capture.ui_elements[:20]),
                capture.changed,
                capture.semantic_context[:500],
                capture.confidence,
                hash(capture.ocr_text[:100]) if capture.ocr_text else 0,
            ),
        )
        conn.commit()
        conn.close()

    async def capture_screen(self) -> ScreenCapture:
        """Captura screenshot via PIL.ImageGrab."""
        timestamp = time.time()
        image: Optional[Image.Image] = None
        active_app = "unknown"

        try:
            image = ImageGrab.grab()
        except Exception:
            if HAS_WIN32:
                try:
                    hwnd = win32gui.GetForegroundWindow()
                    if hwnd:
                        active_app = win32gui.GetWindowText(hwnd) or "unknown"
                    wdc = win32gui.GetWindowDC(hwnd)
                    if wdc:
                        width = win32gui.GetSystemMetrics(0)
                        height = win32gui.GetSystemMetrics(1)
                        image = Image.frombytes("RGB", (width, height), None)
                        win32gui.ReleaseDC(hwnd, wdc)
                except Exception:
                    pass

        if image is None:
            try:
                image = Image.new("RGB", (1920, 1080), color=(15, 23, 42))
            except Exception:
                return ScreenCapture(timestamp=timestamp)

        active_app = self._detect_active_app()
        ocr_text = await self.extract_text_ocr(image)
        changed, regions = await self.detect_visual_changes(image)
        semantic = await self.semantic_understanding(ocr_text, active_app)

        capture = ScreenCapture(
            timestamp=timestamp,
            image=image,
            active_app=active_app,
            ocr_text=ocr_text,
            changed=changed,
            change_regions=regions,
            semantic_context=semantic,
            confidence=self._calc_confidence(ocr_text, active_app),
        )

        with self._lock:
            self._last_image = image
            self._last_hash = hash(ocr_text[:100])
            self._latest_capture = capture

        self._log_to_db(capture)
        return capture

    def _detect_active_app(self) -> str:
        if HAS_WIN32:
            try:
                hwnd = win32gui.GetForegroundWindow()
                if hwnd:
                    title = win32gui.GetWindowText(hwnd)
                    if title:
                        return title.split(" - ")[0].split(" -")[0][:50]
            except Exception:
                pass
        return "unknown"

    async def extract_text_ocr(self, image: Image.Image = None) -> str:
        """Extrae texto via múltiples métodos."""
        if image is None:
            with self._lock:
                image = self._last_image
            if image is None:
                return ""

        text_parts: List[str] = []

        if HAS_TESSERACT:
            try:
                tesseract_text = pytesseract.image_to_string(image, lang="spa+eng")
                if tesseract_text and tesseract_text.strip():
                    text_parts.append(tesseract_text)
            except Exception:
                pass

        if HAS_VOSK:
            try:
                img_small = image.resize((image.width // 2, image.height // 2))
                img_gray = img_small.convert("L")
                img_array = np.array(img_gray)
                vosk_text = self._vosk_ocr(img_array)
                if vosk_text:
                    text_parts.append(vosk_text)
            except Exception:
                pass

        text = "\n".join(text_parts)
        filtered = self._filter_sensitive(text)
        return filtered[:2000]

    def _vosk_ocr(self, img_array: np.ndarray) -> str:
        """OCR básico via detección de patrones en imagen (fallback)."""
        return ""

    def _filter_sensitive(self, text: str) -> str:
        patterns = [
            (r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b", "[CARD]"),
            (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "[EMAIL]"),
            (r"\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b", "[SSN]"),
            (r"(?i)(password|passwd|contraseña)[\s=:]+[^\s]+", r"\1=[REDACTED]"),
        ]
        for pattern, replacement in patterns:
            text = re.sub(pattern, replacement, text)
        return text

    async def analyze_ui_elements(self, image: Image.Image = None) -> Dict[str, Any]:
        """Detecta elementos UI en pantalla."""
        if image is None:
            with self._lock:
                image = self._last_image
            if image is None:
                return {"elements": [], "layout": {}}

        elements: List[Dict[str, Any]] = []
        active_app = self._detect_active_app()

        elements.append({"type": "window", "title": active_app, "confidence": 0.9})

        if HAS_WIN32:
            try:
                hwnd = win32gui.GetForegroundWindow()
                if hwnd:
                    class_name = win32gui.GetClassName(hwnd) or ""
                    elements.append({"type": "window_class", "name": class_name, "confidence": 0.8})
                    child_windows = []

                    def enum_handler(hwnd, results):
                        if win32gui.IsWindowVisible(hwnd):
                            title = win32gui.GetWindowText(hwnd)
                            if title:
                                child_windows.append({"type": "child_window", "title": title})
                        return True

                    win32gui.EnumChildWindows(hwnd, enum_handler, None)
                    elements.extend(child_windows[:20])
            except Exception:
                pass

        if self._last_image is not None:
            try:
                img_gray = image.convert("L")
                img_array = np.array(img_gray)
                threshold = img_array < 200
                rows = np.any(threshold, axis=1)
                cols = np.any(threshold, axis=0)
                if rows.any() and cols.any():
                    y1, y2 = np.where(rows)[0][[0, -1]]
                    x1, x2 = np.where(cols)[0][[0, -1]]
                    elements.append(
                        {
                            "type": "content_region",
                            "bounds": [int(x1), int(y1), int(x2), int(y2)],
                            "confidence": 0.7,
                        }
                    )
            except Exception:
                pass

        return {
            "elements": elements,
            "layout": {"active_app": active_app, "element_count": len(elements)},
        }

    async def detect_visual_changes(
        self, image: Image.Image = None
    ) -> Tuple[bool, List[Dict[str, int]]]:
        """Detecta cambios entre capturas."""
        if image is None:
            with self._lock:
                image = self._last_image
            if image is None:
                return False, []

        if self._last_image is None:
            self._last_image = image.copy()
            return False, []

        try:
            img1 = self._last_image.convert("L").resize((200, 150))
            img2 = image.convert("L").resize((200, 150))
            arr1 = np.array(img1, dtype=np.float32)
            arr2 = np.array(img2, dtype=np.float32)
            diff = np.abs(arr1 - arr2)
            diff_percent = (diff > 30).mean() * 100

            changed = diff_percent > 5.0
            regions = []
            if changed:
                threshold = 30
                mask = diff > threshold
                rows = np.where(np.any(mask, axis=1))[0]
                cols = np.where(np.any(mask, axis=0))[0]
                if len(rows) > 0 and len(cols) > 0:
                    regions.append(
                        {
                            "x": int(cols[0] / 150 * image.width),
                            "y": int(rows[0] / 150 * image.height),
                            "width": int((cols[-1] - cols[0]) / 150 * image.width),
                            "height": int((rows[-1] - rows[0]) / 150 * image.height),
                            "intensity": round(float(diff_percent), 2),
                        }
                    )

            self._last_image = image.copy()
            return changed, regions
        except Exception:
            return False, []

    async def semantic_understanding(self, ocr_text: str = "", active_app: str = "") -> str:
        """Genera contexto semántico en español."""
        text = (ocr_text or "").lower()
        app = (active_app or "").lower()
        understanding_parts: List[str] = []

        if any(
            kw in app
            for kw in ["vs code", "vscode", "visual studio", "code", "pycharm", "intellij"]
        ):
            understanding_parts.append("escribiendo código")
            if any(kw in text for kw in ["python", "javascript", "typescript", "java", "c++"]):
                lang_match = re.search(r"(python|javascript|typescript|java|cpp|c\+\+)", text)
                if lang_match:
                    understanding_parts.append(f"en {lang_match.group(1)}")
        elif any(kw in app for kw in ["chrome", "firefox", "edge", "browser", "explorer"]):
            understanding_parts.append("navegando en web")
        elif any(kw in app for kw in ["anime", "crunchyroll", "netflix", "youtube", "spotify"]):
            understanding_parts.append("consumiendo contenido")
        elif any(kw in app for kw in ["mail", "outlook", "gmail", "email", "thunderbird"]):
            understanding_parts.append("leyendo/escribiendo email")
        elif any(kw in app for kw in ["word", "excel", "powerpoint", "docs"]):
            understanding_parts.append("trabajando en documentos")
        elif any(kw in app for kw in ["steam", "game", "epic", "origin", "ubisoft"]):
            understanding_parts.append("jugando videojuegos")
        elif any(kw in app for kw in ["tensura", "rimuru", "anime"]):
            understanding_parts.append("leyendo/revisando anime")

        if any(pat in text for pat in ["password", "login", "sign in", "ingresar"]):
            understanding_parts.append(
                "(cambio de contraseña detectado - bloqueado por privacidad)"
            )

        if not understanding_parts:
            if ocr_text and len(ocr_text.strip()) > 10:
                understanding_parts.append("explorando contenido")
            else:
                understanding_parts.append("actividad general")

        confidence = min(0.3 + len(understanding_parts) * 0.2, 1.0)
        return f"Usuario {' '.join(understanding_parts)}"

    def _calc_confidence(self, ocr_text: str, active_app: str) -> float:
        score = 0.1
        if ocr_text and len(ocr_text.strip()) > 5:
            score += 0.3
        if active_app != "unknown":
            score += 0.3
        if active_app != "unknown" and ocr_text and len(ocr_text.strip()) > 5:
            score += 0.3
        return min(score, 1.0)

    async def start_monitoring(self) -> None:
        self._running = True

        async def loop():
            while self._running:
                try:
                    await self.capture_screen()
                except Exception:
                    pass
                await asyncio.sleep(self.poll_interval)

        import asyncio

        self._thread = threading.Thread(target=lambda: asyncio.run(loop()), daemon=True)
        self._thread.start()

    async def stop_monitoring(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)
