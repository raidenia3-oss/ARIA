"""
AURA Local Screen-Awareness & Desktop Vision Bridge (OSWorld Style)

Subsistema de captura y procesamiento visual local del escritorio.
Permite a AURA capturar, comprimir y analizar el contenido de la pantalla
mediante modelos multimodales locales (Jan/Ollama) sin depender de la nube.

Características:
- Captura de pantalla eficiente con PIL/mss
- Compresión adaptativa para control de VRAM
- Análisis con modelos VLM locales (moondream, llava, etc.)
- Inyección de contexto visual al orquestador
- Endpoints REST para análisis bajo demanda
"""

from __future__ import annotations

import base64
import io
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable
from enum import Enum
from pathlib import Path

import numpy as np

try:
    from PIL import Image, ImageGrab
except Exception:
    Image = None
    ImageGrab = None

try:
    import mss
except Exception:
    mss = None

try:
    import cv2
except Exception:
    cv2 = None

logger = logging.getLogger("AURAScreenBridge")

# Configuración por defecto
DEFAULT_CAPTURE_INTERVAL = 5.0  # segundos
DEFAULT_MAX_DIMENSION = 1280
DEFAULT_JPEG_QUALITY = 75
DEFAULT_COMPRESSION_LEVEL = 6

# Variables de entorno
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_VISION_MODEL = os.getenv("OLLAMA_VISION_MODEL", "moondream")
JAN_BASE_URL = os.getenv("JAN_BASE_URL", "http://localhost:1337/v1")
JAN_VISION_MODEL = os.getenv("JAN_VISION_MODEL", "llava-v1.5-7b")


class CaptureBackend(str, Enum):
    """Backends disponibles para captura de pantalla."""
    PIL = "pil"
    MSS = "mss"
    AUTO = "auto"


class AnalysisMode(str, Enum):
    """Modos de análisis visual."""
    FULL = "full"           # Análisis completo con VLM
    FAST = "fast"           # Solo metadatos básicos (OpenCV/PIL)
    OCR = "ocr"             # Enfoque en texto (para código, errores)
    UI = "ui"               # Enfoque en elementos de interfaz


@dataclass
class ScreenCaptureConfig:
    """Configuración para captura de pantalla."""
    backend: CaptureBackend = CaptureBackend.AUTO
    interval_seconds: float = DEFAULT_CAPTURE_INTERVAL
    max_dimension: int = DEFAULT_MAX_DIMENSION
    jpeg_quality: int = DEFAULT_JPEG_QUALITY
    compression_level: int = DEFAULT_COMPRESSION_LEVEL
    monitor_index: int = 0  # 0 = todos, 1+ = monitor específico
    region: Optional[tuple] = None  # (left, top, width, height)
    enabled: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "backend": self.backend.value,
            "interval_seconds": self.interval_seconds,
            "max_dimension": self.max_dimension,
            "jpeg_quality": self.jpeg_quality,
            "compression_level": self.compression_level,
            "monitor_index": self.monitor_index,
            "region": self.region,
            "enabled": self.enabled,
        }


@dataclass
class FrameData:
    """Datos de un frame capturado."""
    timestamp: float
    image_base64: str
    width: int
    height: int
    format: str = "JPEG"
    monitor_index: int = 0
    region: Optional[tuple] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "image_base64": self.image_base64,
            "width": self.width,
            "height": self.height,
            "format": self.format,
            "monitor_index": self.monitor_index,
            "region": self.region,
            "metadata": self.metadata,
        }

    @property
    def size_bytes(self) -> int:
        return len(self.image_base64) * 3 // 4  # aprox base64 -> bytes


