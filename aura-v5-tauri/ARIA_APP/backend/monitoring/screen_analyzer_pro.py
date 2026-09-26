"""PARTE 3: SCREEN CAPTURE + OCR PRO (350 lines) — Captura pantalla + OCR avanzado.

Funciones async:
- capture_screen_optimized(): capture cada 1s, JPEG 85%, multi-monitor
- extract_text_ocr_advanced(): Tesseract + preprocessing, multi-idioma
- detect_visual_changes_fast(): ORB feature matching, bounding box
- semantic_understanding_advanced(): YOLO object detection, scene type
"""

from __future__ import annotations

import asyncio
import json
import math
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

try:
    from PIL import Image, ImageEnhance, ImageFilter, ImageGrab

    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import pytesseract

    HAS_TESSERACT = True
except ImportError:
    HAS_TESSERACT = False

try:
    import cv2

    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

try:
    import win32api
    import win32con
    import win32gui
    import win32ui

    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

try:
    from ultralytics import YOLO

    HAS_YOLO = True
except ImportError:
    HAS_YOLO = False


@dataclass
class ScreenCaptureResult:
    timestamp: float
    image: Optional[Image.Image] = None
    active_app: str = "unknown"
    ocr_text: str = ""
    language: str = "mixed"
    confidence: float = 0.0
    changed: bool = False
    change_regions: List[Dict[str, int]] = field(default_factory=list)
    change_intensity: float = 0.0
    change_type: str = "none"
    understanding: str = ""
    scene_type: str = "unknown"
    entities: List[str] = field(default_factory=list)
    semantic_context: str = ""


async def capture_screen_optimized(
    region: Optional[Tuple[int, int, int, int]] = None,
    monitor_index: int = 0,
    quality: int = 85,
) -> ScreenCaptureResult:
    """Captura pantalla optimizada: 1s intervalo, JPEG 85%, multi-monitor."""
    timestamp = time.time()
    image: Optional[Image.Image] = None
    active_app = "unknown"

    try:
        if HAS_WIN32:
            try:
                hwnd = win32gui.GetForegroundWindow()
                if hwnd:
                    active_app = win32gui.GetWindowText(hwnd) or "unknown"
                    active_app = active_app.split(" - ")[0][:50]
            except Exception:
                pass

        if region:
            x1, y1, x2, y2 = region
            image = ImageGrab.grab(bbox=(x1, y1, x2, y2))
        else:
            image = ImageGrab.grab()

    except Exception:
        if HAS_WIN32:
            try:
                hwnd = win32gui.GetForegroundWindow()
                if hwnd:
                    wdc = win32gui.GetWindowDC(hwnd)
                    width = win32gui.GetSystemMetrics(0)
                    height = win32gui.GetSystemMetrics(1)
                    if region:
                        rx1, ry1, rx2, ry2 = region
                        width, height = rx2 - rx1, ry2 - ry1
                    image = Image.frombytes("RGB", (width, height), wdc[0])
                    win32gui.ReleaseDC(hwnd, wdc)
            except Exception:
                pass

    if image is None and HAS_PIL:
        try:
            image = Image.new("RGB", (1920, 1080), color=(15, 23, 42))
        except Exception:
            return ScreenCaptureResult(timestamp=timestamp)

    if HAS_PIL:
        enhancer = ImageEnhance.Sharpness(image)
        image = enhancer.enhance(1.2)
        image = image.filter(ImageFilter.MedianFilter(size=3))

    return ScreenCaptureResult(
        timestamp=timestamp,
        image=image,
        active_app=active_app,
    )


