"""Caelestia Theme Engine — Presets, Dotfiles y QSS Hot-Reloading.

Estilos listos para aplicar: 'Caelestia Dark Anime', 'Dank Material Glass',
'Niri Cyberpunk', 'Minimal Void'. Gestor de dotfiles JSON con export/import
en caliente. QSS dinámico con sombras neón y bordes redondeados adaptativos.
"""

from __future__ import annotations

import os
import json
from dataclasses import dataclass, asdict
from typing import Dict, Optional
from pathlib import Path

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication

DEFAULT_DOTFILES_DIR = Path.home() / ".config" / "caelestia" / "dotfiles"
DEFAULT_DOTFILES_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class ThemePreset:
    name: str
    primary: str
    secondary: str
    tertiary: str
    background_start: str
    background_end: str
    surface: str
    on_surface: str
    on_surface_dim: str
    outline: str
    neon: str
    border_radius: int
    shadow_blur: int

    def as_dict(self) -> dict:
        return asdict(self)


PRESETS: Dict[str, ThemePreset] = {
    "Caelestia Dark Anime": ThemePreset(
        "Caelestia Dark Anime",
        "#ff6b6b", "#4ecdc4", "#ffe66d",
        "#1a1a2e", "#16213e",
        "rgba(26, 26, 46, 0.40)", "#ffffff", "#cbd5e1",
        "rgba(255, 107, 107, 0.35)", "#ff6b6b", 18, 25,
    ),
    "Dank Material Glass": ThemePreset(
        "Dank Material Glass",
        "#6200ee", "#03dac6", "#ff6b6b",
        "#0f0c29", "#24243e",
        "rgba(30, 30, 45, 0.30)", "#ffffff", "#e0e0e0",
        "rgba(156, 115, 255, 0.35)", "#6200ee", 16, 20,
    ),
    "Niri Cyberpunk": ThemePreset(
        "Niri Cyberpunk",
        "#00ff88", "#ff00ff", "#00ffff",
        "#000000", "#0a0a1a",
        "rgba(10, 10, 26, 0.45)", "#e0ffe0", "#a0ffa0",
        "rgba(0, 255, 136, 0.40)", "#00ff88", 20, 30,
    ),
    "Minimal Void": ThemePreset(
        "Minimal Void",
        "#14b8a8", "#3b82f6", "#8b5cf6",
        "#0a0a0f", "#1a1a2e",
        "rgba(26, 26, 46, 0.35)", "#f8fafc", "#94a3bc",
        "rgba(56, 189, 248, 0.25)", "#14b8a8", 14, 15,
    ),
}