@dataclass
class VisionAnalysisResult:
    """Resultado del análisis visual."""
    timestamp: float
    session_id: str
    mode: AnalysisMode
    model_used: str
    description: str
    structured_data: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    processing_time_ms: float = 0.0
    frame_info: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "session_id": self.session_id,
            "mode": self.mode.value,
            "model_used": self.model_used,
            "description": self.description,
            "structured_data": self.structured_data,
            "confidence": self.confidence,
            "processing_time_ms": self.processing_time_ms,
            "frame_info": self.frame_info,
        }

    def to_context_text(self) -> str:
        """Traduce el análisis visual a metadatos textuales inteligibles.

        Produce un resumen textual compacto que el prompt del sistema y el
        agente de automatización web pueden consumir directamente, sin
        necesidad de enviar la imagen completa al núcleo de razonamiento.
        Mantiene la carga de VRAM mínima al operar sobre metadatos.
        """
        parts: List[str] = []
        if self.description:
            parts.append(f"descripción: {self.description}")
        parts.append(f"modelo: {self.model_used}")
        parts.append(f"modo: {self.mode.value}")
        parts.append(f"confianza: {self.confidence:.2f}")
        if self.frame_info:
            fi = self.frame_info
            parts.append(f"frame: {fi.get('width', '?')}x{fi.get('height', '?')}")
        if self.processing_time_ms:
            parts.append(f"tiempo_ms: {self.processing_time_ms:.0f}")
        return " | ".join(parts)


class ScreenCapture:
    """Motor de captura de pantalla multiplataforma."""

    def __init__(self, config: Optional[ScreenCaptureConfig] = None):
        self.config = config or ScreenCaptureConfig()
        self._backend = self._select_backend()
        self._mss_instance = None
        self._last_capture_time = 0.0
        self._lock = threading.Lock()

        if self.config.enabled:
            self._initialize_backend()

    def _select_backend(self) -> CaptureBackend:
        if self.config.backend != CaptureBackend.AUTO:
            return self.config.backend
        if mss is not None:
            return CaptureBackend.MSS
        return CaptureBackend.PIL

    def _initialize_backend(self) -> None:
        if self._backend == CaptureBackend.MSS and mss is not None:
            self._mss_instance = mss.mss()
            logger.info("Screen capture backend: mss (multi-monitor)")
        elif self._backend == CaptureBackend.PIL and ImageGrab is not None:
            logger.info("Screen capture backend: PIL.ImageGrab")
        else:
            logger.warning("No screen capture backend available")
            self.config.enabled = False

    def capture(self, region: Optional[tuple] = None) -> Optional[FrameData]:
        """Captura un frame de la pantalla."""
        if not self.config.enabled:
            logger.debug("Screen capture disabled")
            return None

        with self._lock:
            try:
                if self._backend == CaptureBackend.MSS:
                    return self._capture_mss(region)
                else:
                    return self._capture_pil(region)
            except Exception as exc:
                logger.error(f"Screen capture failed: {exc}")
                return None

    def _capture_mss(self, region: Optional[tuple]) -> Optional[FrameData]:
        if self._mss_instance is None:
            return None

        monitor = self.config.monitor_index
        if region:
            left, top, width, height = region
            monitor_dict = {"left": left, "top": top, "width": width, "height": height}
        else:
            monitors = self._mss_instance.monitors
            if monitor == 0:
                monitor_dict = monitors[0]  # todos los monitores
            elif monitor < len(monitors):
                monitor_dict = monitors[monitor]
            else:
                monitor_dict = monitors[0]

        screenshot = self._mss_instance.grab(monitor_dict)
        img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")

        return self._process_image(img, monitor_dict.get("left", 0), monitor_dict.get("top", 0))

    def _capture_pil(self, region: Optional[tuple]) -> Optional[FrameData]:
        if ImageGrab is None:
            return None

        if region:
            left, top, width, height = region
            bbox = (left, top, left + width, top + height)
            img = ImageGrab.grab(bbox=bbox)
            return self._process_image(img, left, top)
        else:
            img = ImageGrab.grab(all_screens=True)
            return self._process_image(img, 0, 0)

    def _process_image(self, img: Image.Image, left: int, top: int) -> FrameData:
        """Procesa y comprime la imagen capturada."""
        original_width, original_height = img.size

        # Redimensionar si excede max_dimension
        max_dim = self.config.max_dimension
        if max(original_width, original_height) > max_dim:
            if original_width > original_height:
                new_width = max_dim
                new_height = int(original_height * max_dim / original_width)
            else:
                new_height = max_dim
                new_width = int(original_width * max_dim / original_height)
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

        # Convertir a RGB si es necesario
        if img.mode != "RGB":
            img = img.convert("RGB")

        # Comprimir a JPEG
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=self.config.jpeg_quality, optimize=True)
        img_bytes = buf.getvalue()

        # Codificar a base64
        image_b64 = base64.b64encode(img_bytes).decode("utf-8")

        frame = FrameData(
            timestamp=time.time(),
            image_base64=image_b64,
            width=img.width,
            height=img.height,
            monitor_index=self.config.monitor_index,
            region=(left, top, img.width, img.height),
            metadata={
                "original_width": original_width,
                "original_height": original_height,
                "compressed_size_bytes": len(img_bytes),
                "compression_ratio": len(img_bytes) / (original_width * original_height * 3) if original_width * original_height > 0 else 0,
            }
        )

        self._last_capture_time = frame.timestamp
        return frame

    def capture_to_file(self, path: str, region: Optional[tuple] = None) -> bool:
        """Captura y guarda directamente a archivo."""
        frame = self.capture(region)
        if frame is None:
            return False
        try:
            img_data = base64.b64decode(frame.image_base64)
            with open(path, "wb") as f:
                f.write(img_data)
            return True
        except Exception as exc:
            logger.error(f"Failed to save capture: {exc}")
            return False

    def get_monitor_info(self) -> List[Dict[str, Any]]:
        """Obtiene información de monitores disponibles."""
        monitors = []
        if self._backend == CaptureBackend.MSS and self._mss_instance:
            for i, mon in enumerate(self._mss_instance.monitors):
                monitors.append({
                    "index": i,
                    "left": mon["left"],
                    "top": mon["top"],
                    "width": mon["width"],
                    "height": mon["height"],
                })
        elif ImageGrab is not None:
            # PIL solo detecta pantalla principal combinada
            try:
                img = ImageGrab.grab(all_screens=True)
            except Exception as exc:
                logger.debug(f"Monitor probing unavailable (headless?): {exc}")
                return []
            monitors.append({
                "index": 0,
                "left": 0,
                "top": 0,
                "width": img.width,
                "height": img.height,
            })
        return monitors

    def is_available(self) -> bool:
        return self.config.enabled and (self._backend == CaptureBackend.MSS or ImageGrab is not None)


