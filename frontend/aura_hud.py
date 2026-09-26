"""AuraHUD — Interfaz grafica flotante Material 3 con Caelestia Shell.

Ventana frameless y translucida con:
- TopStatusBar: barra de workspaces Niri/Hyprland, estado WebRTC, clima, notificaciones
- VoiceIndicator: visualizador reactivo de estado de voz
- GlassDock: barra inferior con accesos directos + Caelestia Drawer
- Atajo global 'Alt+Space' para mostrar/ocultar
- Integracion con AuraWebRTCClient para /api/webrtc/offer

Uso: python frontend/aura_hud.py
"""

from __future__ import annotations

import os
import sys
import asyncio
import base64
import threading
from typing import Any, Optional

import requests

from PySide6.QtCore import Qt, QTimer, QPoint, QEvent, Signal, QObject, QBuffer, QIODevice
from PySide6.QtGui import QAction, QFont, QGuiApplication, QKeySequence, QShortcut, QColor
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QSystemTrayIcon, QMenu, QStyle, QInputDialog,
)

from frontend.webrtc.aura_webrtc_client import AuraWebRTCClient, VoiceStreamingEngine
from frontend.webrtc.aura_webrtc_utils import VoiceStateManager
from frontend.material_widgets import VoiceIndicator, SystemTelemetryGauge, WeatherWidget, ProfilePowerWidget, MediaPlayerWidget
from frontend.tiling_visualizer import TilingWorkspaceBar
from frontend.caelestia_drawer import CaelestiaDrawer
from frontend.theme_manager import theme_mgr
from frontend.caelestia_theme_engine import theme_engine

try:
    import pyaudio
except ImportError:
    pyaudio = None

DEFAULT_BASE_URL = os.getenv("AURA_API_URL", "http://localhost:8000")


class TopStatusBar(QWidget):
    """Barra superior con workspaces, estado WebRTC, clima y notificaciones."""

    drawer_toggled = Signal()

    def __init__(self, parent=None, weather_widget=None) -> None:
        super().__init__(parent)
        self._weather = weather_widget
        self._webrtc_status = "disconnected"
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)

        self._ws_bar = TilingWorkspaceBar()
        self._ws_bar.setFixedHeight(26)
        self._ws_bar.setStyleSheet("background: transparent;")
        layout.addWidget(self._ws_bar)
        layout.addStretch()

        self._webrtc_label = QLabel("OFFLINE")
        self._webrtc_label.setStyleSheet("color: #f87171; font-size: 10px; font-weight: bold;")
        layout.addWidget(self._webrtc_label)

        if self._weather:
            w = QWidget()
            wl = QHBoxLayout(w)
            wl.setContentsMargins(4, 0, 4, 0)
            wl.setSpacing(2)
            wl.addWidget(self._weather._icon)
            wl.addWidget(self._weather._city_label)
            wl.addWidget(self._weather._temp_label)
            w.setFixedHeight(22)
            layout.addWidget(w)

        self._notif_label = QLabel("🔔")
        self._notif_label.setStyleSheet("color: #94a3bc; font-size: 11px;")
        layout.addWidget(self._notif_label)

        self._drawer_btn = QPushButton("🎛️")
        self._drawer_btn.setFixedSize(24, 24)
        self._drawer_btn.setStyleSheet(
            "background: transparent; border: 1px solid rgba(255,255,255,0.2); "
            "border-radius: 6px; color: white; font-size: 11px;"
        )
        self._drawer_btn.clicked.connect(self.drawer_toggled.emit)
        layout.addWidget(self._drawer_btn)

        self.setFixedHeight(28)
        self.setStyleSheet(theme_mgr.glass_css("top_status_bar"))

    def set_webrtc_status(self, status: str) -> None:
        self._webrtc_status = status
        icons = {"connected": "ONLINE", "disconnected": "OFFLINE", "recording": "GRABANDO"}
        self._webrtc_label.setText(icons.get(status, "OFFLINE"))