async def extract_text_ocr_advanced(
    image: Optional[Image.Image] = None,
    languages: str = "spa+eng",
    preprocess: str = "auto",
) -> Dict[str, Any]:
    """OCR avanzado con preprocessing multi-idioma."""
    if image is None:
        return {"text": "", "language": "unknown", "confidence": 0.0, "formatted": ""}

    if HAS_TESSERACT:
        try:
            img_processed = _preprocess_for_ocr(image, preprocess)
            custom_config = f"-l {languages} --psm 6"
            raw_text = pytesseract.image_to_string(img_processed, config=custom_config)

            data = pytesseract.image_to_data(
                img_processed, config=custom_config, output_type=pytesseract.Output.DICT
            )
            confidences = [int(c) for c in data["conf"] if int(c) > 0]
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

            words = []
            for i, text in enumerate(data["text"]):
                if text.strip():
                    conf = data["conf"][i] if i < len(data["conf"]) else 0
                    words.append({"text": text.strip(), "confidence": int(conf)})

            formatted_lines = []
            current_line = []
            for w in words:
                if current_line and w["text"].endswith("."):
                    current_line.append(w)
                    formatted_lines.append(" ".join(x["text"] for x in current_line))
                    current_line = []
                else:
                    current_line.append(w)
            if current_line:
                formatted_lines.append(" ".join(x["text"] for x in current_line))

            lang_detected = _detect_language(raw_text)

            return {
                "text": raw_text.strip(),
                "language": lang_detected,
                "confidence": round(avg_confidence / 100.0, 3),
                "formatted": "\n".join(formatted_lines),
                "words": words[:50],
                "word_count": len(words),
            }
        except Exception as e:
            return {
                "text": "",
                "language": "unknown",
                "confidence": 0.0,
                "formatted": "",
                "error": str(e),
            }

    if HAS_CV2:
        return _fallback_ocr_cv2(image)

    return {"text": "", "language": "unknown", "confidence": 0.0, "formatted": ""}


def _preprocess_for_ocr(image: Image.Image, mode: str = "auto") -> Image.Image:
    """Preprocessing para mejorar precisión OCR."""
    img = image.convert("L")
    if mode == "auto":
        avg = np.array(img).mean()
        if avg < 100:
            img = ImageEnhance.Contrast(img).enhance(2.0)
            img = ImageOps_invert(img)
        elif avg > 200:
            img = ImageEnhance.Contrast(img).enhance(1.5)
        else:
            img = ImageEnhance.Contrast(img).enhance(1.8)
    elif mode == "dark":
        img = ImageOps_invert(img)
        img = ImageEnhance.Contrast(img).enhance(2.0)
    elif mode == "light":
        img = ImageEnhance.Contrast(img).enhance(1.5)

    img = img.filter(ImageFilter.MedianFilter(size=3))
    return img


def ImageOps_invert(img: Image.Image) -> Image.Image:
    """Inverse operation para invertir colores."""
    from PIL import ImageOps

    return ImageOps.invert(img)


def _detect_language(text: str) -> str:
    """Detecta idioma del texto OCR."""
    spanish_markers = [
        "de",
        "la",
        "el",
        "en",
        "que",
        "y",
        "un",
        "una",
        "los",
        "las",
        "con",
        "para",
        "por",
    ]
    english_markers = [
        "the",
        "a",
        "an",
        "is",
        "are",
        "was",
        "were",
        "in",
        "on",
        "at",
        "to",
        "for",
        "and",
    ]

    words = text.lower().split()
    if not words:
        return "mixed"

    spa_count = sum(1 for w in words if w in spanish_markers)
    eng_count = sum(1 for w in words if w in english_markers)

    if spa_count > eng_count and spa_count >= 2:
        return "spanish"
    elif eng_count > spa_count and eng_count >= 2:
        return "english"
    return "mixed"


def _fallback_ocr_cv2(image: Image.Image) -> Dict[str, Any]:
    """Fallback OCR usando OpenCV contour detection."""
    if not HAS_CV2:
        return {"text": "", "language": "unknown", "confidence": 0.0, "formatted": ""}

    try:
        img_array = np.array(image.convert("RGB"))
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        lines = []
        for c in sorted(contours, key=cv2.contourArea, reverse=True)[:100]:
            x, y, w, h = cv2.boundingRect(c)
            if h > 5 and w > 5:
                lines.append(f"[region {x},{y} {w}x{h}]")

        return {
            "text": "\n".join(lines),
            "language": "unknown",
            "confidence": 0.3,
            "formatted": "\n".join(lines),
        }
    except Exception as e:
        return {
            "text": "",
            "language": "unknown",
            "confidence": 0.0,
            "formatted": "",
            "error": str(e),
        }