class VisionAnalyzer:
    """Analizador visual con soporte para múltiples backends VLM."""

    def __init__(self, orchestrator: Any = None):
        self.orchestrator = orchestrator
        self._last_result: Optional[VisionAnalysisResult] = None

    def analyze(
        self,
        frame: FrameData,
        mode: AnalysisMode = AnalysisMode.FULL,
        session_id: str = "",
        custom_prompt: Optional[str] = None,
    ) -> VisionAnalysisResult:
        """Analiza un frame según el modo especificado."""
        start_time = time.time()

        try:
            if mode == AnalysisMode.FAST:
                return self._fast_analysis(frame, session_id, start_time)
            elif mode == AnalysisMode.OCR:
                return self._ocr_analysis(frame, session_id, start_time)
            elif mode == AnalysisMode.UI:
                return self._ui_analysis(frame, session_id, start_time)
            else:
                return self._full_analysis(frame, session_id, start_time, custom_prompt)
        except Exception as exc:
            logger.error(f"Vision analysis failed: {exc}")
            return VisionAnalysisResult(
                timestamp=time.time(),
                session_id=session_id,
                mode=mode,
                model_used="error",
                description=f"Analysis failed: {exc}",
                processing_time_ms=(time.time() - start_time) * 1000,
            )

    def _full_analysis(
        self,
        frame: FrameData,
        session_id: str,
        start_time: float,
        custom_prompt: Optional[str] = None,
    ) -> VisionAnalysisResult:
        """Análisis completo con modelo VLM (Ollama/Jan)."""
        prompt = custom_prompt or self._get_default_prompt()

        # Intentar Ollama primero
        result = self._analyze_ollama(frame.image_base64, prompt)
        if result:
            return VisionAnalysisResult(
                timestamp=time.time(),
                session_id=session_id,
                mode=AnalysisMode.FULL,
                model_used=f"ollama:{OLLAMA_VISION_MODEL}",
                description=result,
                confidence=0.85,
                processing_time_ms=(time.time() - start_time) * 1000,
                frame_info={"width": frame.width, "height": frame.height},
            )

        # Fallback a Jan
        result = self._analyze_jan(frame.image_base64, prompt)
        if result:
            return VisionAnalysisResult(
                timestamp=time.time(),
                session_id=session_id,
                mode=AnalysisMode.FULL,
                model_used=f"jan:{JAN_VISION_MODEL}",
                description=result,
                confidence=0.8,
                processing_time_ms=(time.time() - start_time) * 1000,
                frame_info={"width": frame.width, "height": frame.height},
            )

        # Fallback final
        return self._fast_analysis(frame, session_id, start_time)

    def _analyze_ollama(self, image_b64: str, prompt: str) -> Optional[str]:
        try:
            import requests as req
            payload = {
                "model": OLLAMA_VISION_MODEL,
                "prompt": prompt,
                "images": [image_b64],
                "stream": False,
            }
            resp = req.post(f"{OLLAMA_HOST}/api/generate", json=payload, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                return str(data.get("response", "")).strip()
        except Exception as exc:
            logger.debug(f"Ollama vision failed: {exc}")
        return None

    def _analyze_jan(self, image_b64: str, prompt: str) -> Optional[str]:
        try:
            import requests as req
            # Jan usa formato OpenAI-compatible
            payload = {
                "model": JAN_VISION_MODEL,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
                        ],
                    }
                ],
                "max_tokens": 500,
                "temperature": 0.3,
            }
            headers = {"Content-Type": "application/json"}
            resp = req.post(f"{JAN_BASE_URL}/chat/completions", json=payload, headers=headers, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                choices = data.get("choices", [])
                if choices:
                    return str(choices[0].get("message", {}).get("content", "")).strip()
        except Exception as exc:
            logger.debug(f"Jan vision failed: {exc}")
        return None

    def _get_default_prompt(self) -> str:
        return (
            "Describe brevemente lo que se muestra en esta captura de pantalla. "
            "Enfócate en: aplicaciones visibles, código o texto legible, errores, "
            "elementos de interfaz relevantes y estado general del escritorio. "
            "Responde en español, máximo 3 oraciones."
        )

    def _fast_analysis(
        self,
        frame: FrameData,
        session_id: str,
        start_time: float,
    ) -> VisionAnalysisResult:
        """Análisis rápido sin VLM (solo metadatos)."""
        try:
            img_data = base64.b64decode(frame.image_base64)
            if Image is not None:
                img = Image.open(io.BytesIO(img_data))
                arr = np.array(img.convert("L"))
            elif cv2 is not None:
                arr = cv2.imdecode(np.frombuffer(img_data, np.uint8), cv2.IMREAD_GRAYSCALE)
            else:
                raise RuntimeError("No image processing backend")

            brightness = float(np.mean(arr))
            contrast = float(np.std(arr))

            if cv2 is not None and len(arr.shape) == 2:
                blur = cv2.Laplacian(arr, cv2.CV_64F).var()
            else:
                blur = 0.0

            description = (
                f"Frame {frame.width}x{frame.height}, "
                f"brillo={brightness:.1f}, contraste={contrast:.1f}, nitidez={blur:.1f}"
            )

            return VisionAnalysisResult(
                timestamp=time.time(),
                session_id=session_id,
                mode=AnalysisMode.FAST,
                model_used="fallback:opencv/pil",
                description=description,
                confidence=0.3,
                processing_time_ms=(time.time() - start_time) * 1000,
                frame_info={"width": frame.width, "height": frame.height},
            )
        except Exception as exc:
            logger.error(f"Fast analysis failed: {exc}")
            return VisionAnalysisResult(
                timestamp=time.time(),
                session_id=session_id,
                mode=AnalysisMode.FAST,
                model_used="error",
                description="Fast analysis unavailable",
                processing_time_ms=(time.time() - start_time) * 1000,
            )

    def _ocr_analysis(
        self,
        frame: FrameData,
        session_id: str,
        start_time: float,
    ) -> VisionAnalysisResult:
        """Análisis enfocado en texto (OCR básico + VLM)."""
        prompt = (
            "Extrae y transcribe todo el texto visible en esta captura. "
            "Incluye código, errores, logs, menús, botones y cualquier texto legible. "
            "Si hay código, indica el lenguaje. Responde en español."
        )

        result = self._analyze_ollama(frame.image_base64, prompt)
        if not result:
            result = self._analyze_jan(frame.image_base64, prompt)

        if not result:
            return self._fast_analysis(frame, session_id, start_time)

        return VisionAnalysisResult(
            timestamp=time.time(),
            session_id=session_id,
            mode=AnalysisMode.OCR,
            model_used=f"ollama:{OLLAMA_VISION_MODEL}" if "ollama" in str(result).lower() else f"jan:{JAN_VISION_MODEL}",
            description=result,
            structured_data={"text_focus": True},
            confidence=0.75,
            processing_time_ms=(time.time() - start_time) * 1000,
            frame_info={"width": frame.width, "height": frame.height},
        )

    def _ui_analysis(
        self,
        frame: FrameData,
        session_id: str,
        start_time: float,
    ) -> VisionAnalysisResult:
        """Análisis enfocado en elementos de UI."""
        prompt = (
            "Identifica elementos de interfaz de usuario: botones, campos de texto, "
            "menús, ventanas, diálogos, iconos. Describe el estado de la aplicación "
            "visible (cargando, error, listo, etc.). Responde en español."
        )

        result = self._analyze_ollama(frame.image_base64, prompt)
        if not result:
            result = self._analyze_jan(frame.image_base64, prompt)

        if not result:
            return self._fast_analysis(frame, session_id, start_time)

        return VisionAnalysisResult(
            timestamp=time.time(),
            session_id=session_id,
            mode=AnalysisMode.UI,
            model_used=f"ollama:{OLLAMA_VISION_MODEL}" if "ollama" in str(result).lower() else f"jan:{JAN_VISION_MODEL}",
            description=result,
            structured_data={"ui_focus": True},
            confidence=0.75,
            processing_time_ms=(time.time() - start_time) * 1000,
            frame_info={"width": frame.width, "height": frame.height},
        )

    def get_last_result(self) -> Optional[VisionAnalysisResult]:
        return self._last_result


class ScreenBridge:
    """
    Puente principal de consciencia de pantalla.

    Coordina captura, análisis e inyección de contexto visual.
    """

    def __init__(
        self,
        config: Optional[ScreenCaptureConfig] = None,
        orchestrator: Any = None,
    ):
        self.capture = ScreenCapture(config)
        self.analyzer = VisionAnalyzer(orchestrator)
        self.config = config or ScreenCaptureConfig()
        self.orchestrator = orchestrator

        # Estado de monitoreo continuo
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._monitor_callback: Optional[Callable[[VisionAnalysisResult], None]] = None
        self._last_analysis: Optional[VisionAnalysisResult] = None

    def analyze_screen(
        self,
        mode: AnalysisMode = AnalysisMode.FULL,
        session_id: str = "",
        region: Optional[tuple] = None,
        custom_prompt: Optional[str] = None,
    ) -> VisionAnalysisResult:
        """Captura y analiza la pantalla actual."""
        frame = self.capture.capture(region)
        if frame is None:
            return VisionAnalysisResult(
                timestamp=time.time(),
                session_id=session_id,
                mode=mode,
                model_used="none",
                description="Screen capture failed or disabled",
            )

        result = self.analyzer.analyze(frame, mode, session_id, custom_prompt)
        self._last_analysis = result
        self._inject_context(result)
        return result

    def analyze_frame(self, frame: FrameData, mode: AnalysisMode = AnalysisMode.FULL, session_id: str = "") -> VisionAnalysisResult:
        """Analiza un frame ya capturado."""
        result = self.analyzer.analyze(frame, mode, session_id)
        self._last_analysis = result
        self._inject_context(result)
        return result

    def _inject_context(self, result: VisionAnalysisResult) -> None:
        """Inyecta el contexto visual en el orquestador / núcleo de razonamiento.

        Traduce el análisis multimodal a metadatos textuales inteligibles
        (context_text) que el prompt del sistema y el agente de
        automatización web pueden consumir, manteniendo la carga de VRAM
        mínima: no se envía la imagen completa, solo el resumen textual.
        """
        if self.orchestrator is None:
            return
        context = {
            "description": result.description,
            "context_text": result.to_context_text(),
            "mode": result.mode.value,
            "model_used": result.model_used,
            "confidence": result.confidence,
            "timestamp": result.timestamp,
            "session_id": result.session_id,
            "frame_info": result.frame_info,
            "structured_data": result.structured_data,
        }
        if hasattr(self.orchestrator, "set_vision_context"):
            try:
                self.orchestrator.set_vision_context(context)
            except Exception as exc:
                logger.debug(f"Orchestrator injection failed: {exc}")
        else:
            logger.debug("Orchestrator has no set_vision_context hook; context not injected")

    def start_monitoring(
        self,
        mode: AnalysisMode = AnalysisMode.FAST,
        session_id: str = "",
        callback: Optional[Callable[[VisionAnalysisResult], None]] = None,
    ) -> bool:
        """Inicia monitoreo continuo de la pantalla."""
        if self._monitoring:
            return False

        if not self.capture.is_available():
            logger.warning("Screen capture not available for monitoring")
            return False

        self._monitoring = True
        self._monitor_callback = callback
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            args=(mode, session_id),
            daemon=True,
        )
        self._monitor_thread.start()
        logger.info(f"Screen monitoring started (mode={mode.value}, interval={self.config.interval_seconds}s)")
        return True

    def stop_monitoring(self) -> None:
        """Detiene el monitoreo continuo."""
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=2.0)
            self._monitor_thread = None
        logger.info("Screen monitoring stopped")

    def _monitor_loop(self, mode: AnalysisMode, session_id: str) -> None:
        while self._monitoring:
            try:
                result = self.analyze_screen(mode=mode, session_id=session_id)
                if self._monitor_callback:
                    try:
                        self._monitor_callback(result)
                    except Exception:
                        pass
            except Exception as exc:
                logger.error(f"Monitor loop error: {exc}")

            time.sleep(self.config.interval_seconds)

    def get_status(self) -> Dict[str, Any]:
        """Estado actual del bridge."""
        return {
            "capture": {
                "enabled": self.capture.config.enabled,
                "backend": self.capture._backend.value,
                "available": self.capture.is_available(),
                "config": self.capture.config.to_dict(),
                "monitors": self.capture.get_monitor_info(),
            },
            "analyzer": {
                "ollama_host": OLLAMA_HOST,
                "ollama_model": OLLAMA_VISION_MODEL,
                "jan_url": JAN_BASE_URL,
                "jan_model": JAN_VISION_MODEL,
            },
            "monitoring": self._monitoring,
            "last_analysis": self._last_analysis.to_dict() if self._last_analysis else None,
        }


# Instancia global por defecto
_screen_bridge: Optional[ScreenBridge] = None


def get_screen_bridge(
    config: Optional[ScreenCaptureConfig] = None,
    orchestrator: Any = None,
) -> ScreenBridge:
    """Obtiene o crea la instancia global del ScreenBridge."""
    global _screen_bridge
    if _screen_bridge is None:
        _screen_bridge = ScreenBridge(config=config, orchestrator=orchestrator)
    return _screen_bridge


async def analyze_screen_async(
    mode: AnalysisMode = AnalysisMode.FULL,
    session_id: str = "",
    region: Optional[tuple] = None,
    custom_prompt: Optional[str] = None,
) -> VisionAnalysisResult:
    """Función de conveniencia asíncrona para análisis de pantalla."""
    bridge = get_screen_bridge()
    # Ejecutar en thread pool para no bloquear
    import asyncio
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        lambda: bridge.analyze_screen(mode, session_id, region, custom_prompt),
    )