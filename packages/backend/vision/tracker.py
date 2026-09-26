"""BLOQUE 65 - AURA Local Advanced Computer Vision & Dynamic UI Template Tracking Engine."""

from __future__ import annotations

import logging
import math
import os
import random
import secrets
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

try:
    from PIL import Image, ImageGrab
except Exception:
    Image = None
    ImageGrab = None

try:
    import cv2
except Exception:
    cv2 = None

logger = logging.getLogger("AURA.Vision.Tracker")

DEFAULT_MATCH_THRESHOLD = 0.85
DEFAULT_MIN_CONFIDENCE = 0.60
DEFAULT_MAX_SCAN_REGIONS = 4
DEFAULT_FRAME_DOWNSCALE = 2


class MatchMode(str, Enum):
    EXACT = "exact"
    PARTIAL = "partial"
    BEST_EFFORT = "best_effort"


@dataclass
class UIRegion:
    left: int
    top: int
    width: int
    height: int

    def to_dict(self):
        return {"left": self.left, "top": self.top, "width": self.width, "height": self.height}

    def as_tuple(self):
        return (self.left, self.top, self.width, self.height)


@dataclass
class UITemplate:
    name: str
    points: List[Tuple[float, float]]
    category: str = "button"
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    def to_dict(self):
        return {"name": self.name, "points": [list(p) for p in self.points],
                "category": self.category, "metadata": self.metadata,
                "created_at": self.created_at}


@dataclass
class UIMatchResult:
    matched: bool
    template_name: str
    confidence: float
    location: Optional[Tuple[float, float]] = None
    region: Optional[UIRegion] = None
    processing_time_ms: float = 0.0
    mode: MatchMode = MatchMode.PARTIAL
    distance: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        return {"matched": self.matched, "template_name": self.template_name,
                "confidence": self.confidence,
                "location": list(self.location) if self.location else None,
                "region": self.region.to_dict() if self.region else None,
                "processing_time_ms": self.processing_time_ms,
                "mode": self.mode.value, "distance": self.distance,
                "metadata": self.metadata}


@dataclass
class DetectionResult:
    timestamp: float
    screen_width: int
    screen_height: int
    matches: List[UIMatchResult]
    processing_time_ms: float
    templates_checked: int = 0
    error: Optional[str] = None

    def to_dict(self):
        return {"timestamp": self.timestamp, "screen_width": self.screen_width,
                "screen_height": self.screen_height,
                "matches": [m.to_dict() for m in self.matches],
                "processing_time_ms": self.processing_time_ms,
                "templates_checked": self.templates_checked,
                "error": self.error}


class TemplateMatcher:
    """Coincidencia de plantillas de UI con umbrales adaptativos y busqueda espacial.

    Usa distancias euclideas normalizadas entre conjuntos de puntos para
    calcular un puntaje de confianza sin dependencias externas.
    """

    def __init__(self, threshold: float = DEFAULT_MATCH_THRESHOLD,
                 min_confidence: float = DEFAULT_MIN_CONFIDENCE,
                 max_scan_regions: int = DEFAULT_MAX_SCAN_REGIONS) -> None:
        self.threshold = threshold
        self.min_confidence = min_confidence
        self.max_scan_regions = max_scan_regions

    def match(self, template_points, screen_points,
              mode: MatchMode = MatchMode.PARTIAL) -> UIMatchResult:
        start = time.time()
        if not template_points or not screen_points:
            return UIMatchResult(matched=False, template_name="",
                                  confidence=0.0, processing_time_ms=0.0,
                                  mode=mode, distance=float("inf"))

        distance = self._sample_distance(template_points, screen_points)
        norm = self._normalize_distance(template_points, screen_points)
        confidence = max(0.0, 1.0 - norm)

        if mode == MatchMode.EXACT:
            matched = confidence >= self.threshold
        elif mode == MatchMode.BEST_EFFORT:
            matched = confidence >= self.min_confidence
        else:
            matched = confidence >= self.threshold

        loc = self._estimate_location(screen_points)
        return UIMatchResult(matched=matched, template_name="",
                              confidence=round(confidence, 4),
                              location=loc, processing_time_ms=(time.time() - start) * 1000,
                              mode=mode, distance=round(distance, 4))

    def _sample_distance(self, a, b) -> float:
        total = 0.0
        n = max(len(a), len(b))
        if n == 0:
            return 0.0
        for i in range(n):
            pa = a[i] if i < len(a) else a[-1]
            pb = b[i] if i < len(b) else b[-1]
            total += math.hypot(pa[0] - pb[0], pa[1] - pb[1])
        return total / n

    def _normalize_distance(self, a, b) -> float:
        span = max(self._bounding_box_diag(a), self._bounding_box_diag(b), 1.0)
        return min(1.0, self._sample_distance(a, b) / span)

    @staticmethod
    def _bounding_box_diag(points) -> float:
        if not points:
            return 0.0
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        w = max(xs) - min(xs)
        h = max(ys) - min(ys)
        return math.hypot(w, h)

    @staticmethod
    def _estimate_location(points):
        if not points:
            return (0.0, 0.0)
        n = len(points)
        return (sum(p[0] for p in points) / n, sum(p[1] for p in points) / n)