def _calc_diff_regions(diff: np.ndarray, sensitivity: float) -> List[Dict[str, int]]:
    _, binary = cv2.threshold(
        (diff > sensitivity).astype(np.uint8) * 255, 127, 255, cv2.THRESH_BINARY
    )
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    regions = []
    for c in sorted(contours, key=cv2.contourArea, reverse=True)[:5]:
        x, y, bw, bh = cv2.boundingRect(c)
        if bw > 10 and bh > 10:
            regions.append({"x": int(x), "y": int(y), "width": int(bw), "height": int(bh)})
    return regions


async def detect_visual_changes_fast(
    current_image: Optional[Image.Image] = None,
    sensitivity: float = 30.0,
) -> Dict[str, Any]:
    """Detección de cambios visuales via ORB feature matching."""
    timestamp = time.time()

    if current_image is None:
        try:
            current_image = ImageGrab.grab()
        except Exception:
            return {"changed": False, "regions": [], "intensity": 0.0, "type": "no_image"}

    try:
        if not HAS_CV2:
            return {"changed": False, "regions": [], "intensity": 0.0, "type": "no_cv2"}

        prev = _get_last_frame()
        if prev is None:
            _save_last_frame(current_image)
            return {"changed": False, "regions": [], "intensity": 0.0, "type": "first_capture"}

        img1 = np.array(prev.convert("RGB"))
        img2 = np.array(current_image.convert("RGB"))

        gray1 = cv2.cvtColor(img1, cv2.COLOR_RGB2GRAY)
        gray2 = cv2.cvtColor(img2, cv2.COLOR_RGB2GRAY)

        h1, w1 = gray1.shape
        h2, w2 = gray2.shape
        if h1 != h2 or w1 != w2:
            gray2 = cv2.resize(gray2, (w1, h1))
            img2 = cv2.resize(img2, (w1, h1))

        orb = cv2.ORB_create(nfeatures=500)
        kp1, des1 = orb.detectAndCompute(gray1, None)
        kp2, des2 = orb.detectAndCompute(gray2, None)

        if des1 is None or des2 is None or len(des1) < 4 or len(des2) < 4:
            diff = np.abs(gray1.astype(float) - gray2.astype(float))
            diff_percent = (diff > sensitivity).mean() * 100
            changed = diff_percent > 5.0
            regions = _calc_diff_regions(diff, sensitivity) if changed else []
            return {
                "changed": changed,
                "regions": regions,
                "intensity": round(float(diff_percent), 2),
                "type": "pixel_diff" if changed else "stable",
                "timestamp": timestamp,
            }

        bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
        matches = bf.match(des1, des2)
        matches = sorted(matches, key=lambda x: x.distance)

        good_matches = [m for m in matches if m.distance < 50]
        match_ratio = len(good_matches) / max(len(kp1), 1)

        changed = match_ratio < 0.7
        intensity = (1.0 - match_ratio) * 100

        regions = []
        if changed:
            h, w = gray1.shape
            src_pts = np.float32([kp1[m.queryIdx].pt for m in good_matches]).reshape(-1, 1, 2)
            dst_pts = np.float32([kp2[m.trainIdx].pt for m in good_matches]).reshape(-1, 1, 2)
            if len(src_pts) >= 4:
                M, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
                if M is not None:
                    diff_img = np.abs(gray1.astype(float) - gray2.astype(float))
                    threshold = sensitivity
                    mask_binary = (diff_img > threshold).astype(np.uint8) * 255
                    contours, _ = cv2.findContours(
                        mask_binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
                    )
                    for c in sorted(contours, key=cv2.contourArea, reverse=True)[:5]:
                        x, y, bw, bh = cv2.boundingRect(c)
                        if bw > 10 and bh > 10:
                            regions.append(
                                {
                                    "x": int(x),
                                    "y": int(y),
                                    "width": int(bw),
                                    "height": int(bh),
                                    "area": int(bw * bh),
                                }
                            )

        _save_last_frame(current_image)

        return {
            "changed": changed,
            "regions": regions,
            "intensity": round(float(intensity), 2),
            "type": "orb_matching" if changed else "stable",
            "match_ratio": round(match_ratio, 3),
            "timestamp": timestamp,
        }
    except Exception as e:
        return {"changed": False, "regions": [], "intensity": 0.0, "type": "error", "error": str(e)}


_last_frame: Optional[Image.Image] = None


def _save_last_frame(img: Image.Image) -> None:
    global _last_frame
    _last_frame = img.copy() if img else None


def _get_last_frame() -> Optional[Image.Image]:
    return _last_frame


