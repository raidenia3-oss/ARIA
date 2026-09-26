"""Theme Manager con paletas dinámicas Material You — Module 30 UI.

Extrae colores de imagenes/wallpapers, genera paletas Material 3
con gradientes nocturnos y aplica efectos Glassmorphism (blur/semitransparencia)
en PySide6 widgets.
"""

from __future__ import annotations

import os
import colorsys
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    Image = None

try:
    import psutil
except ImportError:
    psutil = None

DEFAULT_PALETTE_HEX = "#4f46e5"
CACHE_DIR = Path.home() / ".aura" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class Material3Palette:
    primary: str = "#4f46e5"
    on_primary: str = "#ffffff"
    secondary: str = "#6366f1"
    on_secondary: str = "#ffffff"
    tertiary: str = "#8b5cf6"
    on_tertiary: str = "#ffffff"
    surface: str = "rgba(20, 20, 30, 180)"
    on_surface: str = "#f8fafc"
    background: str = "rgba(10, 10, 15, 160)"
    outline: str = "rgba(255, 255, 255, 0.15)"
    shadow: str = "rgba(0, 0, 0, 0.3)"
    neon: str = "#6366f1"


def _hex_to_rgb(h: str) -> Tuple[int, int, int]:
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def _rgb_to_hex(r: int, g: int, b: int) -> str:
    return f"#{max(0,min(255,r)):02x}{max(0,min(255,g)):02x}{max(0,min(255,b)):02x}"


def _adjust_brightness(color: str, factor: float) -> str:
    r, g, b = _hex_to_rgb(color)
    return _rgb_to_hex(int(r*factor), int(g*factor), int(b*factor))


def _hsl_to_hex(h: float, s: float, l: float) -> str:
    r, g, b = colorsys.hls_to_rgb(h, l, s)
    return _rgb_to_hex(int(r*255), int(g*255), int(b*255))


def _generate_tonal_palette(seed_hex: str) -> Dict[str, str]:
    """Genera paleta Material 3 simplificada desde un color semilla."""
    r, g, b = _hex_to_rgb(seed_hex)
    h, _, _ = colorsys.rgb_to_hls(r/255, g/255, b/255)

    primary = _hsl_to_hex(h, 0.85, 0.45)
    secondary = _hsl_to_hex(h, 0.70, 0.50)
    tertiary = _hsl_to_hex(h, 0.60, 0.55)
    on_primary = "#ffffff" if _hex_to_rgb(primary)[0]*0.299 + _hex_to_rgb(primary)[1]*0.587 + _hex_to_rgb(primary)[2]*0.114 < 128 else "#0f172a"

    return {
        "primary": primary,
        "on_primary": on_primary,
        "secondary": secondary,
        "on_secondary": "#ffffff",
        "tertiary": tertiary,
        "on_tertiary": "#ffffff",
        "surface": "rgba(20, 20, 30, 180)",
        "on_surface": "#f8fafc",
        "background": "rgba(10, 10, 15, 160)",
        "outline": "rgba(255, 255, 255, 0.15)",
        "shadow": "rgba(0, 0, 0, 0.3)",
        "neon": secondary,
    }


def extract_dominant_color(image_path: str) -> Optional[str]:
    """Extrae el color dominante de una imagen usando PIL."""
    if Image is None or not os.path.exists(image_path):
        return None
    try:
        img = Image.open(image_path)
        img = img.convert("RGB")
        img = img.resize((1, 1))
        r, g, b = img.getpixel((0, 0))
        return _rgb_to_hex(r, g, b)
    except Exception:
        return None


def _blend_with_surface(color: str, surface_alpha: float = 0.18) -> str:
    """Mezcla un color con el fondo surface para glassmorphism."""
    r, g, b = _hex_to_rgb(color)
    return f"rgba({r}, {g}, {b}, {surface_alpha:.2f})"