class CoordinateMapper:
    """Traduce coordenadas relativas de deteccion a coordenadas absolutas de pantalla."""

    def __init__(self, screen_width=1920, screen_height=1080,
                 scale=1.0, offset_x=0, offset_y=0):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.scale = scale
        self.offset_x = offset_x
        self.offset_y = offset_y

    def map(self, x, y, region=None, scale=None):
        sx = scale if scale is not None else self.scale
        ox = region.left if region else self.offset_x
        oy = region.top if region else self.offset_y
        return (x * sx + ox, y * sx + oy)

    def map_region(self, region):
        x, y = self.map(region.left, region.top)
        return UIRegion(left=int(x), top=int(y),
                        width=int(region.width * self.scale),
                        height=int(region.height * self.scale))


class TemplateRegistry:
    """Registro de plantillas de UI con busqueda por nombre."""

    def __init__(self):
        self._templates = {}
        self._lock = threading.Lock()

    def register(self, template):
        with self._lock:
            self._templates[template.name] = template

    def get(self, name):
        return self._templates.get(name)

    def list_templates(self):
        return list(self._templates.values())

    def remove(self, name):
        with self._lock:
            if name in self._templates:
                del self._templates[name]
                return True
            return False

    def clear(self):
        with self._lock:
            self._templates.clear()

    def __len__(self):
        return len(self._templates)


class UITemplateTracker:
    """Motor principal de vision avanzada: captura, coincidencia de plantillas
    y mapeo de coordenadas para el motor de automatizacion organica (Bloque 62)."""

    def __init__(self, threshold: float = DEFAULT_MATCH_THRESHOLD,
                 min_confidence: float = DEFAULT_MIN_CONFIDENCE,
                 screen_width: int = 1920, screen_height: int = 1080,
                 scale: float = 1.0) -> None:
        self.matcher = TemplateMatcher(threshold=threshold,
                                        min_confidence=min_confidence)
        self.registry = TemplateRegistry()
        self.mapper = CoordinateMapper(screen_width=screen_width,
                                        screen_height=screen_height,
                                        scale=scale)
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.scale = scale
        self._lock = threading.Lock()
        self._last_detection: Optional[DetectionResult] = None

    def register_template(self, name: str, points, category: str = "button",
                          metadata: Optional[Dict[str, Any]] = None) -> UITemplate:
        tpl = UITemplate(name=name, points=list(points), category=category,
                          metadata=metadata or {})
        self.registry.register(tpl)
        return tpl

    def remove_template(self, name: str) -> bool:
        return self.registry.remove(name)

    def list_templates(self) -> List[UITemplate]:
        return self.registry.list_templates()

    def detect(self, screen_points: List[Tuple[float, float]],
               mode: MatchMode = MatchMode.PARTIAL,
               template_names: Optional[List[str]] = None) -> DetectionResult:
        start = time.time()
        templates = self.registry.list_templates()
        if template_names:
            templates = [t for t in templates if t.name in template_names]
        matches: List[UIMatchResult] = []
        for tpl in templates:
            res = self.matcher.match(tpl.points, screen_points, mode=mode)
            res.template_name = tpl.name
            res.metadata = {"category": tpl.category, **tpl.metadata}
            matches.append(res)
        result = DetectionResult(
            timestamp=time.time(),
            screen_width=self.screen_width,
            screen_height=self.screen_height,
            matches=matches,
            processing_time_ms=(time.time() - start) * 1000,
            templates_checked=len(templates),
        )
        with self._lock:
            self._last_detection = result
        return result

    def map_coordinates(self, x: float, y: float,
                        region: Optional[UIRegion] = None) -> Tuple[float, float]:
        return self.mapper.map(x, y, region=region, scale=self.scale)

    def get_last_detection(self) -> Optional[DetectionResult]:
        return self._last_detection

    def update_config(self, threshold: Optional[float] = None,
                       min_confidence: Optional[float] = None,
                       scale: Optional[float] = None,
                       screen_width: Optional[int] = None,
                       screen_height: Optional[int] = None) -> Dict[str, Any]:
        if threshold is not None:
            self.matcher.threshold = threshold
        if min_confidence is not None:
            self.matcher.min_confidence = min_confidence
        if scale is not None:
            self.scale = scale
            self.mapper.scale = scale
        if screen_width is not None:
            self.screen_width = screen_width
            self.mapper.screen_width = screen_width
        if screen_height is not None:
            self.screen_height = screen_height
            self.mapper.screen_height = screen_height
        return self.get_status()

    def get_status(self) -> Dict[str, Any]:
        return {
            "threshold": self.matcher.threshold,
            "min_confidence": self.matcher.min_confidence,
            "scale": self.scale,
            "screen_width": self.screen_width,
            "screen_height": self.screen_height,
            "templates_registered": len(self.registry),
            "last_detection": self._last_detection.to_dict() if self._last_detection else None,
        }


