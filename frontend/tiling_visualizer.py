"""Tiling Visualizer — Representacion visual de workspaces estilo Niri/Hyprland.

Barra horizontal con miniaturas de escritorios virtuales, vista previa de
mosaico y transiciones suaves de deslizamiento horizontal al cambiar de workspace.
Estilo Niri WM con animaciones de entrada/salida y modos de tiling.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime

from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, Signal, Property, QRect, QPoint
from PySide6.QtGui import QFont, QColor, QPainter, QPen, QBrush, QMouseEvent
from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QFrame

from frontend.caelestia_theme_engine import theme_engine

TILING_MODES = ["layoutmsg", "splitv", "splith", "grid", "stack", "tab", "floating"]


@dataclass
class Workspace:
    id: int
    name: str
    active: bool = False
    window_count: int = 0
    windows: List[str] = None


class WorkspaceThumbnail(QWidget):
    """Miniatura de workspace con vista previa de mosaicos."""

    clicked = Signal(int)

    def __init__(self, ws: Workspace, parent=None, thumb_size: int = 70) -> None:
        super().__init__(parent)
        self._ws = ws
        self._thumb_size = thumb_size
        self._hovered = False
        self._scale: float = 0.0
        self.setFixedSize(thumb_size, thumb_size)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._setup_anim()

    def _setup_anim(self) -> None:
        self._pulse_anim = QPropertyAnimation(self, b"_scale")
        self._pulse_anim.setDuration(250)
        self._pulse_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def _get_scale(self) -> float:
        return self._scale

    def _set_scale(self, val: float) -> None:
        self._scale = val
        self.update()

    _scale_prop = Property(float, _get_scale, _set_scale)

    def set_active(self, active: bool) -> None:
        self._ws.active = active
        self.update()
        if active:
            self._pulse_anim.setStartValue(0.85)
            self._pulse_anim.setEndValue(1.0)
            self._pulse_anim.start()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self.clicked.emit(self._ws.id)

    def enterEvent(self, event) -> None:
        self._hovered = True
        self.update()

    def leaveEvent(self, event) -> None:
        self._hovered = False
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        p = theme_engine.current

        w = self._thumb_size
        scale = self._scale * 0.3 + 0.9
        draw_w = int(w * scale)
        draw_h = int(w * scale)
        offset = (w - draw_w) // 2
        rect = QRect(offset, offset, draw_w, draw_h)

        color = p.primary if self._ws.active else "rgba(100, 100, 140, 0.3)"
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(color))
        painter.drawRoundedRect(rect, 8, 8)

        if self._ws.active:
            painter.setPen(QPen(QColor(p.neon), 2))
            painter.drawRoundedRect(rect, 8, 8)

        painter.setFont(QFont("Segoe UI", 8))
        painter.setPen(QColor(p.on_surface))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self._ws.name)

        if self._ws.window_count > 0:
            painter.setFont(QFont("Segoe UI", 6))
            painter.setPen(QColor(148, 163, 184))
            painter.drawText(rect, Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight, str(self._ws.window_count))


class TilingModeIndicator(QFrame):
    """Indicador del modo de tiling activo (Niri-style)."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._current_mode: str = TILING_MODES[0]
        self._setup_ui()
        self.setFixedHeight(26)

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 6, 2)
        self._label = QLabel("LAYOUT")
        self._label.setStyleSheet(theme_engine.current_as_label_css(9, True, "#94a3bc"))
        layout.addWidget(self._label)

        self._mode_btn = QPushButton(self._current_mode.upper())
        self._mode_btn.setFixedHeight(20)
        self._mode_btn.setStyleSheet("""
            QPushButton { background: rgba(79, 70, 229, 0.3); border: 1px solid rgba(255,255,255,0.15); border-radius: 6px; color: white; font-size: 9px; padding: 2px 8px; }
        """)
        layout.addWidget(self._mode_btn)
        self.setStyleSheet(theme_engine.current_as_glass_css())

    def set_mode(self, mode: str) -> None:
        if mode in TILING_MODES:
            self._current_mode = mode
            self._mode_btn.setText(mode.upper())

    def cycle_mode(self) -> None:
        idx = (TILING_MODES.index(self._current_mode) + 1) % len(TILING_MODES)
        self._current_mode = TILING_MODES[idx]
        self._mode_btn.setText(self._current_mode.upper())


class TilingWorkspaceBar(QWidget):
    """Barra horizontal de workspaces con transiciones de deslizamiento."""

    workspace_activated = Signal(int)

    def __init__(self, parent=None, workspace_count: int = 5) -> None:
        super().__init__(parent)
        self._ws_count = workspace_count
        self._active_id: int = 1
        self._setup_ui()

    def _setup_ui(self) -> None:
        main = QHBoxLayout(self)
        main.setContentsMargins(4, 2, 4, 2)
        main.setSpacing(6)

        self._container = QWidget()
        self._hlayout = QHBoxLayout(self._container)
        self._hlayout.setContentsMargins(0, 0, 0, 0)
        self._hlayout.setSpacing(4)

        self._thumbnails: List[WorkspaceThumbnail] = []
        for i in range(1, self._ws_count + 1):
            ws = Workspace(id=i, name=f"WS{i}", active=(i == 1), window_count=i % 4)
            thumb = WorkspaceThumbnail(ws)
            thumb.clicked.connect(self._on_thumb_clicked)
            self._hlayout.addWidget(thumb)
            self._thumbnails.append(thumb)

        scroll = QHBoxLayout()
        scroll.addStretch()
        scroll.addWidget(self._container)
        scroll.addStretch()
        main.addLayout(scroll)

        self._mode_indicator = TilingModeIndicator()
        main.addWidget(self._mode_indicator)
        self.setFixedHeight(32)
        self.setStyleSheet(theme_mgr_css("tiling_bar"))

    def _on_thumb_clicked(self, ws_id: int) -> None:
        self._animate_slide_to(ws_id)
        self.workspace_activated.emit(ws_id)

    def _animate_slide_to(self, ws_id: int) -> None:
        for thumb in self._thumbnails:
            thumb.set_active(thumb._ws.id == ws_id)
        self._active_id = ws_id

        anim = QPropertyAnimation(self._container, b"pos")
        anim.setDuration(300)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        target_x = self._thumbnails[ws_id - 1].x() if ws_id <= len(self._thumbnails) else 0
        start_x = self._container.x()
        anim.setStartValue(QPoint(start_x, 0))
        anim.setEndValue(QPoint(start_x + (target_x - start_x) * 0.1, 0))
        anim.start()

        for i, thumb in enumerate(self._thumbnails):
            delay = QPropertyAnimation(thumb, b"_scale")
            delay.setDuration(200)
            delay.setStartValue(0.85)
            delay.setEndValue(1.0)
            delay.start()

    def set_active_workspace(self, ws_id: int) -> None:
        if 1 <= ws_id <= self._ws_count:
            self._animate_slide_to(ws_id)

    def activate_workspace(self, ws_id: int, window_count: int = 0) -> None:
        if 1 <= ws_id <= self._ws_count:
            self._thumbnails[ws_id - 1]._ws.active = True
            self._thumbnails[ws_id - 1]._ws.window_count = window_count
            self._thumbnails[ws_id - 1].update()
            self._active_id = ws_id


def theme_mgr_css(name: str) -> str:
    p = theme_engine.current
    return f"""
    QWidget#{name} {{
        background: {p.background};
        border-radius: 10px;
    }}
    """