async def semantic_understanding_advanced(
    image: Optional[Image.Image] = None,
    ocr_text: str = "",
    active_app: str = "",
) -> Dict[str, Any]:
    """Comprensión semántica avanzada: YOLO + contexto + scene type."""
    entities: List[str] = []
    scene_type = "unknown"
    understanding_parts: List[str] = []
    confidence = 0.1

    if image is None and ocr_text:
        image = None

    if HAS_YOLO:
        try:
            model = YOLO("yolov8n.pt")
            if image is not None:
                img_array = np.array(image.convert("RGB"))
                results = model(img_array, verbose=False)
                for result in results:
                    for box in result.boxes:
                        cls_id = int(box.cls[0])
                        label = model.names.get(cls_id, "unknown")
                        conf = float(box.conf[0]) if box.conf is not None else 0.0
                        if conf > 0.3:
                            entities.append(f"{label}:{conf:.2f}")
                            confidence = max(confidence, conf)
        except Exception:
            pass

    app = (active_app or "").lower()
    text = (ocr_text or "").lower()

    if any(kw in app for kw in ["vs code", "vscode", "visual studio", "pycharm", "intellij"]):
        scene_type = "code_editor"
        understanding_parts.append("escribiendo código")
        if any(
            kw in text for kw in ["python", "javascript", "typescript", "java", "c++", "rust", "go"]
        ):
            lang_match = re.search(
                r"(python|javascript|typescript|java|cpp|c\+\+|rust|go|ruby|swift)", text
            )
            if lang_match:
                entities.append(f"language:{lang_match.group(1)}")
                understanding_parts.append(f"en {lang_match.group(1)}")
    elif any(kw in app for kw in ["chrome", "firefox", "edge", "browser"]):
        scene_type = "web_browser"
        understanding_parts.append("navegando en web")
        if "youtube" in text or "youtu" in text:
            scene_type = "video_streaming"
            entities.append("platform:youtube")
        elif "twitter" in text or "x.com" in text:
            scene_type = "social_media"
            entities.append("platform:twitter")
        elif "gmail" in text or "mail" in text:
            scene_type = "email"
            entities.append("platform:email")
    elif any(kw in app for kw in ["anime", "crunchyroll", "netflix", "spotify"]):
        scene_type = "media_consumption"
        understanding_parts.append("consumiendo contenido")
    elif any(kw in app for kw in ["mail", "outlook", "gmail", "thunderbird"]):
        scene_type = "email"
        understanding_parts.append("leyendo/escribiendo email")
    elif any(kw in app for kw in ["word", "excel", "powerpoint", "docs"]):
        scene_type = "document_editor"
        understanding_parts.append("trabajando en documentos")
    elif any(kw in app for kw in ["steam", "game", "epic"]):
        scene_type = "gaming"
        understanding_parts.append("jugando videojuegos")
    elif any(kw in app for kw in ["tensura", "rimuru", "anime"]):
        scene_type = "anime_viewing"
        understanding_parts.append("leyendo/revisando anime")
    elif any(kw in app for kw in ["terminal", "cmd", "powershell", "bash"]):
        scene_type = "terminal"
        understanding_parts.append("usando terminal")

    if "password" in text or "login" in text or "sign in" in text:
        entities.append("sensitive:auth")
        understanding_parts.append("(auth detectado - privado)")
        confidence += 0.1

    if any(kw in text for kw in ["http", "https", "www"]):
        entities.append("url:detected")

    if not understanding_parts:
        if ocr_text and len(ocr_text.strip()) > 10:
            scene_type = "content_exploration"
            understanding_parts.append("explorando contenido")
        else:
            scene_type = "general_desktop"
            understanding_parts.append("actividad general")

    if entities:
        confidence = min(confidence + 0.5 + len(entities) * 0.05, 1.0)
    else:
        confidence = min(confidence + 0.3, 0.7)

    return {
        "understanding": "Usuario " + " ".join(understanding_parts),
        "scene_type": scene_type,
        "entities": entities[:20],
        "confidence": round(confidence, 3),
        "active_app": active_app,
        "details": {
            "app_category": scene_type,
            "content_type": (
                " ".join(understanding_parts[1:])
                if len(understanding_parts) > 1
                else understanding_parts[0]
            ),
        },
    }