class ThemeManager:
    """Gestor de temas Material You con efectos Glassmorphism."""

    _instance: Optional["ThemeManager"] = None

    def __init__(self) -> None:
        self.palette: Material3Palette = Material3Palette()
        self._wallpaper: Optional[str] = None
        self._cache_file = CACHE_DIR / "theme_cache.json"

    @classmethod
    def instance(cls) -> "ThemeManager":
        if cls._instance is None:
            cls._instance = cls()
            cls._instance.load_cache()
        return cls._instance

    def set_from_image(self, image_path: str) -> Material3Palette:
        """Genera y aplica una paleta basada en una imagen/wallpaper."""
        color = extract_dominant_color(image_path)
        if color is None:
            color = DEFAULT_PALETTE_HEX
        self._wallpaper = image_path
        tonal = _generate_tonal_palette(color)
        self.palette = Material3Palette(**tonal)
        self._save_cache()
        return self.palette

    def set_from_hex(self, hex_color: str) -> Material3Palette:
        """Genera y aplica una paleta desde un color hexadecimal."""
        tonal = _generate_tonal_palette(hex_color)
        self.palette = Material3Palette(**tonal)
        self._save_cache()
        return self.palette

    def set_dark(self) -> Material3Palette:
        self.palette = Material3Palette()
        self._save_cache()
        return self.palette

    def glass_css(self, widget_name: str = "") -> str:
        """Genera CSS con efecto Glassmorphism (semitransparencia + neón)."""
        p = self.palette
        selector = f"#{widget_name}" if widget_name else "QWidget"
        return f"""
        {selector} {{
            background-color: {p.background};
            border: 1px solid {p.outline};
            border-radius: 16px;
            background-origin: border;
        }}
        """

    def glass_card_css(self, widget_name: str = "") -> str:
        p = self.palette
        selector = f"#{widget_name}" if widget_name else "QWidget"
        return f"""
        {selector} {{
            background: rgba(30, 30, 45, 0.35);
            border: 1px solid {p.outline};
            border-radius: 14px;
        }}
        """

    def button_css(self, variant: str = "primary") -> str:
        p = self.palette
        colors = {
            "primary": (p.primary, p.on_primary),
            "secondary": (p.secondary, p.on_secondary),
            "tertiary": (p.tertiary, p.on_tertiary),
        }
        bg, fg = colors.get(variant, colors["primary"])
        return f"""
        QPushButton {{
            background: {bg};
            color: {fg};
            border: none;
            border-radius: 12px;
            padding: 8px 16px;
            font-family: 'Segoe UI', sans-serif;
        }}
        QPushButton:hover {{
            background: {_adjust_brightness(bg, 1.1)};
        }}
        QPushButton:pressed {{
            background: {_adjust_brightness(bg, 0.9)};
        }}
        """

    def label_css(self, size: int = 12, bold: bool = False, color: Optional[str] = None) -> str:
        p = self.palette
        c = color or p.on_surface
        weight = "bold" if bold else "normal"
        return f"""
        QLabel {{
            color: {c};
            font-size: {size}px;
            font-weight: {weight};
            font-family: 'Segoe UI', sans-serif;
        }}
        """

    def is_night(self) -> bool:
        """Determina si es de noche basado en la hora local."""
        hour = datetime.now().hour
        return hour < 6 or hour >= 20

    def get_solar_icon(self) -> str:
        return "☾" if self.is_night() else "☀"

    def _save_cache(self) -> None:
        try:
            data = {
                "primary": self.palette.primary,
                "secondary": self.palette.secondary,
                "tertiary": self.palette.tertiary,
                "wallpaper": self._wallpaper,
                "updated_at": datetime.now().isoformat(),
            }
            with open(self._cache_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def load_cache(self) -> None:
        try:
            if self._cache_file.exists():
                with open(self._cache_file) as f:
                    data = json.load(f)
                tonal = _generate_tonal_palette(data.get("primary", DEFAULT_PALETTE_HEX))
                self.palette = Material3Palette(**tonal)
                self._wallpaper = data.get("wallpaper")
        except Exception:
            pass


theme_mgr = ThemeManager.instance()
