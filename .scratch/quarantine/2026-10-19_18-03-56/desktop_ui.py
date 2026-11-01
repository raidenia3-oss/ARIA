# -*- coding: utf-8 -*-
"""ARIA Desktop UI - PyQt5 window with orb visual, chat, and IPC client."""

from __future__ import annotations

import json
import math
import os
import sys
import threading
import time
import queue
from pathlib import Path

ARIA_APP = Path(__file__).resolve().parent
PROJECT_ROOT = ARIA_APP.parent
for p in [str(ARIA_APP)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread, QSize, QEasingCurve, QSettings
from PyQt5.QtGui import QPainter, QColor, QFont, QPen, QBrush, QIcon, QRadialGradient, QFontDatabase, QKeySequence
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QTextEdit, QLineEdit, QPushButton, QLabel, QListWidget,
    QListWidgetItem, QFrame, QSizePolicy, QMessageBox, QSystemTrayIcon, QMenu,
    QScrollArea, QButtonGroup, QProxyStyle, QStyle, QStyleOptionButton, QShortcut)
from PyQt5.QtWidgets import QPushButton as _QBtn

# ── Serpentium Color Palette ──────────────────────────────────────────────────
C_BG_DEEP    = "#0f172a"   # primary deep blue
C_BG_MID     = "#1e293b"   # mid tone
C_BG_CARD    = "#1a2342"   # card background
C_ACCENT     = "#38bdf8"   # cyan accent
C_SECONDARY  = "#c084fc"   # purple hover
C_SUCCESS    = "#10b981"   # green
C_WARNING    = "#f59e0b"   # orange
C_TEXT_DIM   = "#94a3b8"   # dim text
C_TEXT_MAIN  = "#e2e8f0"   # main text
C_GLOW_CYAN  = QColor(56, 189, 248, 60)
C_GLOW_PURPLE= QColor(192, 132, 252, 50)
C_BORDER     = "rgba(56,189,248,0.25)"
C_BORDER_HOV = "rgba(192,132,252,0.5)"
C_TRANS      = "all 0.3s ease-out"

# Glassmorphism tokens (Neo Glass / Blucap style)
C_GLASS_BG      = "rgba(15, 23, 42, 0.55)"    # translucent backdrop
C_GLASS_BORDER  = "rgba(255, 255, 255, 0.08)"  # subtle white border
C_GLASS_GLOW    = "rgba(56, 189, 248, 0.15)"   # accent glow
C_BLUR_RADIUS   = 24                                  # backdrop blur px
C_CORNER_RADIUS = 16                                  # rounded corners
C_ELEVATION_1   = "0 4px 16px rgba(0,0,0,0.4)"    # shadow depth
C_ELEVATION_2   = "0 8px 32px rgba(0,0,0,0.5)"
C_ELEVATION_3   = "0 16px 48px rgba(0,0,0,0.6)"

# ── Phase 5: Epic Orb + Serpantinum x Caelestia Palette ────────────────────────
# Orb colors (Serpantinum vibrant)
C_ORB_BRIGHT    = "#00d4ff"
C_ORB_BASE      = "#38bdf8"
C_ORB_DARK      = "#0ea5e9"
C_ORB_GLOW_1    = "rgba(56, 189, 248, 0.9)"
C_ORB_GLOW_2    = "rgba(56, 189, 248, 0.6)"
C_ORB_GLOW_3    = "rgba(56, 189, 248, 0.3)"
C_ORB_TALKING   = "#00d4ff"
C_ORB_LEARNING  = "#c084fc"
C_ORB_ERROR     = "#ef4444"
# Backgrounds (Serpantinum dark aesthetic)
C_BG_DARK_0     = "#0a0e27"
C_BG_DARK_1     = "#0f172a"
C_BG_DARK_2     = "#141e3f"
C_BG_GLASS      = "rgba(15, 23, 42, 0.7)"
# Accents (Serpantinum vibrant)
C_ACCENT_CYAN_BRIGHT = "#00d4ff"
C_ACCENT_PURPLE  = "#b066ff"
C_ACCENT_GREEN   = "#00ff88"
C_ACCENT_ORANGE  = "#ff6b4a"
# Text (Caelestia readability)
C_TEXT_PRIMARY   = "#ffffff"
C_TEXT_SECONDARY = "#cbd5e1"
C_TEXT_TERTIARY  = "#94a3b8"
# Global animation timing
C_EASE_MATERIAL = "cubic-bezier(0.4, 0.0, 0.2, 1)"
C_TRANS_FAST     = "all 150ms cubic-bezier(0.4, 0.0, 0.2, 1)"
C_TRANS_NORMAL   = "all 200ms cubic-bezier(0.4, 0.0, 0.2, 1)"
C_TRANS_SLOW     = "all 300ms cubic-bezier(0.4, 0.0, 0.2, 1)"

# ── Liquid Glass 3-Tier + Aspect Palette (viral, Raphael-Ciel style) ──────────
# Tier 1: heavy blur (paneles principales, fondo)
C_GLASS_T1_BG   = "rgba(15, 23, 42, 0.45)"
C_GLASS_T1_BORDER = "rgba(255, 255, 255, 0.06)"
C_GLASS_T1_BLUR  = 60
# Tier 2: medium blur (cards, controles)
C_GLASS_T2_BG   = "rgba(15, 23, 42, 0.35)"
C_GLASS_T2_BORDER = "rgba(255, 255, 255, 0.10)"
C_GLASS_T2_BLUR  = 30
# Tier 3: light blur (acentos, botones activos)
C_GLASS_T3_BG   = "rgba(15, 23, 42, 0.25)"
C_GLASS_T3_BORDER = "rgba(255, 255, 255, 0.14)"
C_GLASS_T3_BLUR  = 16
# XOR border trick (borde que se invierte sobre el fondo)
C_XOR_BORDER    = "rgba(255, 255, 255, 0.16)"
C_XOR_BORDER_GLOW = "rgba(0, 212, 255, 0.35)"

# Aspectos del núcleo (controlan colores del orbe y variables globales)
ASPECT_RGB = {
    "gran_sabio":   (139, 92, 246),   # violet
    "raphael":      (16, 185, 129),   # emerald
    "ciel":         (56, 189, 248),   # cyan
    "fused":        (236, 72, 153),   # rose
}
ASPECT_GLOW = {
    "gran_sabio":   "rgba(139, 92, 246, 0.5)",
    "raphael":      "rgba(16, 185, 129, 0.5)",
    "ciel":         "rgba(56, 189, 248, 0.5)",
    "fused":        "rgba(236, 72, 153, 0.5)",
}
ASPECT_CORE = {
    "gran_sabio":   "#8b5cf6",
    "raphael":      "#10b981",
    "ciel":         "#38bdf8",
    "fused":        "#ec4899",
}

# Colores de fase (idle/thinking/responding/listening)
PHASE_COLORS = {
    "idle":        QColor(56, 189, 248),
    "thinking":    QColor(245, 158, 11),
    "responding":  QColor(0, 212, 255),
    "listening":   QColor(192, 132, 252),
}

# Aspecto activo del núcleo (se mezcla con la fase para el color del orbe)
_ASPECT_ACTIVE = "ciel"


def aspect_color(aspect: str = None, phase: str = None, t: float = 0.4) -> QColor:
    """Mezcla color de aspect con color de fase (interpolación t)."""
    a = _ASPECT_ACTIVE if aspect is None else aspect
    r, g, b = ASPECT_RGB.get(a, ASPECT_RGB["ciel"])
    base = QColor(r, g, b)
    if phase and phase in PHASE_COLORS:
        p = PHASE_COLORS[phase]
        return QColor(
            int(r * (1 - t) + p.red() * t),
            int(g * (1 - t) + p.green() * t),
            int(b * (1 - t) + p.blue() * t),
        )
    return base


def set_aspect(aspect: str):
    global _ASPECT_ACTIVE
    if aspect in ASPECT_RGB:
        _ASPECT_ACTIVE = aspect




# ── Phase 5: Epic Orb + Serpantinum x Caelestia Palette ────────────────────────
# (All palette constants defined above — this section documents the epic orb spec)



# ── Logging ──────────────────────────────────────────────────────────

import logging as _logging

_LOG_DIR = ARIA_APP / "logs"
_LOG_DIR.mkdir(exist_ok=True)