class CaelestiaThemeEngine(QObject):
    """Motor de temas con hot-reload de QSS y gestión de dotfiles."""

    theme_changed = Signal(str)
    dotfile_loaded = Signal(str)

    _instance: Optional["CaelestiaThemeEngine"] = None

    def __init__(self) -> None:
        super().__init__()
        self.presets: Dict[str, ThemePreset] = PRESETS
        self.current: ThemePreset = self.presets["Dank Material Glass"]
        self.dotfiles_dir: Path = DEFAULT_DOTFILES_DIR
        self._apply_qss()

    @classmethod
    def instance(cls) -> "CaelestiaThemeEngine":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def apply_preset(self, name: str) -> Optional[ThemePreset]:
        if name in self.presets:
            self.current = self.presets[name]
            self._apply_qss()
            self.theme_changed.emit(name)
            return self.current
        return None

    def _apply_qss(self) -> None:
        qss = self.generate_qss()
        if app := QApplication.instance():
            app.setStyleSheet(qss)

    def generate_qss(self) -> str:
        p = self.current
        r = p.border_radius
        shadow = p.shadow_blur
        neon = p.neon

        return f"""
        QToolTip {{
            background: {p.surface};
            color: {p.on_primary if False else p.on_surface};
            border: 1px solid {p.outline};
            border-radius: {r-2}px;
            padding: 4px 8px;
            font-size: 11px;
        }}
        QPushButton {{
            background: {p.primary};
            color: white;
            border: 1px solid {p.outline};
            border-radius: {r-4}px;
            padding: 6px 14px;
        }}
        QPushButton:hover {{
            background: {self._lighten(p.primary, 0.15)};
        }}
        QPushButton:pressed {{
            background: {self._darken(p.primary, 0.15)};
        }}
        QPushButton.toggle-on {{
            background: {p.secondary};
            border: 2px solid {neon};
        }}
        QSlider::groove:horizontal {{
            border: 1px solid {p.outline};
            height: 10px;
            border-radius: 5px;
            background: {p.surface};
        }}
        QSlider::handle:horizontal {{
            background: {neon};
            border: none;
            border-radius: 8px;
            width: 18px;
            margin: -4px 0;
            box-shadow: 0 0 {shadow}px {neon};
        }}
        QProgressBar {{
            border: 1px solid {p.outline};
            border-radius: {r-4}px;
            background: {p.surface};
            text-align: center;
            color: {p.on_surface};
        }}
        QProgressBar::chunk {{
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {p.primary}, stop:1 {p.secondary});
            border-radius: {r-6}px;
        }}
        QLabel {{
            color: {p.on_surface};
        }}
        QFrame {{
            border: 1px solid {p.outline};
            border-radius: {r}px;
        }}
        """

    def _lighten(self, color: str, factor: float) -> str:
        r, g, b = self._hex_to_rgb(color)
        return self._rgb_to_hex(int(r*(1+factor)), int(g*(1+factor)), int(b*(1+factor)))

    def _darken(self, color: str, factor: float) -> str:
        r, g, b = self._hex_to_rgb(color)
        return self._rgb_to_hex(int(r*(1-factor)), int(g*(1-factor)), int(b*(1-factor)))

    def _hex_to_rgb(self, h: str) -> tuple:
        h = h.lstrip("#")
        return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

    def _rgb_to_hex(self, r: int, g: int, b: int) -> str:
        return f"#{max(0,min(255,r)):02x}{max(0,min(255,g)):02x}{max(0,min(255,b)):02x}"

    def export_theme(self) -> dict:
        return self.current.as_dict()

    def import_theme(self, data: dict) -> bool:
        try:
            self.current = ThemePreset(**data)
            self._apply_qss()
            return True
        except (TypeError, KeyError):
            return False

    def save_dotfile(self, filename: str = "theme.json") -> str:
        path = self.dotfiles_dir / filename
        with open(path, "w") as f:
            json.dump(self.export_theme(), f, indent=2)
        return str(path)

    def load_dotfile(self, filename: str = "theme.json") -> bool:
        path = self.dotfiles_dir / filename
        try:
            with open(path) as f:
                data = json.load(f)
            if self.import_theme(data):
                self.dotfile_loaded.emit(filename)
                return True
        except Exception:
            pass
        return False

    def list_dotfiles(self) -> list:
        if not self.dotfiles_dir.exists():
            return []
        return [f.name for f in self.dotfiles_dir.glob("*.json")]

    def list_presets(self) -> list:
        return list(self.presets.keys())

    def current_as_label_css(self, size: int = 11, bold: bool = False, color: Optional[str] = None) -> str:
        p = self.current
        c = color or p.on_surface
        weight = "bold" if bold else "normal"
        return f"color: {c}; font-size: {size}px; font-weight: {weight}; font-family: 'Segoe UI', sans-serif;"

    def current_as_header_css(self) -> str:
        p = self.current
        return f"font-size: 16px; font-weight: bold; color: {p.primary}; font-family: 'Segoe UI', sans-serif;"

    def current_as_glass_css(self, widget_name: str = "") -> str:
        p = self.current
        selector = f"#{widget_name}" if widget_name else "QWidget"
        return f"""
        {selector} {{
            background: {p.surface};
            border: 1px solid {p.outline};
            border-radius: {p.border_radius}px;
        }}
        """


theme_engine = CaelestiaThemeEngine.instance()