_tracker: Optional[UITemplateTracker] = None


def get_template_tracker() -> UITemplateTracker:
    global _tracker
    if _tracker is None:
        _tracker = UITemplateTracker()
    return _tracker


def reset_template_tracker() -> None:
    global _tracker
    _tracker = None


# --------------------------------------------------------------------------- #
# REST routes
# --------------------------------------------------------------------------- #

try:
    from fastapi import APIRouter, HTTPException
    from pydantic import BaseModel

    router = APIRouter(prefix="/api/vision/track", tags=["vision", "template-tracking"])

    class RegisterTemplateRequest(BaseModel):
        name: str
        points: List[List[float]]
        category: str = "button"
        metadata: Optional[Dict[str, Any]] = None

    class DetectRequest(BaseModel):
        points: List[List[float]]
        mode: str = "partial"
        templates: Optional[List[str]] = None

    class ConfigRequest(BaseModel):
        threshold: Optional[float] = None
        min_confidence: Optional[float] = None
        scale: Optional[float] = None
        screen_width: Optional[int] = None
        screen_height: Optional[int] = None

    @router.get("/status")
    async def tracker_status() -> Dict[str, Any]:
        return get_template_tracker().get_status()

    @router.post("/config")
    async def update_tracker_config(req: ConfigRequest) -> Dict[str, Any]:
        return get_template_tracker().update_config(
            threshold=req.threshold, min_confidence=req.min_confidence,
            scale=req.scale, screen_width=req.screen_width,
            screen_height=req.screen_height)

    @router.post("/templates")
    async def register_template(req: RegisterTemplateRequest) -> Dict[str, Any]:
        tpl = get_template_tracker().register_template(
            req.name, [tuple(p) for p in req.points],
            category=req.category, metadata=req.metadata)
        return {"status": "ok", "template": tpl.to_dict()}

    @router.get("/templates")
    async def list_templates() -> Dict[str, Any]:
        return {"templates": [t.to_dict() for t in get_template_tracker().list_templates()]}

    @router.delete("/templates/{name}")
    async def remove_template(name: str) -> Dict[str, Any]:
        ok = get_template_tracker().remove_template(name)
        return {"status": "ok" if ok else "error", "removed": ok}

    @router.post("/detect")
    async def detect(request: DetectRequest) -> Dict[str, Any]:
        try:
            mode = MatchMode(request.mode)
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Invalid mode: {request.mode}")
        pts = [tuple(p) for p in request.points]
        result = get_template_tracker().detect(pts, mode=mode,
                                                 template_names=request.templates)
        return {"status": "ok", "detection": result.to_dict()}

    @router.get("/last")
    async def last_detection() -> Dict[str, Any]:
        d = get_template_tracker().get_last_detection()
        if d is None:
            return {"status": "error", "detection": None}
        return {"status": "ok", "detection": d.to_dict()}

except Exception as exc:  # pragma: no cover
    logger.warning("tracker routes skipped: %s", exc)
    router = None  # type: ignore


__all__ = [
    "CoordinateMapper",
    "DetectionResult",
    "MatchMode",
    "TemplateMatcher",
    "TemplateRegistry",
    "UIRegion",
    "UITemplate",
    "UITemplateTracker",
    "UIMatchResult",
    "get_template_tracker",
    "reset_template_tracker",
]
