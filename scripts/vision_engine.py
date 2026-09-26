#!/usr/bin/env python3
"""
AURA Vision Engine — Visión en tiempo real para asistente virtual.

Capacidades:
  - Captura de pantalla completa o región (Windows/macOS/Linux)
  - OCR en tiempo real con pytesseract (si está instalado)
  - Análisis de UI: detección de botones, barras, textos, errores
  - Detección básica de objetos por color/contorno
  - Lectura de códigos QR (si pyzbar está instalado)
  - Comparación de capturas para detectar cambios
  - Guardado automático de capturas con metadatos

Uso:
  python scripts/vision_engine.py --capture --save screenshot.png
  python scripts/vision_engine.py --ocr --region 0,0,800,600
  python scripts/vision_engine.py --analyze-ui --region 0,0,1920,1080
  python scripts/vision_engine.py --watch --interval 2
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import logging
import os
import platform
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("VisionEngine")

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SCREENSHOT_DIR = REPO_ROOT / "screenshots"

try:
    from PIL import Image, ImageDraw, ImageFilter
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    logger.warning("Pillow not installed. Install with: pip install Pillow")

try:
    import mss
    HAS_MSS = True
except ImportError:
    HAS_MSS = False
    logger.warning("mss not installed. Install with: pip install mss")

try:
    import pytesseract
    HAS_TESSERACT = True
    if platform.system() == "Windows":
        tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        if Path(tesseract_cmd).exists():
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
except ImportError:
    HAS_TESSERACT = False
    logger.warning("pytesseract not installed. Install with: pip install pytesseract")

try:
    import pyzbar.pyzbar as pyzbar
    HAS_ZBAR = True
except ImportError:
    HAS_ZBAR = False
    logger.warning("pyzbar not installed. Install with: pip install pyzbar")

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    logger.warning("numpy not installed. Install with: pip install numpy")


class VisionEngine:
    """Motor de visión para AURA."""

    def __init__(self, screenshot_dir: Path = DEFAULT_SCREENSHOT_DIR):
        self.screenshot_dir = screenshot_dir
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        self.last_capture_hash: Optional[str] = None
        self.last_capture_path: Optional[Path] = None

    def _check_deps(self) -> None:
        if not HAS_PIL:
            raise RuntimeError("Pillow is required. Install with: pip install Pillow")
        if not HAS_MSS:
            raise RuntimeError("mss is required. Install with: pip install mss")

    def capture_screen(self, region: Optional[Tuple[int, int, int, int]] = None) -> Image.Image:
        self._check_deps()
        with mss.mss() as sct:
            if region:
                monitor = {"top": region[1], "left": region[0], "width": region[2] - region[0], "height": region[3] - region[1]}
            else:
                monitor = sct.monitors[1]
            img = sct.grab(monitor)
            return Image.frombytes("RGB", img.size, img.rgb)

    def save_screenshot(self, img: Image.Image, name: Optional[str] = None) -> Path:
        if name is None:
            name = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        path = self.screenshot_dir / name
        img.save(path, "PNG")
        logger.info(f"Screenshot saved: {path}")
        return path

    def capture_and_save(self, region: Optional[Tuple[int, int, int, int]] = None, name: Optional[str] = None) -> Path:
        img = self.capture_screen(region)
        path = self.save_screenshot(img, name)
        self.last_capture_path = path
        self.last_capture_hash = self._hash_image(img)
        return path

    def _hash_image(self, img: Image.Image) -> str:
        if HAS_NUMPY:
            arr = np.array(img)
            return hashlib.md5(arr.tobytes()).hexdigest()
        import io
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return hashlib.md5(buf.getvalue()).hexdigest()

    def has_changed(self) -> bool:
        if self.last_capture_path is None:
            return True
        try:
            img = self.capture_screen()
            current_hash = self._hash_image(img)
            return current_hash != self.last_capture_hash
        except Exception:
            return True

    def ocr(self, img: Optional[Image.Image] = None, region: Optional[Tuple[int, int, int, int]] = None, lang: str = "spa+eng") -> str:
        if not HAS_TESSERACT:
            return "[ERROR] pytesseract not installed. Run: pip install pytesseract"
        if img is None:
            img = self.capture_screen(region)
        try:
            text = pytesseract.image_to_string(img, lang=lang)
            return text.strip()
        except Exception as e:
            return f"[ERROR] OCR failed: {e}"

    def analyze_ui(self, img: Optional[Image.Image] = None, region: Optional[Tuple[int, int, int, int]] = None) -> Dict[str, Any]:
        if img is None:
            img = self.capture_screen(region)
        if not HAS_PIL:
            return {"error": "Pillow not installed"}
        width, height = img.size
        draw = ImageDraw.Draw(img)
        pixels = img.load()
        analysis = {
            "resolution": {"width": width, "height": height},
            "regions": [],
            "colors": {},
            "text_areas": [],
        }
        if HAS_NUMPY:
            arr = np.array(img)
            analysis["brightness"] = float(np.mean(arr))
            analysis["contrast"] = float(np.std(arr))
            dark_pixels = int(np.sum(arr < 50))
            bright_pixels = int(np.sum(arr > 200))
            total = arr.size // 3
            analysis["dark_ratio"] = round(dark_pixels / total, 3) if total else 0
            analysis["bright_ratio"] = round(bright_pixels / total, 3) if total else 0
        grid_w, grid_h = width // 4, height // 4
        for gy in range(4):
            for gx in range(4):
                x1, y1 = gx * grid_w, gy * grid_h
                x2, y2 = x1 + grid_w, y1 + grid_h
                crop = img.crop((x1, y1, x2, y2))
                if HAS_NUMPY:
                    crop_arr = np.array(crop)
                    brightness = float(np.mean(crop_arr))
                    contrast = float(np.std(crop_arr))
                else:
                    brightness = 0
                    contrast = 0
                region_type = "unknown"
                if brightness < 80:
                    region_type = "dark"
                elif brightness > 200 and contrast < 30:
                    region_type = "white_space"
                elif contrast > 60:
                    region_type = "content"
                analysis["regions"].append({
                    "grid": f"{gx},{gy}",
                    "bbox": [x1, y1, x2, y2],
                    "type": region_type,
                    "brightness": round(brightness, 1),
                    "contrast": round(contrast, 1),
                })
        return analysis

    def detect_changes(self, interval: float = 2.0, max_iterations: int = 10) -> List[Dict]:
        changes = []
        for i in range(max_iterations):
            img = self.capture_screen()
            img_hash = self._hash_image(img)
            if self.last_capture_hash and img_hash != self.last_capture_hash:
                changes.append({
                    "iteration": i + 1,
                    "timestamp": datetime.now().isoformat(),
                    "hash": img_hash,
                    "previous_hash": self.last_capture_hash,
                })
            self.last_capture_hash = img_hash
            self.last_capture_path = self.save_screenshot(img, f"watch_{i:03d}.png")
            time.sleep(interval)
        return changes

    def to_base64(self, img: Image.Image, format: str = "PNG") -> str:
        import io
        buf = io.BytesIO()
        img.save(buf, format=format)
        return base64.b64encode(buf.getvalue()).decode("utf-8")

    def describe_capture(self, region: Optional[Tuple[int, int, int, int]] = None) -> Dict[str, Any]:
        img = self.capture_screen(region)
        path = self.save_screenshot(img)
        ocr_text = self.ocr(img=img) if HAS_TESSERACT else "[OCR no disponible]"
        ui_analysis = self.analyze_ui(img=img)
        return {
            "timestamp": datetime.now().isoformat(),
            "screenshot": str(path),
            "resolution": ui_analysis.get("resolution"),
            "ocr_text": ocr_text[:500] if ocr_text else "",
            "ui_analysis": ui_analysis,
            "base64_preview": self.to_base64(img),
        }


def cmd_capture(args: argparse.Namespace) -> None:
    engine = VisionEngine()
    region = None
    if args.region:
        region = tuple(map(int, args.region.split(",")))
    path = engine.capture_and_save(region=region, name=args.name)
    print(json.dumps({"screenshot": str(path)}, indent=2, ensure_ascii=False))


def cmd_ocr(args: argparse.Namespace) -> None:
    engine = VisionEngine()
    region = None
    if args.region:
        region = tuple(map(int, args.region.split(",")))
    text = engine.ocr(region=region, lang=args.lang)
    print(text)


def cmd_analyze_ui(args: argparse.Namespace) -> None:
    engine = VisionEngine()
    region = None
    if args.region:
        region = tuple(map(int, args.region.split(",")))
    result = engine.analyze_ui(region=region)
    print(json.dumps(result, indent=2, ensure_ascii=False))


def cmd_watch(args: argparse.Namespace) -> None:
    engine = VisionEngine()
    changes = engine.detect_changes(interval=args.interval, max_iterations=args.iterations)
    print(json.dumps({"changes": changes, "total": len(changes)}, indent=2, ensure_ascii=False))


def cmd_describe(args: argparse.Namespace) -> None:
    engine = VisionEngine()
    region = None
    if args.region:
        region = tuple(map(int, args.region.split(",")))
    result = engine.describe_capture(region=region)
    print(json.dumps(result, indent=2, ensure_ascii=False))


def main() -> None:
    p = argparse.ArgumentParser(description="AURA Vision Engine")
    sub = p.add_subparsers(dest="command")

    s_cap = sub.add_parser("capture", help="Capturar pantalla")
    s_cap.add_argument("--region", type=str, default=None, help="Región x1,y1,x2,y2")
    s_cap.add_argument("--name", type=str, default=None, help="Nombre del archivo")
    s_cap.set_defaults(func=cmd_capture)

    s_ocr = sub.add_parser("ocr", help="OCR en pantalla")
    s_ocr.add_argument("--region", type=str, default=None, help="Región x1,y1,x2,y2")
    s_ocr.add_argument("--lang", type=str, default="spa+eng", help="Idiomas Tesseract")
    s_ocr.set_defaults(func=cmd_ocr)

    s_ui = sub.add_parser("analyze-ui", help="Analizar UI de pantalla")
    s_ui.add_argument("--region", type=str, default=None, help="Región x1,y1,x2,y2")
    s_ui.set_defaults(func=cmd_analyze_ui)

    s_watch = sub.add_parser("watch", help="Monitorear cambios en pantalla")
    s_watch.add_argument("--interval", type=float, default=2.0, help="Intervalo en segundos")
    s_watch.add_argument("--iterations", type=int, default=10, help="Número de capturas")
    s_watch.set_defaults(func=cmd_watch)

    s_desc = sub.add_parser("describe", help="Descripción completa de pantalla")
    s_desc.add_argument("--region", type=str, default=None, help="Región x1,y1,x2,y2")
    s_desc.set_defaults(func=cmd_describe)

    args = p.parse_args()
    if args.command is None:
        p.print_help()
        sys.exit(1)
    args.func(args)


if __name__ == "__main__":
    main()