class GlassDock(QWidget):
    """Barra flotante inferior estilo Glassmorphism."""

    mic_toggled = Signal(bool)
    swarm_requested = Signal()
    persona_requested = Signal()
    cli_requested = Signal()
    dashboard_requested = Signal()
    drawer_toggled = Signal()
    screenshot_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._microphone_active = False
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 10)
        layout.setSpacing(6)

        self._mic_btn = self._make_button("🔊 Mic", theme_mgr.palette.primary)
        self._mic_btn.clicked.connect(self._toggle_mic)
        layout.addWidget(self._mic_btn)

        self._swarm_btn = self._make_button("🐝 Swarm", theme_mgr.palette.tertiary)
        self._swarm_btn.clicked.connect(self.swarm_requested.emit)
        layout.addWidget(self._swarm_btn)

        self._persona_btn = self._make_button("👤", theme_mgr.palette.secondary)
        self._persona_btn.clicked.connect(self.persona_requested.emit)
        layout.addWidget(self._persona_btn)

        self._cli_btn = self._make_button("⚡ CLI", QColor(10, 190, 200))
        self._cli_btn.clicked.connect(self.cli_requested.emit)
        layout.addWidget(self._cli_btn)

        self._dashboard_btn = self._make_button("📊 Panel", QColor(16, 185, 129))
        self._dashboard_btn.clicked.connect(self.dashboard_requested.emit)
        layout.addWidget(self._dashboard_btn)

        self._screenshot_btn = self._make_button("📸 Foto", QColor(236, 72, 153))
        self._screenshot_btn.clicked.connect(self.screenshot_requested.emit)
        layout.addWidget(self._screenshot_btn)

        self._drawer_btn = self._make_button("🎛️", QColor(139, 92, 246))
        self._drawer_btn.clicked.connect(self.drawer_toggled.emit)
        layout.addWidget(self._drawer_btn)

        layout.addStretch()
        self.setFixedHeight(44)
        self.setStyleSheet(theme_mgr.glass_css("glass_dock"))

    def _make_button(self, text: str, color) -> QPushButton:
        if isinstance(color, QColor):
            c = f"rgba({color.red()},{color.green()},{color.blue()},0.4)"
        else:
            c = color
        btn = QPushButton(text)
        btn.setFixedSize(72, 32)
        btn.setStyleSheet(
            f"background: {c}; color: white; border: 1px solid {theme_mgr.palette.outline};"
            f"border-radius: 10px; font-size: 10px;"
        )
        return btn

    def _toggle_mic(self) -> None:
        self._microphone_active = not self._microphone_active
        self._mic_btn.setText("🔴 Mic" if self._microphone_active else "🔊 Mic")
        self.mic_toggled.emit(self._microphone_active)

    def set_mic_state(self, active: bool) -> None:
        self._microphone_active = active
        self._mic_btn.setText("🔴 Mic" if active else "🔊 Mic")


class TrayManager(QObject):
    """Gestor del icono de bandeja del sistema."""

    toggle_requested = Signal()
    dashboard_requested = Signal()
    mic_requested = Signal()
    drawer_requested = Signal()

    def __init__(self, app: QApplication) -> None:
        super().__init__()
        self._app = app
        self._tray = QSystemTrayIcon()
        self._tray.setIcon(app.style().standardIcon(QStyle.SP_ComputerIcon))
        self._tray.setToolTip("AURA HUD")

        menu = QMenu()
        show_action = QAction("Mostrar/Ocultar", menu)
        show_action.triggered.connect(self.toggle_requested.emit)
        menu.addAction(show_action)

        dashboard_action = QAction("Abrir Panel", menu)
        dashboard_action.triggered.connect(self.dashboard_requested.emit)
        menu.addAction(dashboard_action)

        mic_action = QAction("Alternar Mic", menu)
        mic_action.triggered.connect(self.mic_requested.emit)
        menu.addAction(mic_action)

        drawer_action = QAction("Quick Settings", menu)
        drawer_action.triggered.connect(self.drawer_requested.emit)
        menu.addAction(drawer_action)

        quit_action = QAction("Salir", menu)
        quit_action.triggered.connect(app.quit)
        menu.addAction(quit_action)

        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_activate)

    def show(self) -> None:
        self._tray.show()

    def _on_activate(self, reason) -> None:
        if reason == QSystemTrayIcon.Trigger.ActivationReason.DoubleClick:
            self.toggle_requested.emit()


