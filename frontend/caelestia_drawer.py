"""Caelestia Drawer — Side drawer with Quick Settings & Notifications.

Desplegable lateral con animacion QPropertyAnimation estilo Caelestia Shell.
Incluye sliders tactiles de volumen/micrófono con medidor RMS en vivo,
Quick Toggles para AI Local, WebRTC, Modo Noche, Swarm Monitor y Bloqueo,
centro de notificaciones agrupadas y telemetria en tiempo real via WebSocket.
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional
from datetime import datetime

from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QPoint, Signal, QThread, QObject
from PySide6.QtGui import QFont, QColor, QPen, QBrush, QPainter
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QSlider, QFrame, QScrollArea, QProgressBar, QGridLayout,
)
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWebSockets import QWebSocket
from PySide6.QtNetwork import QNetworkRequest

from frontend.caelestia_theme_engine import theme_engine
from frontend.material_widgets import SystemTelemetryGauge, WeatherWidget, MediaPlayerWidget


TELEMETRY_WS_URL = "ws://127.0.0.1:8000/ws/telemetry"


@dataclass
class QuickToggleDef:
    label: str
    icon: str
    section: str
    active: bool = False
    callback: Optional[Callable] = None


@dataclass
class NotificationData:
    title: str
    body: str
    icon: str = "🔔"
    timestamp: str = ""
    read: bool = False
    group: str = "general"


class QuickToggleButton(QWidget):
    """Toggle tactil con icono, etiqueta y conmutador."""

    toggled = Signal(bool)

    def __init__(self, toggle_def: QuickToggleDef, parent=None) -> None:
        super().__init__(parent)
        self._def = toggle_def
        self._active = toggle_def.active
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)

        self._icon = QLabel(self._def.icon)
        self._icon.setStyleSheet("font-size: 16px;")
        layout.addWidget(self._icon)

        self._label = QLabel(self._def.label)
        self._label.setStyleSheet(theme_engine.current_as_label_css(11))
        layout.addWidget(self._label)

        layout.addStretch()

        self._toggle = QFrame()
        self._toggle.setFixedSize(40, 22)
        self._toggle.setFrameShape(QFrame.Shape.StyledPanel)
        layout.addWidget(self._toggle)

        self._btn = QPushButton()
        self._btn.setFixedSize(44, 26)
        self._btn.setStyleSheet("background: transparent; border: none;")
        self._btn.clicked.connect(self._on_click)
        self._update_toggle_style()

    def _update_toggle_style(self) -> None:
        p = theme_engine.current
        bg = p.secondary if self._active else "rgba(100, 100, 140, 0.2)"
        self._toggle.setStyleSheet(f"background: {bg}; border-radius: 11px; border: 2px solid {p.outline};")

    def _on_click(self) -> None:
        self._active = not self._active
        self._update_toggle_style()
        if self._def.callback:
            self._def.callback(self._active)
        self.toggled.emit(self._active)

    def set_active(self, active: bool) -> None:
        if self._active != active:
            self._active = active
            self._update_toggle_style()


class NotificationItem(QFrame):
    """Elemento individual de notificacion en el centro de notificaciones."""

    def __init__(self, data: NotificationData, parent=None) -> None:
        super().__init__(parent)
        self._data = data
        self._setup_ui()
        self._apply_read_state()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(6)

        self._icon = QLabel(self._data.icon)
        self._icon.setStyleSheet("font-size: 14px;")
        layout.addWidget(self._icon)

        v = QVBoxLayout()
        self._title = QLabel(self._data.title)
        self._title.setStyleSheet(theme_engine.current_as_label_css(11, True))
        v.addWidget(self._title)
        self._body = QLabel(self._data.body)
        self._body.setStyleSheet(theme_engine.current_as_label_css(9, False, "#94a3bc"))
        self._body.setWordWrap(True)
        v.addWidget(self._body)
        layout.addLayout(v)

        self._time = QLabel(self._data.timestamp or datetime.now().strftime("%H:%M"))
        self._time.setStyleSheet(theme_engine.current_as_label_css(8, False, "#64748a"))
        layout.addWidget(self._time)

    def _apply_read_state(self) -> None:
        if self._data.read:
            self._title.setStyleSheet(theme_engine.current_as_label_css(11, False, "#64748a"))

    def mark_read(self) -> None:
        self._data.read = True
        self._apply_read_state()


class TelemetryWorker(QObject):
    """Worker WebSocket para telemetria en tiempo real."""

    message_received = Signal(dict)
    connected = Signal()
    disconnected = Signal()

    def __init__(self, url: str = TELEMETRY_WS_URL, parent=None) -> None:
        super().__init__(parent)
        self._url = url
        self._ws = QWebSocket()
        self._ws.connected.connect(self.connected)
        self._ws.disconnected.connect(self.disconnected)
        self._ws.textMessageReceived.connect(self._on_message)
        self._running = False

    def run(self) -> None:
        self._running = True
        self._ws.open(QNetworkRequest(self._url))

    def stop(self) -> None:
        self._running = False
        self._ws.close()

    def _on_message(self, message: str) -> None:
        try:
            data = json.loads(message)
            self.message_received.emit(data)
        except Exception:
            pass


class RMSSlider(QSlider):
    """Slider tactil con barra de energia RMS integrada."""

    def __init__(self, parent=None) -> None:
        super().__init__(Qt.Orientation.Horizontal, parent)
        self.setRange(0, 100)
        self.setValue(50)
        self._rms: float = 0.0
        self.setSingleStep(2)
        self.setPageStep(10)
        self.setFixedHeight(28)
        self.setFixedWidth(200)

    def set_rms(self, value: float) -> None:
        self._rms = min(1.0, max(0.0, value))
        self.update()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        rms_w = max(1, int(w * self._rms / 100))
        rms_h = 4
        rms_y = self.height() - 8
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(74, 222, 128, 180))
        painter.drawRoundedRect(0, rms_y, rms_w, rms_h, 2, 2)


class ActionApprovalCard(QFrame):
    """Tarjeta de aprobacion/ejecucion de acciones en el Centro de Notificaciones."""

    approved = Signal(bool)

    def __init__(self, action_data: Dict[str, Any], parent=None) -> None:
        super().__init__(parent)
        self._action_data = action_data
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(4)

        top = QHBoxLayout()
        self._icon = QLabel("🛠️")
        self._icon.setStyleSheet("font-size: 14px;")
        top.addWidget(self._icon)

        title = QLabel(self._action_data.get("tool", "Accion"))
        title.setStyleSheet(theme_engine.current_as_label_css(11, True))
        top.addWidget(title)

        top.addStretch()

        risk = self._action_data.get("risk_level", "safe")
        risk_label = QLabel(risk.upper())
        risk_label.setStyleSheet(f"color: {'#ef4444' if risk in ('high','critical') else '#facc15' if risk == 'medium' else '#22c55e'}; font-size: 10px; font-weight: bold;")
        top.addWidget(risk_label)

        layout.addLayout(top)

        prompt = self._action_data.get("confirmation_prompt") or self._action_data.get("description", "")
        body = QLabel(str(prompt))
        body.setStyleSheet(theme_engine.current_as_label_css(9, False, "#94a3bc"))
        body.setWordWrap(True)
        layout.addWidget(body)

        buttons = QHBoxLayout()
        self._approve_btn = QPushButton("Aprobar")
        self._approve_btn.setStyleSheet(f"background: {theme_engine.current.primary}; color: white; border-radius: 6px; padding: 4px 12px; font-size: 10px;")
        self._approve_btn.clicked.connect(lambda: self.approved.emit(True))
        buttons.addWidget(self._approve_btn)

        self._reject_btn = QPushButton("Rechazar")
        self._reject_btn.setStyleSheet(f"background: {theme_engine.current.surface_variant}; color: white; border-radius: 6px; padding: 4px 12px; font-size: 10px;")
        self._reject_btn.clicked.connect(lambda: self.approved.emit(False))
        buttons.addWidget(self._reject_btn)

        layout.addLayout(buttons)


class AlertCard(QFrame):
    """Tarjeta de alerta en el centro de notificaciones."""

    def __init__(self, alert: Dict[str, Any], parent=None) -> None:
        super().__init__(parent)
        self._alert = alert
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(6)

        level = self._alert.get("level", "info")
        icon_map = {
            "info": "ℹ️",
            "warning": "⚠️",
            "error": "❌",
            "success": "✅",
        }
        icon = icon_map.get(level, "🔔")
        self._icon = QLabel(icon)
        self._icon.setStyleSheet("font-size: 14px;")
        layout.addWidget(self._icon)

        v = QVBoxLayout()
        title = QLabel(f"Alerta {level.upper()}")
        title.setStyleSheet(theme_engine.current_as_label_css(10, True))
        v.addWidget(title)
        body = QLabel(str(self._alert.get("message", "")))
        body.setStyleSheet(theme_engine.current_as_label_css(9, False, "#94a3bc"))
        body.setWordWrap(True)
        v.addWidget(body)
        layout.addLayout(v)

        ts = self._alert.get("timestamp")
        time_str = datetime.fromtimestamp(ts).strftime("%H:%M:%S") if isinstance(ts, (int, float)) else ""
        self._time = QLabel(time_str)
        self._time.setStyleSheet(theme_engine.current_as_label_css(8, False, "#64748a"))
        layout.addWidget(self._time)


class CaelestiaDrawer(QWidget):
    """Desplegable lateral con Quick Settings, sliders, telemetria y notificaciones.

    Animacion de deslizamiento horizontal con QPropertyAnimation,
    tema Material You aplicado dinamicamente vía theme_engine.
    """

    drawer_opened = Signal()
    drawer_closed = Signal()

    def __init__(self, parent=None, drawer_width: int = 320) -> None:
        super().__init__(parent)
        self._drawer_width = drawer_width
        self._is_open = False
        self._animating: bool = False
        self._notifications: List[NotificationData] = []
        self._alerts: List[Dict[str, Any]] = []
        self._quick_toggles: Dict[str, QuickToggleButton] = {}
        self._setup_ui()
        self._setup_animation()
        self._start_telemetry()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        header = QHBoxLayout()
        header.setContentsMargins(16, 12, 16, 12)
        title = QLabel("AURA Quick Settings")
        title.setStyleSheet(theme_engine.current_as_header_css())
        header.addWidget(title)
        header.addStretch()
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(24, 24)
        close_btn.clicked.connect(self.hide_drawer)
        header.addWidget(close_btn)
        layout.addLayout(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QFrame()
        cl = QVBoxLayout(content)

        self._build_quick_section(cl)
        self._vol_slider = RMSSlider()
        cl.addWidget(self._vol_slider)
        self._add_label(cl, "Volumen Maestro")
        self._mic_slider = RMSSlider()
        cl.addWidget(self._mic_slider)
        self._add_label(cl, "Micrófono")

        self._media = MediaPlayerWidget()
        self._media.setFixedHeight(80)
        cl.addWidget(self._media)

        self._telemetry = SystemTelemetryGauge()
        self._telemetry.setFixedHeight(80)
        cl.addWidget(self._telemetry)

        self._weather = WeatherWidget()
        self._weather.setFixedHeight(100)
        cl.addWidget(self._weather)

        self._add_label(cl, "Alertas del Sistema")
        self._alerts_container = QFrame()
        self._alerts_layout = QVBoxLayout(self._alerts_container)
        self._alerts_layout.setContentsMargins(0, 0, 0, 0)
        self._alerts_layout.setSpacing(4)
        cl.addWidget(self._alerts_container)

        self._add_label(cl, "Acciones del Sistema")
        self._actions_container = QFrame()
        self._actions_layout = QVBoxLayout(self._actions_container)
        self._actions_layout.setContentsMargins(0, 0, 0, 0)
        self._actions_layout.setSpacing(4)
        cl.addWidget(self._actions_container)

        self._add_label(cl, "Memoria y RAG")
        memory_controls = QHBoxLayout()
        self._memory_search_input = QLineEdit()
        self._memory_search_input.setPlaceholderText("Buscar recuerdos...")
        self._memory_search_input.setStyleSheet(theme_engine.current_as_input_css())
        self._memory_search_input.returnPressed.connect(self._search_memory)
        memory_controls.addWidget(self._memory_search_input)
        search_btn = QPushButton("🔍")
        search_btn.setFixedSize(28, 28)
        search_btn.setStyleSheet(f"background: {theme_engine.current.primary}; color: white; border-radius: 6px;")
        search_btn.clicked.connect(self._search_memory)
        memory_controls.addWidget(search_btn)
        cl.addLayout(memory_controls)

        self._memory_results_container = QFrame()
        self._memory_results_layout = QVBoxLayout(self._memory_results_container)
        self._memory_results_layout.setContentsMargins(0, 0, 0, 0)
        self._memory_results_layout.setSpacing(4)
        cl.addWidget(self._memory_results_container)

        add_memory_btn = QPushButton("➕ Agregar Nota")
        add_memory_btn.setStyleSheet(theme_engine.button_css("tonal"))
        add_memory_btn.clicked.connect(self._add_memory_dialog)
        cl.addWidget(add_memory_btn)

        self._add_label(cl, "Swarm y Auto-Recuperación")
        self._swarm_status_label = QLabel("Swarm: --")
        self._swarm_status_label.setStyleSheet(theme_engine.current_as_label_css(10, False, "#94a3bc"))
        cl.addWidget(self._swarm_status_label)

        self._healing_btn = QPushButton("🔧 Recuperar Sistema")
        self._healing_btn.setStyleSheet(theme_engine.button_css("outlined"))
        self._healing_btn.clicked.connect(self._recover_swarm)
        cl.addWidget(self._healing_btn)

        cl.addStretch()

        scroll.setWidget(content)
        layout.addWidget(scroll)
        self.setStyleSheet(theme_engine.current_as_glass_css())

    def _add_label(self, parent_layout: QVBoxLayout, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(theme_engine.current_as_label_css(10, False, "#94a3bc"))
        parent_layout.addWidget(lbl)
        return lbl

    def _build_quick_section(self, parent_layout: QVBoxLayout) -> QFrame:
        frame = QFrame()
        frame.setObjectName("QuickSection")
        fl = QGridLayout(frame)
        fl.setContentsMargins(12, 8, 12, 8)

        toggles = [
            ("AI Local", "💽"),
            ("WebRTC", "📡"),
            ("Modo Noche", "🌙"),
            ("Swarm Monitor", "🐝"),
            ("Bloqueo", "🔒"),
        ]
        for idx, (label, icon) in enumerate(toggles):
            d = QuickToggleDef(label=label, icon=icon, section="system", active=False)
            btn = QuickToggleButton(d)
            self._quick_toggles[label] = btn
            fl.addWidget(btn, idx // 2, idx % 2)

        parent_layout.addWidget(frame)
        return frame

    def _setup_animation(self) -> None:
        self._anim = QPropertyAnimation(self, b"pos")
        self._anim.setDuration(350)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def _parent_width(self) -> int:
        if parent := self.parentWidget():
            return parent.width()
        return 400

    def _start_telemetry(self) -> None:
        self._telemetry_thread = QThread()
        self._telemetry_worker = TelemetryWorker()
        self._telemetry_worker.moveToThread(self._telemetry_thread)
        self._telemetry_thread.started.connect(self._telemetry_worker.run)
        self._telemetry_worker.message_received.connect(self._on_telemetry_message)
        self._telemetry_worker.connected.connect(self._on_telemetry_connected)
        self._telemetry_worker.disconnected.connect(self._on_telemetry_disconnected)
        self._telemetry_thread.start()

    def _on_telemetry_connected(self) -> None:
        print("[Telemetry] WebSocket conectado")

    def _on_telemetry_disconnected(self) -> None:
        print("[Telemetry] WebSocket desconectado, reconectando en 2s...")
        threading.Timer(2.0, self._telemetry_worker.run).start()

    def _on_telemetry_message(self, data: Dict[str, Any]) -> None:
        try:
            cpu = float(data.get("cpu_percent", 0))
            ram = float(data.get("ram_percent", 0))
            self._telemetry._cpu = cpu
            self._telemetry._ram = ram
            self._telemetry.update()

            swarm = data.get("swarm_agents", [])
            if swarm:
                active = sum(1 for a in swarm if a.get("status") == "active")
                total = len(swarm)
                if "Swarm Monitor" in self._quick_toggles:
                    self._quick_toggles["Swarm Monitor"].set_active(active > 0)

            alerts = data.get("alerts", [])
            if alerts:
                new_alerts = alerts[len(self._alerts):]
                for alert in new_alerts:
                    self._add_alert_card(alert)
                self._alerts = alerts
        except Exception:
            pass

    def _add_alert_card(self, alert: Dict[str, Any]) -> None:
        card = AlertCard(alert)
        self._alerts_layout.addWidget(card)
        notif = NotificationData(
            title=f"Alerta {alert.get('level', 'info').upper()}",
            body=str(alert.get("message", "")),
            icon="🐝" if alert.get("level") == "error" else "🔔",
            timestamp=datetime.now().strftime("%H:%M:%S"),
        )
        self._notifications.append(notif)

    def add_action_card(self, action_data: Dict[str, Any]) -> None:
        card = ActionApprovalCard(action_data)
        card.approved.connect(lambda approved, data=action_data: self._execute_action(approved, data))
        self._actions_layout.addWidget(card)

    def _execute_action(self, approved: bool, action_data: Dict[str, Any]) -> None:
        if not approved:
            return
        import requests as req
        try:
            req.post(
                f"{action_data.get('base_url', 'http://127.0.0.1:8000')}/api/actions/execute",
                json={"tool": action_data.get("tool"), "params": action_data.get("params", {}), "approved": True},
                timeout=10,
            )
        except Exception:
            pass

    def show_drawer(self) -> None:
        if self._animating or self._is_open:
            return
        pw = self._parent_width()
        self._animating = True
        self.move(pw, 0)
        self.show()
        self._anim.setStartValue(QPoint(pw, 0))
        self._anim.setEndValue(QPoint(pw - self._drawer_width, 0))
        self._anim.finished.connect(self._on_show_finished, type=Qt.ConnectionType.SingleShotConnection)
        self._anim.start()
        self._is_open = True
        self.drawer_opened.emit()

    def _on_show_finished(self) -> None:
        self._animating = False

    def hide_drawer(self) -> None:
        if self._animating or not self._is_open:
            return
        pw = self._parent_width()
        self._animating = True
        self._anim.setStartValue(QPoint(pw - self._drawer_width, 0))
        self._anim.setEndValue(QPoint(pw, 0))
        self._anim.finished.connect(self._on_hide_finished, type=Qt.ConnectionType.SingleShotConnection)
        self._anim.start()
        self._is_open = False
        self.drawer_closed.emit()

    def _on_hide_finished(self) -> None:
        self._animating = False
        self.hide()

    def toggle(self) -> None:
        if self._is_open:
            self.hide_drawer()
        else:
            self.show_drawer()

    def _search_memory(self) -> None:
        query = self._memory_search_input.text().strip()
        if not query:
            return
        try:
            import requests as req
            resp = req.get(
                f"http://127.0.0.1:8000/api/memory/search",
                params={"q": query, "limit": 5},
                timeout=10,
            )
            data = resp.json() if resp.status_code == 200 else {}
            results = data.get("results", [])
            self._render_memory_results(results)
        except Exception:
            self._render_memory_results([])

    def _render_memory_results(self, results: List[Dict[str, Any]]) -> None:
        while self._memory_results_layout.count():
            item = self._memory_results_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        if not results:
            empty = QLabel("Sin recuerdos encontrados")
            empty.setStyleSheet(theme_engine.current_as_label_css(10, False, "#64748a"))
            self._memory_results_layout.addWidget(empty)
            return
        for mem in results:
            card = QFrame()
            card.setStyleSheet(f"background: {theme_engine.current.surface_variant}; border-radius: 8px; border: 1px solid {theme_engine.current.outline};")
            v = QVBoxLayout(card)
            v.setContentsMargins(8, 6, 8, 6)
            v.setSpacing(4)
            title = QLabel(mem.get("memory_type", "memory").upper())
            title.setStyleSheet(theme_engine.current_as_label_css(10, True))
            v.addWidget(title)
            body = QLabel(mem.get("text", ""))
            body.setStyleSheet(theme_engine.current_as_label_css(9, False, "#cbd5e1"))
            body.setWordWrap(True)
            v.addWidget(body)
            score = QLabel(f"Relevancia: {mem.get('relevance_score', 0):.2f} | Recencia: {mem.get('recency_score', 0):.2f}")
            score.setStyleSheet(theme_engine.current_as_label_css(8, False, "#64748a"))
            v.addWidget(score)
            self._memory_results_layout.addWidget(card)

    def _add_memory_dialog(self) -> None:
        text, ok = QInputDialog.getMultiLineText(self, "Nuevo Recuerdo", "Texto:")
        if ok and text.strip():
            try:
                import requests as req
                req.post(
                    "http://127.0.0.1:8000/api/memory/remember",
                    json={"text": text.strip(), "type": "semantic", "source": "desktop"},
                    timeout=10,
                )
            except Exception:
                pass

    def add_notification(self, data: NotificationData) -> None:
        self._notifications.append(data)

    def _recover_swarm(self) -> None:
        try:
            import requests as req
            req.post("http://127.0.0.1:8000/api/swarm/recover", json={"module": "self_healing", "reason": "manual_trigger"}, timeout=10)
        except Exception:
            pass

    def update_swarm_status(self, status: Dict[str, Any]) -> None:
        try:
            swarm = status.get("swarm", {})
            healing = status.get("self_healing", {})
            agents = swarm.get("agents", [])
            active = sum(1 for a in agents if a.get("status") == "active")
            total = len(agents)
            critical = healing.get("critical", 0)
            self._swarm_status_label.setText(f"Swarm: {active}/{total} agentes | Críticos: {critical}")
        except Exception:
            pass