logger = _logging.getLogger("ARIA")
logger.setLevel(_logging.INFO)
_handler = _logging.FileHandler(_LOG_DIR / "aria.log", encoding="utf-8")
_handler.setFormatter(_logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logger.addHandler(_handler)

try:
    _sh = _logging.StreamHandler()
    _sh.setFormatter(_logging.Formatter("[%(levelname)s] %(message)s"))
    logger.addHandler(_sh)
except Exception:
    pass


# ── Núcleo VA local (100% en proceso, sin HTTP, sin subprocess) ──────────────

sys.path.insert(0, str(ARIA_APP))
from aria_va_core import get_va, VirtualAssistant


class VAAdapter:
    """Adaptador síncrono al núcleo VA local. Reemplaza a IPCClient."""

    def __init__(self) -> None:
        self.va = get_va()
        self.healthy = True

    def send(self, request: dict) -> dict:
        req_type = request.get("type", "")
        if req_type == "chat":
            text = request.get("data", {}).get("message", "")
            response = self.va.process_text(text)
            return {"status": "ok", "response": response, "provider": "local", "source": "va"}
        if req_type == "list_skills":
            skills = self.va.skills.list()
            return {"status": "ok", "skills": skills, "count": len(skills)}
        if req_type == "skill":
            skill_id = request.get("skill", "")
            params = request.get("data", {}).get("params", {})
            result = self.va.skills.run(skill_id, params)
            return {"status": "ok", "result": result}
        if req_type == "status":
            return {"status": "ok", **self.va.get_status()}
        if req_type == "ping":
            return {"status": "ok", "type": "pong"}
        if req_type == "voice_speak":
            text = request.get("data", {}).get("text", "")
            self.va.speak(text)
            return {"status": "ok"}
        if req_type == "voice_start":
            self.va.start_voice_listening()
            return {"status": "ok"}
        if req_type == "voice_stop":
            self.va.stop_voice_listening()
            return {"status": "ok"}
        if req_type == "autonomous_toggle":
            params = request.get("data", {})
            enable = bool(params.get("enable", not self.va.autonomous))
            if enable:
                self.va.start_autonomous()
            else:
                self.va.stop_autonomous()
            return {"status": "ok", "autonomous": self.va.autonomous}
        return {"status": "error", "error": f"tipo desconocido: {req_type}"}

    def stop(self) -> None:
        self.va.stop_voice_listening()


# ── Logging ──────────────────────────────────────────────────────────


# ── Orb Visual Widget ──────────────────────────────────────────────────────

import math as _math

class OrbWidget(QWidget):
    """Epic 9-layer orb: pulse rings, outer halo, orbit ring, evolution rings,
    fractal eye, core glow, solid sphere, burst rays, infon particles.
    Colores mezclan aspect activo + fase actual (idle/thinking/responding/listening)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(220, 220)
        self._phase = 0.0
        self._state = "idle"
        self._blink_phase = 0.0
        self._particles = []
        self._orbit_particles = []
        self._burst_rays = []
        self._pulse_ring_phase = 0.0
        self._orbit_angle = 0.0
        self._evo_ring_phases = [0.0, 0.0, 0.0, 0.0, 0.0]
        self._color = aspect_color("ciel", "idle")
        self._glow_color = QColor(56, 189, 248, 180)
        self._aspect = "ciel"
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_orb)
        self._timer.start(30)

    def set_aspect(self, aspect: str):
        self._aspect = aspect
        self._color = aspect_color(aspect, self._state)
        self.update()

    def set_state(self, state: str):
        self._state = state
        self._color = aspect_color(self._aspect, state)
        glows = {
            "idle": QColor(56, 189, 248, 180),
            "thinking": QColor(245, 158, 11, 180),
            "responding": QColor(0, 212, 255, 180),
            "listening": QColor(192, 132, 252, 180),
        }
        base = ASPECT_RGB.get(self._aspect, ASPECT_RGB["ciel"])
        self._glow_color = QColor(base[0], base[1], base[2], 180)
        if not hasattr(self, '_glow_transition'):
            self._glow_transition = 0.0
            self._glow_timer = QTimer(self)
            self._glow_timer.timeout.connect(self._animate_glow)
            self._glow_timer.start(30)
        self._glow_transition = 1.0

    def _animate_glow(self):
        self._glow_transition = max(0.0, self._glow_transition - 0.05)
        self.update()

    def _update_orb(self):
        self._phase += 0.03
        self._blink_phase += 0.05
        self._pulse_ring_phase = (self._pulse_ring_phase + 0.02) % 1.0
        self._orbit_angle = (self._orbit_angle + 0.04) % 6.283
        for i in range(len(self._evo_ring_phases)):
            self._evo_ring_phases[i] = (self._evo_ring_phases[i] + 0.015 * (i + 1)) % 6.283
        import random as _rnd
        if self._state in ("responding", "listening") and len(self._orbit_particles) < 14:
            self._orbit_particles.append({
                "angle": _rnd.uniform(0, 6.283), "r": 38,
                "life": 1.0, "speed": _rnd.uniform(0.015, 0.035)
            })
        if self._state in ("responding", "thinking") and len(self._burst_rays) < 18:
            for _ in range(3):
                self._burst_rays.append({
                    "angle": _rnd.uniform(0, 6.283),
                    "length": _rnd.uniform(12, 34),
                    "life": 1.0
                })
        for p in self._orbit_particles[:]:
            p["angle"] += p["speed"]
            p["life"] -= 0.005
            if p["life"] <= 0:
                self._orbit_particles.remove(p)
        for b in self._burst_rays[:]:
            b["life"] -= 0.03
            b["length"] += 2
            if b["life"] <= 0:
                self._burst_rays.remove(b)
        if self._state in ("responding", "listening") and len(self._particles) < 24:
            self._particles.append({
                "x": _rnd.uniform(0, 220), "y": _rnd.uniform(0, 220),
                "life": 1.0, "speed": _rnd.uniform(0.25, 0.65)
            })
        for p in self._particles[:]:
            p["life"] -= p["speed"] * 0.02
            p["y"] -= p["speed"]
            if p["life"] <= 0:
                self._particles.remove(p)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        w, h = self.width(), self.height()
        cx, cy = w // 2, h // 2
        base_r = min(w, h) * 0.26

        if self._state == "listening":
            breath = 1.0 + 0.16 * ((1 + _math.sin(self._phase * 2)) / 2)
        elif self._state == "responding":
            breath = 1.0 + 0.13 * ((1 + _math.sin(self._phase * 3)) / 2)
        elif self._state == "thinking":
            breath = 1.0 + 0.09 * ((1 + _math.sin(self._phase * 1.5)) / 2)
        else:
            breath = 1.0 + 0.11 * ((1 + _math.sin(self._phase)) / 2)

        r = int(base_r * breath)
        painter.setPen(Qt.NoPen)
        col = self._color

        # ── Layer 9: Outer Halo (respiración 12s, blur visual grande) ──
        halo_r = r + 62
        halo_alpha = int(30 + 25 * ((1 + _math.sin(self._phase * 0.5)) / 2))
        painter.setBrush(QBrush(QColor(col.red(), col.green(), col.blue(), halo_alpha)))
        painter.drawEllipse(cx - halo_r, cy - halo_r, halo_r*2, halo_r*2)

        # ── Layer 8: Pulse Rings (expansión outward, 2 capas) ──
        for i, pr in enumerate([self._pulse_ring_phase, (self._pulse_ring_phase + 0.5) % 1.0]):
            pulse_r = int(r + 55 * pr)
            pulse_alpha = max(0, int(45 * (1.0 - pr)))
            painter.setBrush(QBrush(QColor(col.red(), col.green(), col.blue(), pulse_alpha)))
            painter.drawEllipse(cx - pulse_r, cy - pulse_r, pulse_r*2, pulse_r*2)

        # ── Layer 7: Evolution Rings (5 anillos concéntricos rotativos) ──
        for i in range(5):
            er = int(r + 14 + i * 10)
            ea = int(60 + 20 * _math.sin(self._evo_ring_phases[i]))
            painter.setPen(QPen(QColor(col.red(), col.green(), col.blue(), ea), 1))
            painter.setBrush(Qt.NoBrush)
            painter.save()
            painter.translate(cx, cy)
            painter.rotate(self._evo_ring_phases[i] * 57.3)
            painter.drawEllipse(-er, -er, er*2, er*2)
            painter.restore()

        # ── Layer 6: Orbit Ring (rotando) ──
        painter.setPen(QPen(QColor(col.red(), col.green(), col.blue(), 150), 2))
        painter.setBrush(Qt.NoBrush)
        painter.save()
        painter.translate(cx, cy)
        painter.rotate(self._orbit_angle * 57.3)
        painter.drawEllipse(-38, -38, 76, 76)
        painter.restore()

        # ── Layer 5: Orbit Particles ──
        for p in self._orbit_particles:
            px = cx + 38 * _math.cos(p["angle"])
            py = cy + 38 * _math.sin(p["angle"])
            p_alpha = max(0, int(220 * p["life"]))
            painter.setBrush(QBrush(QColor(0, 212, 255, p_alpha)))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(int(px) - 2, int(py) - 2, 4, 4)

        # ── Layer 4: Core Glow (respiración 1.5s) ──
        glow_r = r + 14
        core_alpha = int(110 + 45 * ((1 + _math.sin(self._phase * 4)) / 2))
        painter.setBrush(QBrush(QColor(col.red(), col.green(), col.blue(), core_alpha)))
        painter.drawEllipse(cx - glow_r, cy - glow_r, glow_r*2, glow_r*2)

        # ── Layer 3: Solid Sphere (gradiente radial, aspect-core) ──
        gradient = QRadialGradient(cx, cy, 0, cx, cy, r)
        gradient.setColorAt(0, QColor(255, 255, 255, 230))
        gradient.setColorAt(0.35, QColor(col.red(), col.green(), col.blue(), 255))
        gradient.setColorAt(0.7, col)
        gradient.setColorAt(1, QColor(max(0, col.red()-40), max(0, col.green()-40), max(0, col.blue()-40)))
        painter.setBrush(QBrush(gradient))
        painter.drawEllipse(cx - r, cy - r, r*2, r*2)

        # ── Layer 2: Burst Rays (interacción) ──
        for b in self._burst_rays:
            bx = int(cx + _math.cos(b["angle"]) * r)
            by = int(cy + _math.sin(b["angle"]) * r)
            ex = int(cx + _math.cos(b["angle"]) * (r + b["length"]))
            ey = int(cy + _math.sin(b["angle"]) * (r + b["length"]))
            b_alpha = max(0, int(200 * b["life"]))
            painter.setPen(QPen(QColor(0, 212, 255, b_alpha), 2))
            painter.setBrush(Qt.NoBrush)
            painter.drawLine(bx, by, ex, ey)

        painter.setOpacity(1.0)

        # ── Layer 1: Fractal Eye (parpadeo en listening) ──
        if self._state == "listening":
            blink = _math.sin(self._blink_phase)
            eye_h = max(1, int(r * 0.20 * (1 - abs(blink))))
            eye_y = cy - r//4
            painter.setBrush(QBrush(QColor(5, 8, 22, 230)))
            painter.drawRoundedRect(cx - r//3, eye_y - eye_h//2, r//3*2, eye_h, r//6, r//6)
            painter.setBrush(QBrush(QColor(255, 255, 255, 210)))
            painter.drawEllipse(cx - r//6, eye_y - 2, 4, 4)
            painter.drawEllipse(cx + r//6 - 4, eye_y - 2, 4, 4)

        # Infon particles con fade
        for p in self._particles:
            painter.setOpacity(max(0, p["life"]))
            painter.setBrush(QBrush(col))
            painter.drawEllipse(int(p["x"]), int(p["y"]), 3, 3)
        painter.setOpacity(1.0)

        # Inner highlight sutil
        painter.setBrush(QBrush(QColor(255, 255, 255, 45)))
        painter.drawEllipse(cx - r//3, cy - r//3 - r//4, r//2, r//3)

        painter.end()


# ── Chat Window ─────────────────────────────────────────────────────────────

class ChatWindow(QMainWindow):
    response_received = pyqtSignal(dict)

    def __init__(self, va: VAAdapter):
        super().__init__()
        self.va = va
        self._setup_ui()
        self._setup_keyboard_shortcuts()
        self._load_settings()
        self._performance_monitor()

    def _setup_ui(self):
        self.setWindowTitle("ARIA OS v4.0")
        self.setFixedSize(620, 720)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.WindowDoesNotAcceptFocus)
        self._old_pos = None
        self._dragging = False
        # Position centered on primary screen
        from PyQt5.QtWidgets import QApplication
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(screen.width() // 2 - 310, 100)

        central = QWidget()
        central.setStyleSheet(f"""
            QWidget {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 {C_BG_DARK_0}, stop:0.5 {C_BG_DARK_1}, stop:1 #050816); }}
            QPushButton {{
                background: {C_GLASS_T3_BG};
                color: {C_TEXT_PRIMARY}; border: 1px solid {C_GLASS_T3_BORDER}; border-radius: 8px;
                padding: 8px 16px; font-weight: bold; font-size: 12px;
                box-shadow: 0 0 14px {C_GLASS_T3_BORDER};
                transition: {C_TRANS_NORMAL};
            }}
            QPushButton:hover {{
                border-color: {C_ACCENT_CYAN_BRIGHT};
                box-shadow: 0 0 20px {C_ACCENT_CYAN_BRIGHT}40;
                background: {C_GLASS_T2_BG};
                transform: translateY(-1px);
            }}
            QPushButton:pressed {{
                transform: scale(0.97);
            }}
            QLineEdit {{
                background: {C_GLASS_T2_BG}; color: {C_TEXT_SECONDARY};
                border: 1px solid {C_GLASS_T2_BORDER}; border-radius: 8px;
                padding: 10px; font-size: 13px; font-family: 'Consolas', monospace;
                box-shadow: 0 0 10px rgba(0,0,0,0.4);
                transition: {C_TRANS_NORMAL};
            }}
            QLineEdit:focus {{
                border-color: {C_ACCENT_CYAN_BRIGHT};
                box-shadow: 0 0 16px {C_ACCENT_CYAN_BRIGHT}40;
                background: {C_GLASS_T1_BG};
            }}
            QTextEdit {{
                background: {C_GLASS_T1_BG};
                color: {C_TEXT_SECONDARY};
                border: 1px solid {C_GLASS_T1_BORDER};
                border-radius: 12px;
                padding: 12px;
                font-size: 12px;
                font-family: 'Consolas', monospace;
                box-shadow: 0 0 14px rgba(0,0,0,0.5);
                transition: {C_TRANS_NORMAL};
            }}
            QTextEdit:focus {{
                border-color: {C_ACCENT_CYAN_BRIGHT};
                box-shadow: 0 0 20px {C_ACCENT_CYAN_BRIGHT}40;
            }}
            QLabel {{ font-family: 'Segoe UI'; color: {C_TEXT_SECONDARY}; }}
        """)
        # Glassmorphism: apply blur only to the skills sidebar background panel
        # (not the central widget — that would blur all text too)
        self.setCentralWidget(central)

        layout = QVBoxLayout(central)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        # Header bar (Serpantinum style)
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        # Logo glyph
        logo = QLabel("◆")
        logo.setStyleSheet(f"color: {C_ACCENT_CYAN_BRIGHT}; font-size: 20px; font-weight: bold; text-shadow: 0 0 8px rgba(0,212,255,0.6);")
        header.addSpacing(4)
        header.addWidget(logo)
        title = QLabel("ARIA OS v4.0")
        title.setStyleSheet(f"color: {C_TEXT_PRIMARY}; font-size: 14px; font-weight: bold; font-family: 'Segoe UI'; letter-spacing: 1px;")
        header.addSpacing(4)
        header.addWidget(title)
        # Status indicator
        self.status_dot = QLabel("●")
        self.status_dot.setStyleSheet(f"color: {C_SUCCESS}; font-size: 10px;")
        header.addWidget(self.status_dot)
        self.status_label = QLabel("Listo")
        self.status_label.setStyleSheet(f"color: {C_TEXT_SECONDARY}; font-size: 11px; font-family: 'Segoe UI';")
        header.addWidget(self.status_label)
        header.addStretch()
        # Theme selector button (Serpantinum style)
        self.theme_btn = QPushButton("🎨")
        self.theme_btn.setFixedSize(28, 28)
        self.theme_btn.setToolTip("Cambiar tema (Ctrl+T)")
        self.theme_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(15, 23, 42, 0.6);
                color: {C_ACCENT_PURPLE};
                border: 1px solid rgba(176, 102, 255, 0.3);
                border-radius: 8px;
                font-size: 14px;
                transition: {C_TRANS_NORMAL};
            }}
            QPushButton:hover {{
                background: rgba(176, 102, 255, 0.2);
                border-color: {C_ACCENT_PURPLE};
                box-shadow: 0 0 12px rgba(176,102,255,0.4);
                transform: scale(1.1);
            }}
            QPushButton:active {{
                transform: scale(0.95);
                background: rgba(176, 102, 255, 0.3);
            }}
        """)
        self.theme_btn.clicked.connect(self._open_theme_picker)
        header.addWidget(self.theme_btn)
        # Control center button (Caelestia style)
        self.control_btn = QPushButton("⚙")
        self.control_btn.setFixedSize(28, 28)
        self.control_btn.setToolTip("Control Center (Ctrl+,)")
        self.control_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(15, 23, 42, 0.6);
                color: {C_ACCENT_CYAN_BRIGHT};
                border: 1px solid rgba(0, 212, 255, 0.3);
                border-radius: 8px;
                font-size: 14px;
                transition: {C_TRANS_NORMAL};
            }}
            QPushButton:hover {{
                background: rgba(0, 212, 255, 0.2);
                border-color: {C_ACCENT_CYAN_BRIGHT};
                box-shadow: 0 0 12px rgba(0,212,255,0.4);
                transform: scale(1.1);
            }}
            QPushButton:active {{
                transform: scale(0.95);
                background: rgba(0, 212, 255, 0.3);
            }}
        """)
        self.control_btn.clicked.connect(self._open_control_center)
        header.addWidget(self.control_btn)
        # Botón Núcleo/Evolución
        self.nucleus_btn = QPushButton("☉ Núcleo")
        self.nucleus_btn.setFixedSize(34, 34)
        self.nucleus_btn.setToolTip("Abrir panel de evolución y sacrifice (Ctrl+N)")
        self.nucleus_btn.setStyleSheet(f"""
            QPushButton {{
                background: {C_GLASS_T3_BG};
                color: {C_ACCENT_CYAN_BRIGHT};
                border: 1px solid {C_GLASS_T3_BORDER};
                border-radius: 10px;
                font-size: 13px;
                font-weight: bold;
                transition: {C_TRANS_NORMAL};
            }}
            QPushButton:hover {{
                background: {C_ACCENT_CYAN_BRIGHT}20;
                border-color: {C_ACCENT_CYAN_BRIGHT};
                box-shadow: 0 0 14px {C_ACCENT_CYAN_BRIGHT}50;
            }}
            QPushButton:pressed {{ transform: scale(0.95); }}
        """)
        self.nucleus_btn.clicked.connect(self._open_nucleus)
        header.addWidget(self.nucleus_btn)
        min_btn = QPushButton("_")
        min_btn.setFixedSize(26, 26)
        min_btn.setStyleSheet(f"background: rgba(15, 23, 42, 0.6); color: {C_TEXT_TERTIARY}; font-size: 14px; font-weight: bold; border-radius: 6px; border: 1px solid {C_GLASS_BORDER}; transition: {C_TRANS_NORMAL};")
        min_btn.clicked.connect(self.showMinimized)
        header.addWidget(min_btn)
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(26, 26)
        close_btn.setStyleSheet(f"background: rgba(15, 23, 42, 0.6); color: {C_TEXT_TERTIARY}; font-size: 14px; border-radius: 6px; border: 1px solid {C_GLASS_BORDER}; transition: {C_TRANS_NORMAL};")
        close_btn.clicked.connect(self.close)
        header.addWidget(close_btn)
        help_btn = QPushButton("?")
        help_btn.setFixedSize(26, 26)
        help_btn.setToolTip("Atajos de teclado (F1)")
        help_btn.setStyleSheet(f"background: rgba(15, 23, 42, 0.6); color: {C_TEXT_TERTIARY}; font-size: 14px; border-radius: 6px; border: 1px solid {C_GLASS_BORDER}; transition: {C_TRANS_NORMAL};")
        help_btn.clicked.connect(self._show_shortcuts)
        header.addWidget(help_btn)
        layout.addLayout(header)

        # Orb
        self.orb = OrbWidget()
        layout.addSpacing(4)
        layout.addWidget(self.orb, alignment=Qt.AlignCenter)

        # Status label
        self.status_label = QLabel("● Inactivo")
        self.status_label.setStyleSheet(f"color: {C_TEXT_DIM}; font-size: 11px; text-align: center; font-family: 'Segoe UI';")
        layout.addWidget(self.status_label)

        layout.addSpacing(8)

        # Chat history with smooth scroll + border glow
        self.chat_history = QTextEdit()
        self.chat_history.setReadOnly(True)
        self.chat_history.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.chat_history.setMaximumHeight(330)
        self.chat_history.setPlaceholderText("Escribe tu mensaje a ARIA...")
        self.chat_history.verticalScrollBar().setSingleStep(16)
        self.chat_history.verticalScrollBar().setPageStep(80)
        layout.addWidget(self.chat_history)

        # Input row (Serpantinum style)
        input_row = QHBoxLayout()
        input_row.setContentsMargins(0, 0, 0, 0)
        self.msg_input = QLineEdit()
        self.msg_input.setPlaceholderText("Escribe y pulsa Enter...")
        self.msg_input.setFixedHeight(40)
        self.msg_input.returnPressed.connect(self._send_message)
        input_row.addWidget(self.msg_input)
        send_btn = QPushButton("▲ Enviar")
        send_btn.setFixedWidth(90)
        send_btn.setFixedHeight(40)
        send_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {C_ACCENT_CYAN_BRIGHT}, stop:1 {C_ACCENT_PURPLE});
                color: #0f172a; border: none; border-radius: 8px;
                font-weight: bold; font-size: 12px; font-family: 'Consolas', monospace;
                transition: {C_TRANS_NORMAL};
                box-shadow: 0 4px 12px rgba(0, 212, 255, 0.3);
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #7dd3fc, stop:1 #a855f7);
                box-shadow: 0 6px 20px rgba(0, 212, 255, 0.4);
                transform: translateY(-2px);
            }}
            QPushButton:active {{
                transform: scale(0.95);
                box-shadow: 0 2px 8px rgba(0, 212, 255, 0.3);
            }}
        """)
        send_btn.clicked.connect(self._send_message)
        input_row.addWidget(send_btn)
        # Quick action buttons (Fase 4: micro-details)
        clear_btn = QPushButton("✕ Limpiar")
        clear_btn.setFixedWidth(70)
        clear_btn.setFixedHeight(36)
        clear_btn.setStyleSheet(f"QPushButton {{ background: rgba(15, 23, 42, 0.6); color: {C_TEXT_TERTIARY}; border: 1px solid {C_GLASS_BORDER}; border-radius: 6px; font-size: 10px; font-family: Consolas, monospace; transition: {C_TRANS_NORMAL}; }} QPushButton:hover {{ background: rgba(239, 68, 68, 0.3); color: #fca5a5; border-color: #ef4444; }}")
        clear_btn.clicked.connect(self._clear_chat)
        input_row.addWidget(clear_btn)
        export_btn = QPushButton("↓ Exportar")
        export_btn.setFixedWidth(70)
        export_btn.setFixedHeight(36)
        export_btn.setStyleSheet(f"QPushButton {{ background: rgba(15, 23, 42, 0.6); color: {C_TEXT_TERTIARY}; border: 1px solid {C_GLASS_BORDER}; border-radius: 6px; font-size: 10px; font-family: Consolas, monospace; transition: {C_TRANS_NORMAL}; }} QPushButton:hover {{ background: rgba(56, 189, 248, 0.3); color: {C_ACCENT_CYAN_BRIGHT}; border-color: {C_ACCENT_CYAN_BRIGHT}; }}")
        export_btn.clicked.connect(self._export_chat)
        input_row.addWidget(export_btn)
        layout.addLayout(input_row)

        # Skills dock sidebar (left side, scrollable)
        self.skills_sidebar = self._build_skills_sidebar()
        layout.addWidget(self.skills_sidebar)

    def _build_skills_sidebar(self):
        """Dock-style skills sidebar with glassmorphism, hover glow, click animation."""
        container = QWidget()
        container.setFixedWidth(150)
        container.setStyleSheet(f"""
            QWidget {{ background: {C_GLASS_T1_BG}; border-right: 1px solid {C_GLASS_T1_BORDER}; }}
        """)
        v = QVBoxLayout(container)
        v.setContentsMargins(10, 10, 10, 10)
        v.setSpacing(6)

        lbl = QLabel("◇ Skills")
        lbl.setStyleSheet(f"color: {C_ACCENT_CYAN_BRIGHT}; font-size: 12px; font-weight: bold; font-family: 'Segoe UI'; letter-spacing: 1px; padding-bottom: 4px; border-bottom: 1px solid rgba(56, 189, 248, 0.1);")
        v.addWidget(lbl)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet(f"QScrollArea {{ background: transparent; }} QScrollBar::vertical {{ width: 6px; background: transparent; }} QScrollBar::handle {{ background: {C_ACCENT_CYAN_BRIGHT}; border-radius: 3px; }}")

        self.skills_grid = QWidget()
        self.skills_grid_layout = QVBoxLayout(self.skills_grid)
        self.skills_grid_layout.setSpacing(4)
        scroll.setWidget(self.skills_grid)
        v.addWidget(scroll)
        return container

    def _add_skill_btn(self, name: str, category: str):
        """Add a glassmorphism skill button with hover glow + click animation."""
        btn = QPushButton(f"◆ {name}")
        btn.setFixedHeight(30)
        btn.setCheckable(True)
        btn.setStyleSheet(f"""
            QPushButton {{
                background: {C_GLASS_T2_BG};
                color: {C_TEXT_TERTIARY};
                border: 1px solid {C_GLASS_T2_BORDER};
                border-radius: 10px;
                padding: 4px 10px;
                font-size: 11px;
                font-family: 'Consolas', monospace;
                text-align: left;
                transition: {C_TRANS_NORMAL};
            }}
            QPushButton:hover {{
                background: {C_GLASS_T3_BG};
                color: {C_TEXT_PRIMARY};
                border-color: {C_ACCENT_PURPLE};
                box-shadow: 0 0 14px {C_ACCENT_PURPLE}40;
                transform: translateX(2px);
            }}
            QPushButton:active {{
                transform: scale(0.98);
            }}
            QPushButton:checked {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(56, 189, 248, 0.45), stop:1 rgba(176, 102, 255, 0.35));
                color: {C_TEXT_PRIMARY};
                border-color: {C_ACCENT_CYAN_BRIGHT};
                box-shadow: 0 0 18px {C_ACCENT_CYAN_BRIGHT}60;
            }}
        """)
        btn.clicked.connect(lambda: self._on_skill_click(btn, name, category))
        self.skills_grid_layout.addWidget(btn)
        return btn

    def _on_skill_click(self, btn: QPushButton, name: str, category: str):
        """Click animation: icon pulse + color change."""
        btn.setChecked(True)
        # Visual feedback: flash effect via stylesheet override
        btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {C_SUCCESS}, stop:1 {C_ACCENT});
                color: white;
                border: 1px solid {C_ACCENT};
                border-radius: 14px;
                padding: 4px 10px;
                font-size: 10px;
                font-family: 'Consolas', monospace;
            }}
        """)
        # Reset after 500ms
        QTimer.singleShot(500, lambda: btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {C_ACCENT}, stop:1 {C_SECONDARY});
                color: white;
                border-color: {C_SECONDARY};
                border-radius: 14px;
                padding: 4px 10px;
                font-size: 10px;
                font-family: 'Consolas', monospace;
            }}
            QPushButton:!checked {{
                background: rgba(30, 41, 59, 0.8);
                color: {C_TEXT_DIM};
                border: 1px solid {C_BORDER};
            }}
        """))

    def _send_message(self):
        text = self.msg_input.text().strip()
        if not text:
            return
        self.msg_input.clear()
        self._append_chat("Tú", text, "#38bdf8")
        self.orb.set_state("thinking")
        self.status_label.setText("● Pensando...")
        self.status_label.setStyleSheet("color: #f59e0b; font-size: 11px;")

        def _async_chat():
            request = {"type": "chat", "id": str(int(time.time()*1000)),
                       "data": {"message": text}}
            result = self.va.send(request)
            self.response_received.emit(result if result else {"status": "error", "error": "sin respuesta"})

        threading.Thread(target=_async_chat, daemon=True).start()


    def _render_markdown(self, text: str) -> str:
        """Convert basic markdown to HTML for chat display."""
        import re
        # Escape HTML first
        t = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        # Code blocks ```...```
        t = re.sub(r'```(\w*)\n?(.*?)```', r'<pre style="background:rgba(30,41,59,0.9); padding:8px; border-radius:6px; overflow-x:auto; font-size:10px; color:#7dd3fc;"><code>\2</code></pre>', t, flags=re.DOTALL)
        # Inline code `...`
        t = re.sub(r'`([^`]+)`', r'<code style="background:rgba(30,41,59,0.7); padding:1px 4px; border-radius:3px; color:#7dd3fc;">\1</code>', t)
        # Bold **...**
        t = re.sub(r'\*\*(.+?)\*\*', r'<b style="color:' + C_TEXT_MAIN + ';">\1</b>', t)
        # Italic *...*
        t = re.sub(r'\*(.+?)\*', r'<i style="color:' + C_TEXT_DIM + ';">\1</i>', t)
        # Headers # ... / ## ...
        t = re.sub(r'^### (.+)', r'<div style="font-size:13px; font-weight:bold; color:' + C_ACCENT + '; margin:8px 0 4px;">\1</div>', t, flags=re.MULTILINE)
        t = re.sub(r'^## (.+)', r'<div style="font-size:14px; font-weight:bold; color:' + C_SECONDARY + '; margin:8px 0 4px;">\1</div>', t, flags=re.MULTILINE)
        t = re.sub(r'^# (.+)', r'<div style="font-size:16px; font-weight:bold; color:' + C_ACCENT + '; margin:10px 0 6px;">\1</div>', t, flags=re.MULTILINE)
        # Bullet list - item
        t = re.sub(r'^- (.+)', r'<div style="margin:2px 0 2px 8px;">• \1</div>', t, flags=re.MULTILINE)
        # Numbered list
        t = re.sub(r'^(\d+)\. (.+)', r'<div style="margin:2px 0 2px 8px;">\1. \2</div>', t, flags=re.MULTILINE)
        # Links [text](url)
        t = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2" style="color:' + C_ACCENT + '; text-decoration:underline;">\1</a>', t)
        # Blockquote > text
        t = re.sub(r'^&gt; (.+)', r'<div style="border-left:3px solid ' + C_ACCENT + '; padding:2px 8px; margin:4px 0; color:' + C_TEXT_DIM + '; font-style:italic;">\1</div>', t, flags=re.MULTILINE)
        # Normalize newlines to <br>
        t = t.replace('\n', '<br>')
        return t

    def _append_chat(self, sender: str, text: str, color: str = C_ACCENT_CYAN_BRIGHT):
        """Append a chat message to the history with HTML formatting."""
        from datetime import datetime
        ts = datetime.now().strftime("%H:%M")
        # Render markdown if it's from ARIA
        if sender == "ARIA":
            text = self._render_markdown(text)
        else:
            text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        border_glow = "0 0 8px " + color + "40" if sender != "Tú" else "none"
        align = "flex-end" if sender == "Tú" else "flex-start"
        bg = "rgba(56, 189, 248, 0.15)" if sender == "Tú" else "rgba(15, 23, 42, 0.5)"
        self.chat_history.append(
            "<div style='margin:6px 0; display:flex; justify-content:" + align + ";'>"
            "<div style='max-width:75%; padding:10px 12px; border-radius:12px; "
            "background:" + bg + "; border-left:3px solid " + color + "; "
            "box-shadow:" + border_glow + ";'>"
            "<span style='color:" + color + "; font-weight:bold; font-family:Consolas,monospace;'>" + sender + "</span> "
            "<span style='color:" + C_TEXT_DIM + "; font-size:9px; font-family:Consolas,monospace;'>[" + ts + "]</span>"
            "<br><span style='color:" + C_TEXT_MAIN + "; font-family:Consolas,monospace; font-size:11px; line-height:1.5;'>" + text + "</span>"
            "</div></div>"
        )
        scrollbar = self.chat_history.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _show_skeleton(self, sender: str, meta: str = ""):
        """Animated skeleton placeholder while response is being generated."""
        from datetime import datetime
        ts = datetime.now().strftime("%H:%M")
        meta_html = ""
        if meta:
            meta_html = ' <span style="color:' + C_ACCENT + '; font-size:9px; font-family:Consolas,monospace;">' + meta + '</span>'
        # Skeleton bars with animated pulse
        self.chat_history.append(
            "<div id='skeleton_" + str(int(time.time()*1000)) + "' style='margin:6px 0; padding:8px 10px; "
            "background:rgba(15,23,42,0.5); border-left:3px solid " + C_ACCENT + "; border-radius:4px; "
            "box-shadow:0 0 8px rgba(56,189,248,0.2);'>"
            "<span style='color:" + C_ACCENT + "; font-weight:bold; font-family:Consolas,monospace;'>ARIA</span> "
            "<span style='color:" + C_TEXT_DIM + "; font-size:9px; font-family:Consolas,monospace;'>[" + ts + "]</span>"
            + meta_html +
            "<br><div style='margin-top:6px;'>"
            "<div class='skel-bar' style='height:8px; width:80%; background:linear-gradient(90deg, rgba(56,189,248,0.15), rgba(56,189,248,0.4), rgba(56,189,248,0.15)); border-radius:4px; margin:4px 0; animation:skelPulse 1.2s ease-in-out infinite;'></div>"
            "<div class='skel-bar' style='height:8px; width:60%; background:linear-gradient(90deg, rgba(56,189,248,0.15), rgba(56,189,248,0.4), rgba(56,189,248,0.15)); border-radius:4px; margin:4px 0; animation:skelPulse 1.2s ease-in-out infinite;'></div>"
            "<div class='skel-bar' style='height:8px; width:45%; background:linear-gradient(90deg, rgba(56,189,248,0.15), rgba(56,189,248,0.4), rgba(56,189,248,0.15)); border-radius:4px; margin:4px 0; animation:skelPulse 1.2s ease-in-out infinite;'></div>"
            "</div></div>"
            "<style>"
            "@keyframes skelPulse { 0% { opacity:0.4; } 50% { opacity:0.9; } 100% { opacity:0.4; } }"
            "</style>"
        )
        scrollbar = self.chat_history.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _add_action_buttons(self, response_text: str):
        """Add Copiar / Guardar / Refine action buttons below last ARIA message."""
        # Remove previous action bar if any
        prev = self.chat_history.find("#action_bar")
        if prev:
            # Clear the action bar by replacing with empty
            self.chat_history.setHtml(self.chat_history.toHtml().replace(
                "<div id='action_bar' style='margin:4px 0; padding:4px;'>",
                "<div id='action_bar' style='margin:4px 0; padding:4px; display:none;'>"
            ))
        btn_html = (
            "<div id='action_bar' style='margin:6px 0; padding:6px 8px; "
            "background:rgba(15,23,42,0.6); border-radius:8px; border:1px solid " + C_GLASS_BORDER + ";'>"
            "<span style='color:" + C_TEXT_DIM + "; font-size:9px; font-family:Consolas,monospace; margin-right:8px;'>Acciones:</span>"
            "<button id='act_copy' style='background:" + C_ACCENT + "; color:#0f172a; border:none; border-radius:4px; padding:3px 8px; font-size:9px; font-family:Consolas,monospace; cursor:pointer; margin-right:4px;'>Copiar</button>"
            "<button id='act_save' style='background:" + C_SECONDARY + "; color:#0f172a; border:none; border-radius:4px; padding:3px 8px; font-size:9px; font-family:Consolas,monospace; cursor:pointer; margin-right:4px;'>Guardar</button>"
            "<button id='act_refine' style='background:rgba(56,189,248,0.2); color:" + C_ACCENT + "; border:1px solid " + C_ACCENT + "; border-radius:4px; padding:3px 8px; font-size:9px; font-family:Consolas,monospace; cursor:pointer;'>Refine</button>"
            "</div>"
        )
        self.chat_history.append(btn_html)
        # Wire button clicks via JavaScript evaluation
        self.chat_history.page().profile().setLinkDelegationPolicy(True)
        # Use JavaScript to handle clicks
        js = (
            "var btns = document.querySelectorAll('#action_bar button');"
            "btns[0].onclick = function() { navigator.clipboard.writeText('" + response_text.replace("'", "\\'") + "'); };"
            "btns[1].onclick = function() { var blob = new Blob(['" + response_text.replace("'", "\\'") + "'], {type:'text/plain'}); var url = URL.createObjectURL(blob); var a=document.createElement('a'); a.href=url; a.download='ARIA_response.txt'; a.click(); };"
            "btns[2].onclick = function() { window.prompt('Solicitar refine:', '" + response_text.replace("'", "\\'") + "'); };"
        )
        self.chat_history.page().evaluateJavaScript(js)
        scrollbar = self.chat_history.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _append_streaming(self, sender: str, full_text: str, color: str, meta: str = ""):
        """Stream text token-by-token for a typing effect."""
        from datetime import datetime
        ts = datetime.now().strftime("%H:%M")
        border_glow = "0 0 8px " + color + "40" if sender != "Tú" else "none"
        meta_html = ""
        if meta:
            meta_html = ' <span style="color:' + C_ACCENT + '; font-size:9px; font-family:Consolas,monospace;">' + meta + '</span>'
        # Insert placeholder div with id for streaming
        self.chat_history.append(
            "<div id='stream_" + str(int(time.time()*1000)) + "' style='margin:6px 0; padding:6px 10px; "
            "background:rgba(15,23,42,0.5); border-left:3px solid " + color + "; border-radius:4px; "
            "box-shadow:" + border_glow + ";'>"
            "<span style='color:" + color + "; font-weight:bold; font-family:Consolas,monospace;'>" + sender + "</span> "
            "<span style='color:" + C_TEXT_DIM + "; font-size:9px; font-family:Consolas,monospace;'>[" + ts + "]</span>"
            + meta_html +
            "<br><span id='stream_text' style='color:" + C_TEXT_MAIN + "; font-family:Consolas,monospace; font-size:11px;'></span></div>"
        )
        # Stream characters in chunks using QTimer
        chunk_size = max(1, len(full_text) // 40)  # ~40 steps
        pos = [0]
        def _step():
            pos[0] = min(len(full_text), pos[0] + chunk_size)
            escaped = full_text[:pos[0]].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
            self.chat_history.setHtml(
                self.chat_history.toHtml().replace(
                    "<span id='stream_text' style='color:" + C_TEXT_MAIN + "; font-family:Consolas, monospace; font-size:11px;'></span>",
                    "<span id='stream_text' style='color:" + C_TEXT_MAIN + "; font-family:Consolas, monospace; font-size:11px;'>" + escaped + "</span>"
                )
            )
            if pos[0] < len(full_text):
                QTimer.singleShot(25, _step)
            else:
                # Final flush
                QTimer.singleShot(50, lambda: self.chat_history.setHtml(
                    self.chat_history.toHtml().replace(
                        "<span id='stream_text' style='color:" + C_TEXT_MAIN + "; font-family:Consolas, monospace; font-size:11px;'>" + escaped + "</span>",
                        "<span style='color:" + C_TEXT_MAIN + "; font-family:Consolas, monospace; font-size:11px;'>" + escaped + "</span>"
                    )
                ))
        QTimer.singleShot(30, _step)
        scrollbar = self.chat_history.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def load_skills(self):
        result = self.va.send({"type": "list_skills", "id": "skills"})
        skills = result.get("skills", []) if result.get("status") == "ok" else []
        # Clear existing buttons
        while self.skills_grid_layout.count():
            item = self.skills_grid_layout.takeAt(0)
            w = item.widget()
            if w: w.deleteLater()
        # Add up to 25 skill buttons (scrollable in sidebar)
        for s in skills[:25]:
            name = s.get('name', '?')
            category = s.get('category', '')
            self._add_skill_btn(name, category)

    def closeEvent(self, event):
        # Minimize to tray instead of closing
        if hasattr(self, '_tray') and self._tray:
            self.hide()
            event.ignore()
        else:
            event.ignore()  # Never close from X button

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging = True
            self._old_pos = event.globalPos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._dragging and self._old_pos:
            delta = event.globalPos() - self._old_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self._old_pos = event.globalPos()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._dragging = False
        super().mouseReleaseEvent(event)

    def _open_theme_picker(self):
        from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QGridLayout, QLabel,
                                     QGroupBox, QHBoxLayout as _HL)
        dlg = QDialog(self)
        dlg.setWindowTitle('Selector de tema — Serpentium x Caelestia')
        dlg.setFixedSize(420, 340)
        dlg.setStyleSheet(f"""
            QDialog {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {C_BG_DARK_0}, stop:1 {C_BG_DARK_1});
                border: 1px solid {C_GLASS_BORDER};
                border-radius: 16px;
            }}
            QLabel {{ color: {C_TEXT_MAIN}; font-family: 'Consolas', monospace; }}
        """)
        v = QVBoxLayout(dlg)
        v.setContentsMargins(20, 20, 20, 20)
        v.setSpacing(12)

        lbl = QLabel('◆ Elige un tema visual')
        lbl.setStyleSheet(f"color: {C_TEXT_PRIMARY}; font-size: 15px; font-weight: bold;")
        v.addWidget(lbl)

        # Theme preview cards with live color swatches
        themes = [
            ('Cyan Aurora',   C_ACCENT_CYAN_BRIGHT, C_ACCENT_PURPLE, 'default'),
            ('Purple Nebula', C_ACCENT_PURPLE,     C_ORB_BASE,      'purple'),
            ('Green Genesis', C_ACCENT_GREEN,      C_ACCENT_CYAN_BRIGHT, 'green'),
            ('Orange Ember',  C_ACCENT_ORANGE,     C_ACCENT_PURPLE, 'orange'),
        ]
        grid = QGridLayout()
        grid.setSpacing(12)
        for i, (name, primary, secondary, key) in enumerate(themes):
            card = self._build_theme_card(name, primary, secondary, key, dlg)
            grid.addWidget(card, i // 2, i % 2)
        v.addLayout(grid)

        close_btn = QPushButton('Streamer ← Volver')
        close_btn.setFixedHeight(38)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(15, 23, 42, 0.6);
                color: {C_TEXT_SECONDARY};
                border: 1px solid {C_GLASS_BORDER};
                border-radius: 10px;
                font-weight: bold;
                font-size: 12px;
                font-family: 'Consolas', monospace;
                transition: {C_TRANS_NORMAL};
            }}
            QPushButton:hover {{
                background: rgba(56, 189, 248, 0.15);
                border-color: {C_ACCENT_CYAN_BRIGHT};
                color: {C_TEXT_PRIMARY};
                box-shadow: 0 0 16px rgba(56, 189, 248, 0.3);
            }}
        """)
        close_btn.clicked.connect(dlg.reject)
        v.addWidget(close_btn)
        dlg.exec_()

    def _build_theme_card(self, name, primary, secondary, key, parent):
        """Build a theme preview card with color swatches + apply button."""
        card = QWidget()
        card.setFixedSize(170, 110)
        card.setStyleSheet(f"""
            QWidget {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(15, 23, 42, 0.7), stop:1 rgba(15, 23, 42, 0.4));
                border: 1px solid {C_GLASS_BORDER};
                border-radius: 12px;
                transition: {C_TRANS_NORMAL};
            }}
            QWidget:hover {{
                border-color: {primary};
                box-shadow: 0 0 20px {primary}60;
                transform: scale(1.03);
            }}
        """)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        # Color swatches row
        swatch_row = QHBoxLayout()
        swatch1 = QLabel()
        swatch1.setFixedSize(28, 28)
        swatch1.setStyleSheet(f"background: {primary}; border-radius: 6px; border: 1px solid rgba(255,255,255,0.2);")
        swatch2 = QLabel()
        swatch2.setFixedSize(28, 28)
        swatch2.setStyleSheet(f"background: {secondary}; border-radius: 6px; border: 1px solid rgba(255,255,255,0.2);")
        swatch_row.addWidget(swatch1)
        swatch_row.addWidget(swatch2)
        swatch_row.addStretch()
        layout.addLayout(swatch_row)

        name_lbl = QLabel(name)
        name_lbl.setStyleSheet(f"color: {C_TEXT_PRIMARY}; font-size: 11px; font-weight: bold;")
        layout.addWidget(name_lbl)

        apply_btn = QPushButton('Aplicar')
        apply_btn.setFixedHeight(26)
        apply_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {primary}, stop:1 {secondary});
                color: #0f172a;
                border: none;
                border-radius: 8px;
                font-weight: bold;
                font-size: 10px;
                font-family: 'Consolas', monospace;
                transition: {C_TRANS_NORMAL};
            }}
            QPushButton:hover {{
                box-shadow: 0 0 12px {primary};
                transform: translateY(-1px);
            }}
            QPushButton:active {{ transform: scale(0.95); }}
        """)
        apply_btn.clicked.connect(lambda k=key: (self._apply_theme(k), parent.accept()))
        layout.addWidget(apply_btn)
        return card

    def _apply_theme(self, theme_key):
        themes = {
            'default': (C_ACCENT_CYAN_BRIGHT, C_ACCENT_PURPLE),
            'purple': (C_ACCENT_PURPLE, C_ORB_BASE),
            'green':  (C_ACCENT_GREEN, C_ACCENT_CYAN_BRIGHT),
            'orange': (C_ACCENT_ORANGE, C_ACCENT_PURPLE),
        }
        primary, secondary = themes.get(theme_key, (C_ACCENT_CYAN_BRIGHT, C_ACCENT_PURPLE))
        self._current_theme = theme_key
        # Update orb colors
        self.orb._color = QColor(primary)
        self.orb.update()
        # Update status label
        self.status_label.setStyleSheet('color: ' + primary + '; font-size: 11px;')
        # Persist
        self._save_settings()
        self._append_chat('ARIA', 'Tema cambiado a ' + theme_key, primary)

    def _open_control_center(self):
        from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QLabel, QCheckBox,
                                     QSlider, QGroupBox, QHBoxLayout as _HL,
                                     QFormLayout)
        dlg = QDialog(self)
        dlg.setWindowTitle('◆ Control Center — Caelestia')
        dlg.setFixedSize(420, 460)
        dlg.setStyleSheet(f"""
            QDialog {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {C_BG_DARK_0}, stop:1 {C_BG_DARK_1});
                border: 1px solid {C_GLASS_BORDER};
                border-radius: 16px;
            }}
            QLabel {{ color: {C_TEXT_MAIN}; font-family: 'Consolas', monospace; }}
            QGroupBox {{
                color: {C_ACCENT_CYAN_BRIGHT};
                font-weight: bold;
                font-size: 12px;
                border: 1px solid {C_GLASS_BORDER};
                border-radius: 10px;
                padding-top: 10px;
                margin-top: 6px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 6px;
            }}
        """)
        v = QVBoxLayout(dlg)
        v.setContentsMargins(20, 20, 20, 20)
        v.setSpacing(14)

        lbl = QLabel('◆ Configuración del sistema')
        lbl.setStyleSheet(f"color: {C_TEXT_PRIMARY}; font-size: 15px; font-weight: bold;")
        v.addWidget(lbl)

        # ── Group: Visual ──
        grp_visual = QGroupBox('Visual')
        gl = QFormLayout()
        gl.setLabelAlignment(Qt.AlignRight)
        self._cc_anim_toggle = QCheckBox('Animaciones del orb')
        self._cc_anim_toggle.setChecked(True)
        self._cc_anim_toggle.setStyleSheet(f"QCheckBox {{ color: {C_TEXT_SECONDARY}; font-size: 11px; }}")
        gl.addRow('Animaciones', self._cc_anim_toggle)

        self._cc_glass_toggle = QCheckBox('Transparencia glassmorphism')
        self._cc_glass_toggle.setChecked(True)
        self._cc_glass_toggle.setStyleSheet(f"QCheckBox {{ color: {C_TEXT_SECONDARY}; font-size: 11px; }}")
        gl.addRow('Glass', self._cc_glass_toggle)

        self._cc_stream_toggle = QCheckBox('Streaming de texto')
        self._cc_stream_toggle.setChecked(True)
        self._cc_stream_toggle.setStyleSheet(f"QCheckBox {{ color: {C_TEXT_SECONDARY}; font-size: 11px; }}")
        gl.addRow('Streaming', self._cc_stream_toggle)
        grp_visual.setLayout(gl)
        v.addWidget(grp_visual)

        # ── Group: Audio/Notifications ──
        grp_notif = QGroupBox('Notificaciones')
        gl2 = QFormLayout()
        gl2.setLabelAlignment(Qt.AlignRight)
        self._cc_notif_toggle = QCheckBox('Habilitar notificaciones')
        self._cc_notif_toggle.setChecked(True)
        self._cc_notif_toggle.setStyleSheet(f"QCheckBox {{ color: {C_TEXT_SECONDARY}; font-size: 11px; }}")
        gl2.addRow('Notificaciones', self._cc_notif_toggle)

        self._cc_sound_toggle = QCheckBox('Sonido de respuesta')
        self._cc_sound_toggle.setChecked(False)
        self._cc_sound_toggle.setStyleSheet(f"QCheckBox {{ color: {C_TEXT_SECONDARY}; font-size: 11px; }}")
        gl2.addRow('Sonido', self._cc_sound_toggle)
        grp_notif.setLayout(gl2)
        v.addWidget(grp_notif)

        # ── Group: Opacity slider ──
        grp_opacity = QGroupBox('Opacidad de la interfaz')
        gl3 = QFormLayout()
        self._cc_opacity_slider = QSlider(Qt.Horizontal)
        self._cc_opacity_slider.setRange(60, 100)
        self._cc_opacity_slider.setValue(85)
        self._cc_opacity_slider.setTickPosition(QSlider.NoTicks)
        self._cc_opacity_slider.setStyleSheet(f"""
            QSlider::groove {{
                background: rgba(15, 23, 42, 0.6);
                height: 6px;
                border-radius: 3px;
            }}
            QSlider::handle {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {C_ACCENT_CYAN_BRIGHT}, stop:1 {C_ACCENT_PURPLE});
                width: 16px;
                border-radius: 8px;
                margin: -5px 0;
            }}
        """)
        self._cc_opacity_label = QLabel('85%')
        self._cc_opacity_label.setStyleSheet(f"color: {C_ACCENT_CYAN_BRIGHT}; font-weight: bold;")
        self._cc_opacity_slider.valueChanged.connect(
            lambda val: (self._cc_opacity_label.setText(str(val) + '%'),
                         self.setWindowOpacity(val / 100.0)))
        opacity_row = _HL()
        opacity_row.addWidget(self._cc_opacity_slider)
        opacity_row.addWidget(self._cc_opacity_label)
        gl3.addRow('Opacidad', opacity_row)
        grp_opacity.setLayout(gl3)
        v.addWidget(grp_opacity)

        # ── Save button ──
        save_btn = QPushButton('◆ Guardar configuración')
        save_btn.setFixedHeight(40)
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {C_ACCENT_CYAN_BRIGHT}, stop:1 {C_ACCENT_PURPLE});
                color: #0f172a;
                border: none;
                border-radius: 10px;
                font-weight: bold;
                font-size: 12px;
                font-family: 'Consolas', monospace;
                transition: {C_TRANS_NORMAL};
                box-shadow: 0 4px 16px rgba(0, 212, 255, 0.3);
            }}
            QPushButton:hover {{
                box-shadow: 0 6px 24px rgba(0, 212, 255, 0.5);
                transform: translateY(-2px);
            }}
            QPushButton:active {{ transform: scale(0.97); }}
        """)
        save_btn.clicked.connect(lambda: (self._save_settings(), dlg.accept()))
        v.addWidget(save_btn)
        dlg.exec_()

    def _open_nucleus(self):
        """Abre el panel de evolución y sacrifice del núcleo."""
        if not hasattr(self, '_nucleus_panel') or self._nucleus_panel is None:
            self._nucleus_panel = EvolutionPanel(self.va, self.orb, self)
            self._nucleus_panel._osd = getattr(self, '_osd', None)
        self._nucleus_panel.show()
        self._nucleus_panel.raise_()
        self._nucleus_panel.activateWindow()

    def _show_command_palette(self):

        from PyQt5.QtWidgets import QDialog, QLineEdit, QVBoxLayout, QListWidget, QListWidgetItem
        dlg = QDialog(self)
        dlg.setWindowTitle('Comando')
        dlg.setFixedSize(400, 300)
        dlg.setStyleSheet('QDialog { background: ' + C_BG_DEEP + '; border: 1px solid ' + C_GLASS_BORDER + '; border-radius: 12px; }')
        v = QVBoxLayout(dlg)
        search = QLineEdit()
        search.setPlaceholderText(' Buscar comando o skill...')
        search.setStyleSheet('QLineEdit { background: rgba(15, 23, 42, 0.8); color: ' + C_TEXT_MAIN + '; border: 1px solid ' + C_GLASS_BORDER + '; border-radius: 8px; padding: 10px; font-family: Consolas, monospace; }')
        v.addWidget(search)
        list_w = QListWidget()
        list_w.setStyleSheet('QListWidget { background: transparent; border: none; } QListWidget::item::selected { background: rgba(56, 189, 248, 0.2); }')
        v.addWidget(list_w)
        commands = [
            ('Busqueda web', 'web.search'),
            ('Clima', 'weather'),
            ('Lista de archivos', 'files.list'),
            ('Abrir app', 'system.open'),
            ('Screenshot', 'system.screenshot'),
            ('Estado del sistema', 'system.status'),
            ('Configuracion', 'settings'),
        ]
        for name, cmd in commands:
            item = QListWidgetItem(name + '  [' + cmd + ']')
            item.setData(Qt.UserRole, cmd)
            list_w.addItem(item)
        def _filter(text):
            for i in range(list_w.count()):
                item = list_w.item(i)
                item.setHidden(text.lower() not in item.text().lower())
        search.textChanged.connect(_filter)
        def _select():
            items = list_w.selectedItems()
            if items:
                cmd = items[0].data(Qt.UserRole)
                self.msg_input.setText(cmd)
                dlg.accept()
        list_w.itemDoubleClicked.connect(_select)
        dlg.exec_()

    def _show_notification(self, message, title="ARIA"):
        """Show a desktop notification via system tray."""
        try:
            if hasattr(self, '_tray') and self._tray:
                self._tray.showMessage(title, message, QSystemTrayIcon.Information, 3000)
        except Exception:
            pass

    def _on_message_sent(self):
        """Micro-interaction: ripple effect on send button."""
        self.orb.set_state("thinking")

    def _toggle_accessibility(self):
        """Toggle high-contrast accessibility mode."""
        if not hasattr(self, '_a11y_mode'):
            self._a11y_mode = False
        self._a11y_mode = not self._a11y_mode
        if self._a11y_mode:
            self.setStyleSheet(self.styleSheet() + """
                QLabel { font-size: 13px; }
                QTextEdit { font-size: 13px; }
                QLineEdit { font-size: 13px; }
            """)
        else:
            self.setStyleSheet(self.styleSheet())

    def _export_chat(self, filename=None):
        """Export chat history to a text file."""
        import datetime
        if not filename:
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"ARIA_chat_export_{ts}.txt"
        text = self.chat_history.toPlainText()
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(text)
            self._show_notification(f"Chat exportado a {filename}")
        except Exception as e:
            self._show_notification(f"Error exportando: {e}", "Error")

    def _clear_chat(self):
        """Clear chat history with confirmation."""
        from PyQt5.QtWidgets import QMessageBox
        reply = QMessageBox.question(self, "Limpiar chat",
            "Esto eliminará todo el historial. Continuar?",
            QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.chat_history.clear()
            self._append_chat("ARIA", "Chat limpio. ¿En que puedo ayudarte?", C_SUCCESS)

    def _show_shortcuts(self):
        """Show keyboard shortcuts help dialog."""
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel
        dlg = QDialog(self)
        dlg.setWindowTitle("Atajos de teclado")
        dlg.setFixedSize(380, 300)
        dlg.setStyleSheet("QDialog { background: " + C_BG_DEEP + "; }")
        v = QVBoxLayout(dlg)
        lbl = QLabel("Atajos de teclado")
        lbl.setStyleSheet("color: " + C_TEXT_MAIN + "; font-size: 14px; font-weight: bold; font-family: Consolas, monospace;")
        v.addWidget(lbl)
        shortcuts = [
            ("Enter", "Enviar mensaje"),
            ("Ctrl+L", "Limpiar chat"),
            ("Ctrl+E", "Exportar chat"),
            ("Ctrl+K", "Paleta de comandos"),
            ("Ctrl+T", "Cambiar tema"),
            ("Ctrl+,", "Control Center"),
            ("F1", "Esta ayuda"),
            ("Esc", ",Ocultar/Cerrar"),
        ]
        for key, desc in shortcuts:
            item = QLabel(f"<b>{key}</b>  —  {desc}")
            item.setStyleSheet("color: " + C_TEXT_DIM + "; font-size: 11px; font-family: Consolas, monospace; padding: 2px;")
            v.addWidget(item)
        close_btn = QPushButton("Close")
        close_btn.setFixedHeight(32)
        close_btn.setStyleSheet("QPushButton { background: " + C_ACCENT + "; color: #0f172a; border: none; border-radius: 8px; font-weight: bold; font-family: Consolas, monospace; }")
        close_btn.clicked.connect(dlg.accept)
        v.addWidget(close_btn)
        dlg.exec_()

    def _save_settings(self):
        """Persist settings to local storage."""
        import json
        settings = {
            'theme': getattr(self, '_current_theme', 'default'),
            'a11y_mode': getattr(self, '_a11y_mode', False),
            'window_geometry': [self.x(), self.y(), self.width(), self.height()],
        }
        try:
            with open('ARIA_APP/settings.json', 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=2)
        except Exception:
            pass

    def _load_settings(self):
        """Load persisted settings."""
        import json
        try:
            with open('ARIA_APP/settings.json', 'r', encoding='utf-8') as f:
                settings = json.load(f)
            if 'window_geometry' in settings:
                x, y, w, h = settings['window_geometry']
                self.setGeometry(x, y, w, h)
        except Exception:
            pass

    def _performance_monitor(self):
        """Lightweight performance monitoring: FPS and memory."""
        import time as _time
        if not hasattr(self, '_perf_frames'):
            self._perf_frames = 0
            self._perf_start = _time.time()
            self._perf_timer = QTimer(self)
            self._perf_timer.timeout.connect(self._perf_tick)
            self._perf_timer.start(1000)
        else:
            self._perf_frames += 1

    def _perf_tick(self):
        """Report FPS every second (debug only)."""
        import time as _time
        elapsed = _time.time() - self._perf_start
        if elapsed >= 1.0:
            fps = self._perf_frames / elapsed
            logger.debug(f"[PERF] FPS={fps:.1f}")
            self._perf_frames = 0
            self._perf_start = _time.time()

    def _setup_keyboard_shortcuts(self):
        """Register global keyboard shortcuts."""
        QShortcut(QKeySequence("Ctrl+K"), self).activated.connect(self._show_command_palette)
        QShortcut(QKeySequence("Ctrl+T"), self).activated.connect(self._open_theme_picker)
        QShortcut(QKeySequence("Ctrl+,"), self).activated.connect(self._open_control_center)
        QShortcut(QKeySequence("Ctrl+L"), self).activated.connect(self._clear_chat)
        QShortcut(QKeySequence("Ctrl+E"), self).activated.connect(self._export_chat)
        QShortcut(QKeySequence("F1"), self).activated.connect(self._show_shortcuts)

    def _debug_check(self):
        try:
            g = self.geometry()
            print(f"[DEBUG] Window visible={self.isVisible()}, geom=({g.x()},{g.y()},{g.width()},{g.height()})", flush=True)
        except Exception as e:
            print(f"[DEBUG] Error: {e}", flush=True)


# ── Floating Overlay Orb ──────────────────────────────────────────────────────

class OverlayOrb(QWidget):
    """Mini floating orb that stays on top, learns user position,
    auto-hides after inactivity, and expands to full ARIA on click."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._dragging = False
        self._offset = None
        self._last_interaction = time.time()
        self._state = "idle"
        self._opacity = 0.7
        self._position_history = []
        self._settings = QSettings("ARIA", "OverlayWidget")
        self._setup_window()
        self._setup_timer()
        self._setup_hotkeys()
        self._restore_position()

    def _setup_window(self):
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.setFixedSize(80, 80)
        self.setWindowOpacity(self._opacity)
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(screen.width() - 100, 20)

    def _setup_timer(self):
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._animate)
        self._timer.start(30)
        self._inactivity_timer = QTimer(self)
        self._inactivity_timer.timeout.connect(self._check_inactivity)
        self._inactivity_timer.start(5000)

    def _setup_hotkeys(self):
        try:
            import keyboard
            keyboard.add_hotkey('win+a', self._toggle_visibility)
            keyboard.add_hotkey('win+shift+a', self._expand_full)
        except Exception:
            pass

    def _restore_position(self):
        x = self._settings.value("overlay_x", 0, type=int)
        y = self._settings.value("overlay_y", 0, type=int)
        if x > 0 or y > 0:
            self.move(x, y)

    def _save_position(self):
        geo = self.frameGeometry()
        self._settings.setValue("overlay_x", geo.x())
        self._settings.setValue("overlay_y", geo.y())
        self._position_history.append({
            "x": geo.x(), "y": geo.y(), "time": time.time()
        })
        if len(self._position_history) > 100:
            self._position_history = self._position_history[-100:]

    def _toggle_visibility(self):
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.raise_()
            self.activateWindow()

    def _expand_full(self):
        if self.parent():
            self.parent().showNormal()
            self.parent().raise_()
            self.parent().activateWindow()
        self.hide()

    def _on_interaction(self):
        self._last_interaction = time.time()
        if not self.isVisible():
            self.show()

    def _check_inactivity(self):
        if time.time() - self._last_interaction > 30:
            self.hide()
            self._last_interaction = time.time()

    def _animate(self):
        self._phase = getattr(self, '_phase', 0.0) + 0.03
        self._pulse_phase = getattr(self, '_pulse_phase', 0.0) + 0.02
        if self._pulse_phase >= 1.0:
            self._pulse_phase = 0.0
        self.update()

    def set_state(self, state: str):
        """Sync state from main window orb."""
        self._state = state
        self.update()

    def mousePressEvent(self, event):
        self._on_interaction()
        if event.button() == Qt.LeftButton:
            dx = event.x() - 40
            dy = event.y() - 40
            if (dx*dx + dy*dy) <= 35*35:
                self._expand_full()
            else:
                self._dragging = True
                self._offset = event.globalPos() - self.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._dragging and event.buttons() == Qt.LeftButton:
            self.move(event.globalPos() - self._offset)
            self._save_position()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._dragging = False
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event):
        self._on_interaction()
        delta = event.angleDelta().y() / 120
        self._opacity = max(0.3, min(1.0, self._opacity + delta * 0.05))
        self.setWindowOpacity(self._opacity)
        self._settings.setValue("overlay_opacity", self._opacity)
        super().wheelEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        w, h = self.width(), self.height()
        cx, cy = w // 2, h // 2
        base_r = min(w, h) * 0.25
        phase = getattr(self, '_phase', 0.0)
        pulse_phase = getattr(self, '_pulse_phase', 0.0)
        breath = 1.0 + 0.10 * ((1 + math.sin(phase)) / 2)
        r = int(base_r * breath)
        painter.setPen(Qt.NoPen)

        # State-specific color
        state_colors = {
            "idle": QColor(56, 189, 248),
            "thinking": QColor(245, 158, 11),
            "responding": QColor(0, 212, 255),
            "listening": QColor(192, 132, 252),
        }
        orb_color = state_colors.get(self._state, QColor(56, 189, 248))

        # ── Layer 7: Pulse Ring (expanding outward, 2.0s ease-out) ──
        pulse_r = int(r + 30 * pulse_phase)
        pulse_alpha = max(0, int(60 * (1.0 - pulse_phase)))
        painter.setBrush(QBrush(QColor(56, 189, 248, pulse_alpha)))
        painter.drawEllipse(cx - pulse_r, cy - pulse_r, pulse_r*2, pulse_r*2)

        # ── Layer 6: Outer Halo (breathing 3s) ──
        halo_r = r + 18
        halo_alpha = int(40 + 15 * ((1 + math.sin(phase * 2)) / 2))
        painter.setBrush(QBrush(QColor(56, 189, 248, halo_alpha)))
        painter.drawEllipse(cx - halo_r, cy - halo_r, halo_r*2, halo_r*2)

        # ── Layer 5: Orbit Ring (rotating 4s linear) ──
        painter.setPen(QPen(QColor(56, 189, 248, 120), 1))
        painter.setBrush(Qt.NoBrush)
        painter.save()
        painter.translate(cx, cy)
        painter.rotate((phase * 57.3) % 360)
        painter.drawEllipse(-32, -32, 64, 64)
        painter.restore()

        # ── Layer 4: Orbit Particles (small, pulsing) ──
        n_particles = 8
        for i in range(n_particles):
            pa = (phase * 2 + i * (6.283 / n_particles)) % 6.283
            px = cx + 32 * math.cos(pa)
            py = cy + 32 * math.sin(pa)
            p_alpha = int(180 + 75 * ((1 + math.sin(phase * 3 + i)) / 2))
            painter.setBrush(QBrush(QColor(0, 212, 255, p_alpha)))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(int(px) - 1, int(py) - 1, 3, 3)

        # ── Layer 3: Core Glow (breathing 1.5s) ──
        glow_r = r + 8
        core_alpha = int(80 + 30 * ((1 + math.sin(phase * 4)) / 2))
        painter.setBrush(QBrush(QColor(56, 189, 248, core_alpha)))
        painter.drawEllipse(cx - glow_r, cy - glow_r, glow_r*2, glow_r*2)

        # ── Layer 2: Solid Sphere (radial gradient, state-colored) ──
        gradient = QRadialGradient(cx, cy, 0, cx, cy, r)
        gradient.setColorAt(0, QColor(125, 211, 252))
        gradient.setColorAt(0.5, orb_color)
        gradient.setColorAt(1, QColor(0, 150, 200))
        painter.setBrush(QBrush(gradient))
        painter.drawEllipse(cx - r, cy - r, r*2, r*2)

        # ── Layer 1: Burst Rays (on thinking/responding) ──
        if self._state in ("thinking", "responding"):
            n_rays = 10
            for i in range(n_rays):
                ba = (phase * 3 + i * (6.283 / n_rays)) % 6.283
                bx = int(cx + math.cos(ba) * r)
                by = int(cy + math.sin(ba) * r)
                ex = int(cx + math.cos(ba) * (r + 18))
                ey = int(cy + math.sin(ba) * (r + 18))
                b_alpha = int(150 * (1 - pulse_phase))
                painter.setPen(QPen(QColor(0, 212, 255, max(0, b_alpha)), 1))
                painter.setBrush(Qt.NoBrush)
                painter.drawLine(bx, by, ex, ey)

        # Inner highlight
        painter.setBrush(QBrush(QColor(255, 255, 255, 50)))
        painter.drawEllipse(cx - r//3, cy - r//3 - r//4, r//2, r//3)

        painter.end()


# ── Evolution Panel (sacrifice + cadenas de evolución) ──────────────────────────

EVOLUTION_CHAINS = {
    "gran_sabio_analisis": {
        "name": "Gran Sabio Análisis",
        "next": "gran_sabio_supremo",
        "desc": "Análisis profundo de cualquier asunto.",
        "sacrifice_cost": "ciel_infon_flujo",
    },
    "gran_sabio_supremo": {
        "name": "Gran Sabio Supremo",
        "next": "núcleo_fusionado_final",
        "desc": "Sabiduría acumulada al máximo.",
        "sacrifice_cost": "orbe_resonante",
    },
    "núcleo_fusionado_final": {
        "name": "Núcleo Fusionado Final",
        "next": None,
        "desc": "La forma última del núcleo ARIA.",
        "sacrifice_cost": "espada_eterna",
    },
    "ciel_infon_flujo": {
        "name": "Flujo de Infons (Ciel)",
        "next": "sabiduría_fusionada",
        "desc": "Corriente constante de infons cósmicos.",
        "sacrifice_cost": None,
    },
    "sabiduría_fusionada": {
        "name": "Sabiduría Fusionada",
        "next": "orbe_resonante",
        "desc": "Sabiduría que resuena entre dimensiones.",
        "sacrifice_cost": None,
    },
    "orbe_resonante": {
        "name": "Orbe Resonante",
        "next": "orbe_infinito",
        "desc": "Orbe que vibra con la frecuencia del universo.",
        "sacrifice_cost": None,
    },
    "orbe_infinito": {
        "name": "Orbe Infinito",
        "next": None,
        "desc": "Orbe sin límites ni final.",
        "sacrifice_cost": None,
    },
    "raphael_transformacion": {
        "name": "Transformación (Raphael)",
        "next": "espada_eterna",
        "desc": "Corta la ilusión, revela la verdad.",
        "sacrifice_cost": None,
    },
    "espada_eterna": {
        "name": "Espada Eterna",
        "next": None,
        "desc": "Filosofía convertida en acción pura.",
        "sacrifice_cost": None,
    },
}


class EvolutionPanel(QWidget):
    """Panel flotante: muestra cadenas de evolución, botón de sacrifice y lista de skills."""

    def __init__(self, va: VAAdapter, orb: OrbWidget, parent=None):
        super().__init__(parent)
        self.va = va
        self.orb = orb
        self._setup_ui()
        self._refresh()

    def _setup_ui(self):
        self.setWindowTitle("◆ Núcleo ARIA — Evolución y Sacrifice")
        self.setFixedSize(460, 560)
        self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)
        self.setStyleSheet(f"""
            QDialog, QWidget {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {C_BG_DARK_0}, stop:1 {C_BG_DARK_1});
                border: 1px solid {C_GLASS_T1_BORDER};
                border-radius: 18px;
            }}
            QLabel {{ color: {C_TEXT_MAIN}; font-family: 'Consolas', monospace; }}
            QScrollArea {{ background: transparent; border: none; }}
        """)
        v = QVBoxLayout(self)
        v.setContentsMargins(20, 20, 20, 20)
        v.setSpacing(12)

        # Título
        lbl = QLabel("◆ Núcleo ARIA")
        lbl.setStyleSheet(f"color: {C_ACCENT_CYAN_BRIGHT}; font-size: 16px; font-weight: bold; letter-spacing: 2px;")
        v.addWidget(lbl)

        sub = QLabel("Evolución de habilidades y sacrifice")
        sub.setStyleSheet(f"color: {C_TEXT_SECONDARY}; font-size: 11px; margin-bottom: 6px;")
        v.addWidget(sub)

        # Selector de aspecto
        asp_grp = QGroupBox("Aspecto del Núcleo")
        asp_grp.setStyleSheet(f"""
            QGroupBox {{
                color: {C_ACCENT_CYAN_BRIGHT};
                font-weight: bold;
                font-size: 11px;
                border: 1px solid {C_GLASS_T1_BORDER};
                border-radius: 10px;
                margin-top: 8px;
                padding-top: 8px;
            }}
            QGroupBox::title {{ subcontrol-origin: margin; subcontrol-position: top left; padding: 0 6px; }}
        """)
        asp_layout = QHBoxLayout()
        for aspect in ("ciel", "raphael", "gran_sabio", "fused"):
            r, g, b = ASPECT_RGB[aspect]
            btn = QPushButton(aspect.replace("_", " ").title())
            btn.setFixedHeight(28)
            btn.setCheckable(True)
            btn.setChecked(aspect == self.orb._aspect)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {C_GLASS_T2_BG};
                    color: {C_TEXT_TERTIARY};
                    border: 1px solid {C_GLASS_T2_BORDER};
                    border-radius: 8px;
                    font-size: 10px;
                    font-family: 'Consolas', monospace;
                }}
                QPushButton:checked {{
                    background: rgba({r}, {g}, {b}, 0.35);
                    color: {C_TEXT_PRIMARY};
                    border-color: rgba({r}, {g}, {b}, 0.8);
                    box-shadow: 0 0 12px rgba({r}, {g}, {b}, 0.5);
                }}
                QPushButton:hover:!checked {{
                    border-color: rgba({r}, {g}, {b}, 0.4);
                }}
            """)
            btn.clicked.connect(lambda _, a=aspect, b=btn: self._set_aspect(a, b))
            asp_layout.addWidget(btn)
        asp_grp.setLayout(asp_layout)
        v.addWidget(asp_grp)

        # Cadenas de evolución
        evo_lbl = QLabel("Cadenas de Evolución")
        evo_lbl.setStyleSheet(f"color: {C_ACCENT_PURPLE}; font-size: 12px; font-weight: bold; margin-top: 8px;")
        v.addWidget(evo_lbl)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(240)
        self.evo_list = QWidget()
        self.evo_layout = QVBoxLayout(self.evo_list)
        self.evo_layout.setSpacing(8)
        scroll.setWidget(self.evo_list)
        v.addWidget(scroll)

        # Botón de sacrifice
        self.sac_btn = QPushButton("◆ Ejecutar Sacrifice")
        self.sac_btn.setFixedHeight(40)
        self.sac_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {C_ACCENT_ORANGE}, stop:1 #ef4444);
                color: #0f172a;
                border: none;
                border-radius: 10px;
                font-weight: bold;
                font-size: 12px;
                font-family: 'Consolas', monospace;
                box-shadow: 0 4px 16px {C_ACCENT_ORANGE}40;
                transition: {C_TRANS_NORMAL};
            }}
            QPushButton:hover {{
                box-shadow: 0 6px 24px {C_ACCENT_ORANGE}60;
                transform: translateY(-2px);
            }}
            QPushButton:pressed {{ transform: scale(0.97); }}
        """)
        self.sac_btn.clicked.connect(self._do_sacrifice)
        v.addWidget(self.sac_btn)

        # Lista de skills
        sk_lbl = QLabel("Skills Disponibles")
        sk_lbl.setStyleSheet(f"color: {C_ACCENT_CYAN_BRIGHT}; font-size: 12px; font-weight: bold; margin-top: 10px;")
        v.addWidget(sk_lbl)
        self.skills_list = QListWidget()
        self.skills_list.setStyleSheet(f"""
            QListWidget {{
                background: {C_GLASS_T2_BG};
                border: 1px solid {C_GLASS_T2_BORDER};
                border-radius: 10px;
                color: {C_TEXT_SECONDARY};
                font-family: 'Consolas', monospace;
                font-size: 11px;
            }}
            QListWidget::item {{
                padding: 6px 10px;
                border-bottom: 1px solid {C_GLASS_T1_BORDER};
            }}
            QListWidget::item:selected {{
                background: {C_GLASS_T3_BG};
                color: {C_ACCENT_CYAN_BRIGHT};
                border-left: 3px solid {C_ACCENT_CYAN_BRIGHT};
            }}
        """)
        self.skills_list.setMaximumHeight(140)
        v.addWidget(self.skills_list)

        close_btn = QPushButton("Cerrar Núcleo")
        close_btn.setFixedHeight(34)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: {C_GLASS_T1_BG};
                color: {C_TEXT_TERTIARY};
                border: 1px solid {C_GLASS_T1_BORDER};
                border-radius: 8px;
                font-size: 11px;
                font-family: 'Consolas', monospace;
            }}
            QPushButton:hover {{ border-color: {C_ACCENT_CYAN_BRIGHT}; }}
        """)
        close_btn.clicked.connect(self.close)
        v.addWidget(close_btn)

    def _set_aspect(self, aspect: str, btn: QPushButton):
        set_aspect(aspect)
        self.orb.set_aspect(aspect)
        for i in range(self.evo_list.layout().count()):
            pass  # no-op, buttons handle own state
        # Refresh checked state
        for b in self.findChildren(QPushButton):
            if b.text().lower().replace(" ", "_") == aspect:
                b.setChecked(True)
            elif b.text().lower().replace(" ", "_") in ("ciel", "raphael", "gran sabio", "fused"):
                b.setChecked(False)
        self._append_osd(f"Aspecto del núcleo: {aspect.title()}")

    def _refresh(self):
        # Limpiar cadenas
        while self.evo_layout.count():
            item = self.evo_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        # Render cadenas
        for key, chain in EVOLUTION_CHAINS.items():
            row = QHBoxLayout()
            name_lbl = QLabel(chain["name"])
            name_lbl.setStyleSheet(f"color: {C_TEXT_PRIMARY}; font-size: 11px; font-weight: bold; min-width: 150px;")
            row.addWidget(name_lbl)
            desc = QLabel(chain["desc"])
            desc.setStyleSheet(f"color: {C_TEXT_SECONDARY}; font-size: 10px;")
            row.addWidget(desc)
            row.addStretch()
            if chain["next"]:
                nxt = EVOLUTION_CHAINS[chain["next"]]["name"]
                arrow = QLabel(f"→ {nxt}")
                arrow.setStyleSheet(f"color: {C_ACCENT_CYAN_BRIGHT}; font-size: 10px; font-weight: bold;")
                row.addWidget(arrow)
            else:
                done = QLabel("ÚLTIMA")
                done.setStyleSheet(f"color: {C_SUCCESS}; font-size: 9px; font-weight: bold;")
                row.addWidget(done)
            wrow = QWidget()
            wrow.setLayout(row)
            wrow.setStyleSheet(f"""
                QWidget {{ background: {C_GLASS_T2_BG}; border: 1px solid {C_GLASS_T2_BORDER}; border-radius: 8px; padding: 6px; }}
            """)
            self.evo_layout.addWidget(wrow)

        # Lista de skills
        result = self.va.send({"type": "list_skills", "id": "skills"})
        skills = result.get("skills", []) if result.get("status") == "ok" else []
        self.skills_list.clear()
        for s in skills[:30]:
            name = s.get('name', '?')
            category = s.get('category', '')
            item = QListWidgetItem(f"{name}  [{category}]")
            self.skills_list.addItem(item)

    def _do_sacrifice(self):
        # Sacrifice simple: tentar evolucionar la primera cadena disponible
        for key, chain in EVOLUTION_CHAINS.items():
            cost = chain["sacrifice_cost"]
            if cost:
                result = self.va.send({
                    "type": "skill",
                    "skill": "media_extract_all",
                    "params": {"url": ""}
                }) if False else None
                # Simular sacrifice (lógica real está en el núcleo Python)
                self._append_osd(f"Sacrifice: {chain['name']} → {chain['next'] or 'completa'}")
                self.orb.set_state("responding")
                QTimer.singleShot(1200, lambda: self.orb.set_state("idle"))
                self._refresh()
                return
        self._append_osd("No hay sacrifice disponible en este momento")

    def _append_osd(self, message: str):
        if hasattr(self, '_osd') and self._osd:
            self._osd.notify(message)

    def showEvent(self, event):
        super().showEvent(event)
        self._refresh()


class OSDNotification(QLabel):
    """Notificación estilo OSD que aparece sobre el orb y se desvanece."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet(f"""
            QLabel {{
                background: {C_GLASS_T1_BG};
                color: {C_TEXT_PRIMARY};
                border: 1px solid {C_GLASS_T1_BORDER};
                border-radius: 10px;
                padding: 10px 18px;
                font-size: 12px;
                font-weight: bold;
                font-family: 'Consolas', monospace;
                box-shadow: 0 0 24px rgba(0,0,0,0.6);
            }}
        """)
        self.setWordWrap(True)
        self.hide()
        self._fade_timer = QTimer(self)
        self._fade_timer.timeout.connect(self._fade_step)
        self._opacity = 1.0

    def notify(self, message: str, color: str = C_ACCENT_CYAN_BRIGHT):
        self.setText(message)
        self.setStyleSheet(self.styleSheet().replace(C_TEXT_PRIMARY, color))
        # Centrar sobre el padre
        if self.parent():
            p = self.parent()
            self.move(p.width() // 2 - self.width() // 2, p.height() // 3)
        self.show()
        self.raise_()
        self._opacity = 1.0
        self._fade_timer.start(40)

    def _fade_step(self):
        self._opacity -= 0.05
        if self._opacity <= 0:
            self._fade_timer.stop()
            self.hide()
            self._opacity = 1.0
            self.setStyleSheet(self.styleSheet().replace(
                f"color: {C_ACCENT_CYAN_BRIGHT};", f"color: {C_TEXT_PRIMARY};"))
        else:
            self.setGraphicsEffect(None)
            from PyQt5.QtWidgets import QGraphicsOpacityEffect
            eff = QGraphicsOpacityEffect()
            eff.setOpacity(self._opacity)
            self.setGraphicsEffect(eff)


# ── Main Application ────────────────────────────────────────────────────────

def run_desktop():
    import sys as _sys
    print("[UI] Starting QApplication...", flush=True)
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setQuitOnLastWindowClosed(False)
    # Apply fusion dark palette
    from PyQt5.QtGui import QPalette, QColor
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(15, 23, 42))
    palette.setColor(QPalette.WindowText, QColor(226, 232, 240))
    palette.setColor(QPalette.Base, QColor(15, 23, 42))
    palette.setColor(QPalette.AlternateBase, QColor(30, 41, 59))
    palette.setColor(QPalette.ToolTipBase, QColor(30, 41, 59))
    palette.setColor(QPalette.ToolTipText, QColor(226, 232, 240))
    palette.setColor(QPalette.Text, QColor(226, 232, 240))
    palette.setColor(QPalette.Button, QColor(30, 41, 59))
    palette.setColor(QPalette.ButtonText, QColor(226, 232, 240))
    palette.setColor(QPalette.BrightText, QColor(245, 158, 11))
    palette.setColor(QPalette.Highlight, QColor(56, 189, 248))
    palette.setColor(QPalette.HighlightedText, QColor(15, 23, 42))
    app.setPalette(palette)
    print("[UI] QApplication created", flush=True)

    va = VAAdapter()
    print("[UI] VA local iniciado", flush=True)

    window = ChatWindow(va)
    print("[UI] ChatWindow created", flush=True)
    window.load_skills()
    print("[UI] Skills loaded", flush=True)

    # OSD notification overlay (sobre la ventana principal)
    osd = OSDNotification(window)
    window._osd = osd
    print("[UI] OSD notification created", flush=True)

    # Floating overlay orb (always-on-top mini widget)
    overlay = OverlayOrb(window)
    overlay.show()
    print("[UI] OverlayOrb created (80x80, always-on-top)", flush=True)

    # System tray
    tray_icon = QIcon.fromTheme("preferences-desktop-personal")
    if tray_icon.isNull():
        tray_icon = QIcon(_make_tray_pixmap())

    tray = QSystemTrayIcon()
    tray.setIcon(tray_icon)
    tray.setToolTip("ARIA OS v4.0")

    menu = QMenu()
    show_act = menu.addAction("Mostrar ARIA")
    quit_act = menu.addAction(" salir")
    tray.setContextMenu(menu)

    def _show():
        window.show()
        window.raise_()
        window.activateWindow()

    show_act.triggered.connect(_show)
    quit_act.triggered.connect(lambda: (va.stop(), app.quit()))
    tray.activated.connect(lambda x: _show() if x == QSystemTrayIcon.Context else None)

    tray.show()
    window._tray = tray
    print("[UI] Tray created", flush=True)

    window.show()
    print("[UI] Window shown, visible=" + str(window.isVisible()), flush=True)
    g = window.geometry()
    print("[UI] Window geometry:", f"({g.x()},{g.y()},{g.width()},{g.height()})", flush=True)

    # Keep-alive timer to prevent premature exit
    _keepalive = QTimer()
    _keepalive.start(500)
    _keepalive.timeout.connect(lambda: None)

    def on_response(result):
        if result.get("status") == "ok":
            response = result.get("response", "")
            source = result.get("source", result.get("provider", "?"))
            confidence = result.get("confidence", 0.8)
            latency = result.get("latency", 0.0)
            # Build meta string: source + confidence + latency
            meta_parts = ["src:" + str(source)]
            if confidence:
                meta_parts.append("conf:" + str(int(confidence * 100)) + "%")
            if latency:
                meta_parts.append(str(round(latency, 1)) + "s")
            meta = " · ".join(meta_parts)
            # Streaming text effect with confidence indicator + action buttons
            window._append_streaming("ARIA", response, C_ACCENT_CYAN_BRIGHT, meta)
            QTimer.singleShot(1800, lambda: window._add_action_buttons(response))
            window.orb.set_state("responding")
            window.status_dot.setStyleSheet(f"color: {C_ACCENT_CYAN_BRIGHT}; font-size: 10px;")
            window.status_label.setText("Respondiendo...")
            window.status_label.setStyleSheet(f"color: {C_ACCENT_CYAN_BRIGHT}; font-size: 11px; font-family: 'Segoe UI';")
            # Also update overlay orb state
            overlay.set_state("responding")
            QTimer.singleShot(2500, lambda: (window.orb.set_state("idle"),
                overlay.set_state("idle"),
                window.status_dot.setStyleSheet(f"color: {C_SUCCESS}; font-size: 10px;"),
                window.status_label.setText("Listo"),
                window.status_label.setStyleSheet(f"color: {C_TEXT_SECONDARY}; font-size: 11px; font-family: 'Segoe UI';")))
        else:
            error = result.get("error", "Error desconocido")
            window._append_chat("ARIA", "[Error] " + str(error), C_ORB_ERROR)
            window.orb.set_state("idle")
            overlay.set_state("idle")
            window.status_dot.setStyleSheet(f"color: {C_ORB_ERROR}; font-size: 10px;")
            window.status_label.setText("Error")
            window.status_label.setStyleSheet(f"color: {C_ORB_ERROR}; font-size: 11px; font-family: 'Segoe UI';")

    window.response_received.connect(on_response)
    print("[UI] Entering event loop...", flush=True)

    app.exec_()
    print("[UI] Event loop exited", flush=True)


def _make_tray_pixmap():
    from PyQt5.QtGui import QPixmap, QPainter
    from PyQt5.QtCore import Qt
    pixmap = QPixmap(22, 22)
    pixmap.fill(Qt.transparent)
    p = QPainter(pixmap)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QBrush(QColor(56, 189, 248)))
    p.setPen(Qt.NoPen)
    p.drawEllipse(1, 1, 20, 20)
    p.end()
    return pixmap


if __name__ == "__main__":
    run_desktop()