class AuraHUD(QMainWindow):
    """Ventana HUD flotante con UI Material 3 + Caelestia Drawer."""

    def __init__(self, base_url: str = DEFAULT_BASE_URL) -> None:
        super().__init__()
        self.setWindowTitle("AURA HUD")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotTrackFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self._drag_position: Optional[QPoint] = None

        theme_engine.apply_preset("Dank Material Glass")

        self._client = AuraWebRTCClient(base_url=base_url)
        self._streamer: Optional[VoiceStreamingEngine] = None
        self._update_timer: Optional[QTimer] = None
        self._voice_mgr = VoiceStateManager()
        self._dashboard = None
        self._drawer: Optional[CaelestiaDrawer] = None

        self._build_ui()
        self._setup_tray()
        self._setup_hotkey()
        self._setup_timer()

    def _build_ui(self) -> None:
        main_container = QWidget()
        main_container.setObjectName("AuraHUDMain")
        main_container.setStyleSheet(theme_mgr.glass_css("AuraHUDMain"))
        layout = QVBoxLayout(main_container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._weather_widget = WeatherWidget()
        self._top_bar = TopStatusBar(weather_widget=self._weather_widget)
        layout.addWidget(self._top_bar)

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(16, 16, 16, 44)
        content_layout.setSpacing(12)

        self._profile_widget = ProfilePowerWidget()
        content_layout.addWidget(self._profile_widget)

        self._voice_indicator = VoiceIndicator(size=90)
        content_layout.addWidget(self._voice_indicator, alignment=Qt.AlignmentFlag.AlignCenter)

        self._media_widget = MediaPlayerWidget()
        content_layout.addWidget(self._media_widget)

        self._telemetry_widget = SystemTelemetryGauge()
        self._telemetry_widget.setFixedHeight(60)
        content_layout.addWidget(self._telemetry_widget)

        self._connect_btn = QPushButton("Conectar al Backend")
        self._connect_btn.setStyleSheet(theme_mgr.button_css("secondary"))
        self._connect_btn.clicked.connect(self.connect_backend)
        content_layout.addWidget(self._connect_btn)

        self._start_btn = QPushButton("Iniciar Microfono")
        self._start_btn.setStyleSheet(theme_mgr.button_css("primary"))
        self._start_btn.clicked.connect(self.toggle_streaming)
        content_layout.addWidget(self._start_btn)

        self._persona_btn = QPushButton("Seleccionar Personaje")
        self._persona_btn.setStyleSheet(theme_mgr.button_css("tertiary"))
        self._persona_btn.clicked.connect(self.select_persona)
        content_layout.addWidget(self._persona_btn)

        layout.addWidget(content)

        self._dock = GlassDock()
        layout.addWidget(self._dock)

        self.setCentralWidget(main_container)

        self._drawer = CaelestiaDrawer(self)
        self._drawer.hide()
        self._connect_drawer_signals()

    def _connect_drawer_signals(self) -> None:
        if self._drawer:
            self._top_bar.drawer_toggled.connect(self._drawer.toggle)
            self._dock.drawer_toggled.connect(self._drawer.toggle)
            self._dock.mic_toggled.connect(self.toggle_streaming)
            self._dock.dashboard_requested.connect(self.open_dashboard)
            self._dock.persona_requested.connect(self.select_persona)
            self._dock.screenshot_requested.connect(self.take_screenshot)

    def _setup_tray(self) -> None:
        self._tray_mgr = TrayManager(QApplication.instance())
        self._tray_mgr.show()
        self._tray_mgr.toggle_requested.connect(self.toggle_window)
        self._tray_mgr.dashboard_requested.connect(self.open_dashboard)
        self._tray_mgr.mic_requested.connect(lambda: self.toggle_streaming(not (self._streamer and self._streamer._running)))
        self._tray_mgr.drawer_requested.connect(lambda: self._drawer.toggle() if self._drawer else None)

    def _setup_hotkey(self) -> None:
        if sys.platform == "win32":
            try:
                import ctypes
                ctypes.windll.user32.RegisterHotKey(
                    int(self.winId()), 1, 0x01 | 0x8000, 0x20
                )
                ctypes.windll.user32.RegisterHotKey(
                    int(self.winId()), 2, 0x01 | 0x8000, 0x53
                )
                self.installEventFilter(self)
            except Exception:
                self._setup_fallback_hotkey()
        else:
            self._setup_fallback_hotkey()

    def _setup_fallback_hotkey(self) -> None:
        self._shortcut = QShortcut(QKeySequence("Alt+Space"), self)
        self._shortcut.activated.connect(self.toggle_window)
        self._screenshot_shortcut = QShortcut(QKeySequence("Alt+S"), self)
        self._screenshot_shortcut.activated.connect(self.take_screenshot)

    def _setup_timer(self) -> None:
        self._update_timer = QTimer()
        self._update_timer.timeout.connect(self._update_ui)
        self._update_timer.start(100)

    def eventFilter(self, obj: Any, event: QEvent) -> bool:
        if event.type() == QEvent.Type.KeyRelease:
            if hasattr(event, "key") and event.key() == 0x20:
                if event.modifiers() & Qt.KeyboardModifier.AltModifier:
                    self.toggle_window()
                    return True
        return super().eventFilter(obj, event)

    def _update_ui(self) -> None:
        self._voice_indicator.animate()
        if self._streamer and self._streamer._running:
            pass

    def open_dashboard(self) -> None:
        if self._dashboard is None:
            try:
                from frontend.dashboard_window import DashboardWindow
                self._dashboard = DashboardWindow(base_url=self._client.base_url)
            except Exception as exc:
                print(f"Dashboard error: {exc}")
                return
        self._dashboard.show_and_raise()

    def toggle_window(self) -> None:
        if self.isVisible():
            self.hide()
        else:
            self.show()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_position = event.globalPosition().toQPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self._drag_position is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toQPoint() - self._drag_position)
            event.accept()

    def connect_backend(self) -> None:
        url, ok = QInputDialog.getText(self, "Backend", "URL:", text=self._client.base_url)
        if ok and url:
            self._client.base_url = url.rstrip("/")
            self._top_bar.set_webrtc_status("connecting")
            self._connect_async()

    def _connect_async(self) -> None:
        async def _connect() -> None:
            try:
                result = await self._client.create_session()
                self._top_bar.set_webrtc_status("connected")
                await self._client.send_ice_candidate()
            except Exception:
                self._top_bar.set_webrtc_status("disconnected")
        loop = asyncio.new_event_loop()
        threading.Thread(target=lambda: loop.run_until_complete(_connect()), daemon=True).start()

    def toggle_streaming(self, active: Optional[bool] = None) -> None:
        if active is None:
            active = not (self._streamer and self._streamer._running)
        if active:
            if not self._client.is_connected:
                self._top_bar.set_webrtc_status("disconnected")
                return
            if pyaudio is None:
                return
            if self._streamer is None:
                self._streamer = VoiceStreamingEngine(self._client)
            self._streamer.start()
            self._start_btn.setText("Detener Microfono")
            self._dock.set_mic_state(True)
            self._voice_indicator.set_state("listening")
            self._top_bar.set_webrtc_status("recording")
            self._start_audio_ws()
        else:
            if self._streamer:
                self._streamer.stop()
            self._start_btn.setText("Iniciar Microfono")
            self._dock.set_mic_state(False)
            self._voice_indicator.set_state("listening")
            self._top_bar.set_webrtc_status("connected")

    def _start_audio_ws(self) -> None:
        if not self._client.session_id:
            return
        def _on_tts_chunk(chunk: bytes) -> None:
            self._voice_indicator.set_state("speaking")
            if self._streamer and self._streamer._output_stream:
                try:
                    self._streamer._output_stream.write(chunk)
                except Exception:
                    pass
        def _run():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self._client.connect_audio_websocket(on_tts_chunk=_on_tts_chunk))
            except Exception:
                pass
            finally:
                loop.close()
        threading.Thread(target=_run, daemon=True).start()

    def select_persona(self) -> None:
        personas = ["default", "asistente", "programador", "storyteller"]
        idx, ok = QInputDialog.getItem(self, "Personaje", "Selecciona:", personas, 0, False)
        if ok and idx >= 0:
            self._profile_widget.set_persona(personas[idx])

    def take_screenshot(self) -> None:
        try:
            screen = QGuiApplication.primaryScreen()
            if not screen:
                return
            pixmap = screen.grabWindow(0)
            buffer = QtCore.QBuffer()
            buffer.open(QtCore.QIODevice.WriteOnly)
            pixmap.save(buffer, "PNG")
            img_b64 = base64.b64encode(buffer.data().data()).decode("utf-8")
            buffer.close()
            if not self._client.session_id:
                return
            def _send():
                try:
                    requests.post(
                        f"{self._client.base_url}/api/vision/screenshot",
                        json={"image": img_b64, "session_id": self._client.session_id},
                        timeout=10,
                    )
                except Exception:
                    pass
            threading.Thread(target=_send, daemon=True).start()
        except Exception:
            pass


def main() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    hud = AuraHUD()
    hud.resize(280, 440)
    screen = QGuiApplication.primaryScreen()
    screen_geo = screen.availableGeometry()
    hud.move(screen_geo.width() - 300, screen_geo.height() - 480)
    hud.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
