"""AURA JJK Style — Jujutsu Kaisen visual theme engine.

Provides:
- Glow effects for tkinter widgets
- Cursed energy color palettes
- Domain expansion visual helpers
- Animated transitions for JJK-style UI
"""

from __future__ import annotations

import tkinter as tk
from typing import Tuple


class JJKTheme:
    BG = "#05070a"
    PANEL = "#0f1219"
    ACCENT = "#7c4dff"
    ACCENT2 = "#00e5ff"
    TEXT = "#e6e9f0"
    TEXT_DIM = "#6b7280"
    RED = "#ff4d4d"
    GREEN = "#00e676"
    YELLOW = "#ffea00"
    CYAN = "#00e5ff"
    PURPLE = "#7c4dff"
    VOID_BLACK = "#0a0a0f"
    CURSED_ENERGY = "#8a2be2"

    @staticmethod
    def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
        hex_color = hex_color.lstrip("#")
        return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))

    @staticmethod
    def rgb_to_hex(rgb: Tuple[int, int, int]) -> str:
        return "#{:02x}{:02x}{:02x}".format(*rgb)

    @staticmethod
    def glow_color(base_hex: str, intensity: float = 0.6) -> str:
        r, g, b = JJKTheme.hex_to_rgb(base_hex)
        glow_r = min(255, int(r + (255 - r) * intensity))
        glow_g = min(255, int(g + (255 - g) * intensity))
        glow_b = min(255, int(b + (255 - b) * intensity))
        return JJKTheme.rgb_to_hex((glow_r, glow_g, glow_b))

    @staticmethod
    def cursed_energy_gradient(step: int, total: int) -> str:
        ratio = step / max(1, total)
        r = int(138 + (0 - 138) * ratio)
        g = int(43 + (229 - 43) * ratio)
        b = int(226 + (255 - 226) * ratio)
        return JJKTheme.rgb_to_hex((r, g, b))

    @staticmethod
    def apply_glow(widget: tk.Widget, color: str = ACCENT, size: int = 2) -> None:
        try:
            widget.configure(highlightbackground=color, highlightcolor=color, highlightthickness=size)
        except Exception:
            pass

    @staticmethod
    def apply_domain_style(widget: tk.Widget) -> None:
        try:
            widget.configure(bg=JJKTheme.VOID_BLACK, fg=JJKTheme.CURSED_ENERGY, font=("Impact", 12, "bold"))
        except Exception:
            pass

    @staticmethod
    def animate_glow(widget: tk.Widget, color1: str, color2: str, steps: int = 10, delay: int = 50) -> None:
        try:
            for i in range(steps):
                ratio = i / max(1, steps - 1)
                r1, g1, b1 = JJKTheme.hex_to_rgb(color1)
                r2, g2, b2 = JJKTheme.hex_to_rgb(color2)
                r = int(r1 + (r2 - r1) * ratio)
                g = int(g1 + (g2 - g1) * ratio)
                b = int(b1 + (b2 - b1) * ratio)
                color = JJKTheme.rgb_to_hex((r, g, b))
                widget.after(i * delay, lambda c=color: JJKTheme.apply_glow(widget, c, 3))
        except Exception:
            pass

    @staticmethod
    def animate_transition(widget: tk.Widget, from_style: dict, to_style: dict, steps: int = 10, delay: int = 50) -> None:
        """Anima la transición de estilos de un widget tkinter.

        from_style/to_style: dict con claves como 'bg', 'fg', 'font'.
        """
        try:
            keys = set(from_style.keys()) & set(to_style.keys())
            for i in range(steps):
                ratio = i / max(1, steps - 1)
                kwargs = {}
                for key in keys:
                    v1 = from_style[key]
                    v2 = to_style[key]
                    if isinstance(v1, str) and v1.startswith("#") and isinstance(v2, str) and v2.startswith("#"):
                        r1, g1, b1 = JJKTheme.hex_to_rgb(v1)
                        r2, g2, b2 = JJKTheme.hex_to_rgb(v2)
                        r = int(r1 + (r2 - r1) * ratio)
                        g = int(g1 + (g2 - g1) * ratio)
                        b = int(b1 + (b2 - b1) * ratio)
                        kwargs[key] = JJKTheme.rgb_to_hex((r, g, b))
                    else:
                        kwargs[key] = v2 if ratio > 0.5 else v1
                widget.after(i * delay, lambda kw=kwargs: widget.configure(**kw))
        except Exception:
            pass
