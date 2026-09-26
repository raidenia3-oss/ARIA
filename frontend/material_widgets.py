"""Material 3 Widgets para AURA — Module 30 UI.

Widgets modulares con estilo Glassmorphism Material You:
- VoiceIndicator: visualizador de estado de voz
- ProfilePowerWidget: avatar + estado + botones rapidos
- WorldClockWidget: reloj digital + zonas horarias
- QuickUtilityWidget: zona drag & drop con conversion
- MediaPlayerWidget: estado audio WebRTC/TTS + barra RMS
- WeatherWidget: clima actual con cache local
- SystemTelemetryGauge: CPU/RAM/Batera en tiempo real
"""

from __future__ import annotations

import os
import json
from datetime import datetime
from typing import List, Optional

from zoneinfo import ZoneInfo

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont, QColor, QPainter, QPen, QBrush
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QProgressBar, QFrame,
)
from PySide6.QtGui import QDragEnterEvent, QDropEvent

from frontend.theme_manager import theme_mgr

try:
    import psutil
except ImportError:
    psutil = None

TIMEZONES: List[tuple] = [
    ("Local", "local"),
    ("UTC", "Etc/UTC"),
    ("America/New_York", "NYC"),
    ("Asia/Tokyo", "Tokyo"),
]

WEATHER_CACHE_FILE = os.path.expanduser("~/.aura_weather.json")


class VoiceIndicator(QWidget):
    """Visualizador reactivo del estado de voz (escuchando/procesando/hablando)."""

    def __init__(self, parent=None, size: int = 80) -> None:
        super().__init__(parent)
        self._state: str = "listening"
        self._energy: float = 0.0
        self._anim: float = 0.0
        self.setFixedSize(size, size)

    def set_state(self, state: str, energy: float = 0.0) -> None:
        self._state = state
        self._energy = energy
        self._anim = 1.0
        self.update()

    def animate(self) -> None:
        if self._anim > 0.01:
            self._anim *= 0.85
            self.update()

    def paintEvent(self, event) -> None:
        colors = {"listening": QColor(100, 180, 255), "processing": QColor(255, 200, 60), "speaking": QColor(255, 70, 70)}
        color = colors.get(self._state, colors["listening"])
        alpha = max(60, min(255, int(255 * (0.4 + 0.6 * self._anim))))
        color.setAlpha(alpha)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(color, 2))
        painter.setBrush(QBrush(color))
        extra = int(self._energy * 0.005 * self._anim * 30)
        rect = self.rect()
        painter.drawEllipse(rect.center(), 24 + extra, 24 + extra)

        color.setAlpha(255)
        painter.setPen(QPen(color))
        painter.setFont(QFont("Arial", 8))
        labels = {"listening": "Escuchando", "processing": "Procesando", "speaking": "Hablando"}
        painter.drawText(rect, Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter, labels.get(self._state, ""))


class ProfilePowerWidget(QWidget):
    """Avatar de Persona activa, estado del sistema y botones rapidos."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._persona_name: str = "AURA"
        self._system_status: str = "ready"
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(12)

        self._avatar = QLabel("A")
        self._avatar.setFixedSize(48, 48)
        self._avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._avatar.setStyleSheet(f"background: {theme_mgr.palette.primary}; color: white; border-radius: 24px; font-size: 20px; font-weight: bold;")

        info_layout = QVBoxLayout()
        self._name_label = QLabel(self._persona_name)
        self._name_label.setStyleSheet(theme_mgr.label_css(13, True))
        self._status_label = QLabel(f"Estado: {self._system_status}")
        self._status_label.setStyleSheet(theme_mgr.label_css(11, False, "#94a3bc"))
        info_layout.addWidget(self._name_label)
        info_layout.addWidget(self._status_label)

        btns_layout = QHBoxLayout()
        for label, color in [("Lock", "#f59e0b"), ("Restart", "#38bdfa"), ("Shutdown", "#f87171")]:
            btn = QPushButton(label)
            btn.setFixedHeight(28)
            btn.setStyleSheet(f"background: {color}; color: white; border: none; border-radius: 8px; padding: 4px 12px;")
            btns_layout.addWidget(btn)

        layout.addWidget(self._avatar)
        layout.addLayout(info_layout)
        layout.addLayout(btns_layout)
        layout.addStretch()
        self.setStyleSheet(theme_mgr.glass_card_css("profile_widget"))

    def set_persona(self, name: str) -> None:
        self._persona_name = name
        self._name_label.setText(name)

    def set_status(self, status: str) -> None:
        self._system_status = status
        self._status_label.setText(f"Estado: {status}")


class WorldClockWidget(QWidget):
    """Reloj digital principal + zonas horarias secundarias."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._setup_ui()
        self._timer = QTimer()
        self._timer.timeout.connect(self._update_time)
        self._timer.start(1000)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)

        self._main_clock = QLabel("00:00")
        self._main_clock.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._main_clock.setFont(QFont("Segoe UI", 28, QFont.Weight.Bold))
        self._main_clock.setStyleSheet(theme_mgr.label_css(24, True))
        layout.addWidget(self._main_clock)

        self._date_label = QLabel("")
        self._date_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._date_label.setStyleSheet(theme_mgr.label_css(11, False, "#94a3bc"))
        layout.addWidget(self._date_label)

        zones_layout = QHBoxLayout()
        self._zone_labels: List[QLabel] = []
        for _, tz_name in TIMEZONES[1:]:
            lbl = QLabel("--:--")
            lbl.setStyleSheet(theme_mgr.label_css(11, False, "#cbd5e1"))
            zones_layout.addWidget(lbl)
            self._zone_labels.append(lbl)
        layout.addLayout(zones_layout)
        self.setStyleSheet(theme_mgr.glass_card_css("clock_widget"))

    def _update_time(self) -> None:
        now = datetime.now()
        self._main_clock.setText(now.strftime("%H:%M"))
        self._date_label.setText(now.strftime("%A, %d %B"))

        for i, (_, tz_name) in enumerate(TIMEZONES[1:]):
            if i >= len(self._zone_labels):
                break
            try:
                if tz_name == "local":
                    tz_time = now
                else:
                    tz_time = now.astimezone(ZoneInfo(tz_name))
                self._zone_labels[i].setText(tz_time.strftime("%H:%M"))
            except Exception:
                pass


class QuickUtilityWidget(QWidget):
    """Zona drag & drop para archivos PNG/JPG/PDF con conversion a WEBP."""

    SUPPORTED_EXTS = {".png", ".jpg", ".jpeg", ".pdf"}

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self._dropped_file: Optional[str] = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)

        self._drop_zone = QFrame()
        self._drop_zone.setMinimumHeight(100)
        self._drop_zone.setFrameShape(QFrame.Shape.StyledPanel)
        self._drop_zone.setStyleSheet(f"""
            QFrame {{ background: rgba(40, 40, 60, 0.4); border: 2px dashed {theme_mgr.palette.outline}; border-radius: 12px; }}
        """)
        drop_layout = QVBoxLayout(self._drop_zone)
        self._drop_label = QLabel("Arrastra PNG, JPG o PDF aqui")
        self._drop_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._drop_label.setStyleSheet(theme_mgr.label_css(12, False, "#94a3bc"))
        drop_layout.addWidget(self._drop_label)
        layout.addWidget(self._drop_zone)

        btns = QHBoxLayout()
        self._convert_btn = QPushButton("Convertir a WEBP")
        self._convert_btn.clicked.connect(self._on_convert)
        btns.addWidget(self._convert_btn)
        self._rag_btn = QPushButton("Procesar con RAG")
        self._rag_btn.clicked.connect(self._on_rag)
        btns.addWidget(self._rag_btn)
        layout.addLayout(btns)
        self.setStyleSheet(theme_mgr.glass_card_css("quick_widget"))

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragMoveEvent(self, event) -> None:
        event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls:
                path = urls[0].toLocalFile()
                ext = os.path.splitext(path)[1].lower()
                if ext in self.SUPPORTED_EXTS:
                    self._dropped_file = path
                    self._drop_label.setText(os.path.basename(path))
                else:
                    self._drop_label.setText(f"Tipo no soportado: {ext}")
        event.acceptProposedAction()

    def _on_convert(self) -> None:
        if self._dropped_file:
            self._drop_label.setText(f"Convirtiendo: {os.path.basename(self._dropped_file)}")

    def _on_rag(self) -> None:
        if self._dropped_file:
            self._drop_label.setText(f"Procesando con RAG: {os.path.basename(self._dropped_file)}")


class MediaPlayerWidget(QWidget):
    """Visualizador de estado de audio WebRTC/TTS con barra RMS y controles."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._is_speaking: bool = False
        self._rms_value: float = 0.0
        self._is_playing: bool = False
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(12)

        self._status_icon = QLabel("🔊")
        self._status_icon.setStyleSheet("font-size: 20px;")
        layout.addWidget(self._status_icon)

        self._rms_bar = QProgressBar()
        self._rms_bar.setRange(0, 1000)
        self._rms_bar.setFixedHeight(16)
        self._rms_bar.setTextVisible(False)
        self._rms_bar.setStyleSheet("""
            QProgressBar { border: none; border-radius: 8px; background: rgba(255,255,255,0.1); }
            QProgressBar::chunk { background: linear-gradient(90deg, #4f46e5, #8b5cf6); border-radius: 8px; }
        """)
        layout.addWidget(self._rms_bar)

        self._play_btn = QPushButton("▶")
        self._play_btn.setFixedSize(28, 28)
        self._play_btn.clicked.connect(self._toggle_play)
        layout.addWidget(self._play_btn)

        self._vol_slider = QSlider()
        self._vol_slider.setOrientation(Qt.Orientation.Horizontal)
        self._vol_slider.setRange(0, 100)
        self._vol_slider.setValue(70)
        self._vol_slider.setFixedWidth(80)
        layout.addWidget(self._vol_slider)
        self.setStyleSheet(theme_mgr.glass_card_css("media_widget"))

    def update_audio(self, is_speaking: bool, rms: float) -> None:
        self._is_speaking = is_speaking
        self._rms_value = rms
        self._rms_bar.setValue(int(rms * 100))
        self._status_icon.setText("🎤" if is_speaking else "🔇")
        self._is_playing = is_speaking

    def _toggle_play(self) -> None:
        self._is_playing = not self._is_playing
        self._play_btn.setText("⏸" if self._is_playing else "▶")


class WeatherWidget(QWidget):
    """Panel de clima actual con cache local."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._temp: float = 22.0
        self._description: str = "Despejado"
        self._humidity: int = 45
        self._wind: float = 8.5
        self._city: str = "AURA HQ"
        self._setup_ui()
        self._timer = QTimer()
        self._timer.timeout.connect(self._refresh_weather)
        self._timer.start(60000)
        self._load_cache()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)

        top = QHBoxLayout()
        self._icon = QLabel(theme_mgr.get_solar_icon())
        self._icon.setStyleSheet("font-size: 24px;")
        top.addWidget(self._icon)
        self._temp_label = QLabel(f"{int(self._temp)}°C")
        self._temp_label.setStyleSheet(theme_mgr.label_css(20, True))
        top.addWidget(self._temp_label)
        top.addStretch()
        self._city_label = QLabel(self._city)
        self._city_label.setStyleSheet(theme_mgr.label_css(11, False, "#94a3bc"))
        top.addWidget(self._city_label)
        layout.addLayout(top)

        self._desc_label = QLabel(self._description)
        self._desc_label.setStyleSheet(theme_mgr.label_css(13))
        layout.addWidget(self._desc_label)

        details = QHBoxLayout()
        self._humidity_label = QLabel(f"💧 {self._humidity}%")
        self._humidity_label.setStyleSheet(theme_mgr.label_css(11, False, "#cbd5e1"))
        details.addWidget(self._humidity_label)
        self._wind_label = QLabel(f"💨 {self._wind} m/s")
        self._wind_label.setStyleSheet(theme_mgr.label_css(11, False, "#cbd5e1"))
        details.addWidget(self._wind_label)
        self._time_label = QLabel(datetime.now().strftime("%H:%M"))
        self._time_label.setStyleSheet(theme_mgr.label_css(11, False, "#94a3bc"))
        details.addWidget(self._time_label)
        layout.addLayout(details)
        self.setStyleSheet(theme_mgr.glass_card_css("weather_widget"))

    def _load_cache(self) -> None:
        try:
            with open(WEATHER_CACHE_FILE) as f:
                data = json.load(f)
                self._temp = data.get("temp", self._temp)
                self._description = data.get("description", self._description)
                self._humidity = data.get("humidity", self._humidity)
                self._wind = data.get("wind", self._wind)
                self._city = data.get("city", self._city)
                self._update_display()
        except Exception:
            self._update_display()

    def _save_cache(self) -> None:
        try:
            with open(WEATHER_CACHE_FILE, "w") as f:
                json.dump({
                    "temp": self._temp, "description": self._description,
                    "humidity": self._humidity, "wind": self._wind,
                    "city": self._city, "updated_at": datetime.now().isoformat(),
                }, f)
        except Exception:
            pass

    def _update_display(self) -> None:
        self._icon.setText(theme_mgr.get_solar_icon())
        self._temp_label.setText(f"{int(self._temp)}°C")
        self._desc_label.setText(self._description)
        self._humidity_label.setText(f"💧 {self._humidity}%")
        self._wind_label.setText(f"💨 {self._wind} m/s")
        self._city_label.setText(self._city)
        self._time_label.setText(datetime.now().strftime("%H:%M"))
        self._save_cache()

    def _refresh_weather(self) -> None:
        self._update_display()


class SystemTelemetryGauge(QWidget):
    """Indicadores de CPU %, RAM % y Batería % en tiempo real usando psutil."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._cpu: float = 0.0
        self._ram: float = 0.0
        self._battery: float = 0.0
        self._setup_ui()
        self._timer = QTimer()
        self._timer.timeout.connect(self._update_telemetry)
        self._timer.start(500)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        labels = [("CPU", "#4f46e5"), ("RAM", "#06b6d4"), ("BAT", "#f59e0b")]
        for name, color in labels:
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(0)
            bar.setTextVisible(True)
            bar.setFormat(f"{name} %v%")
            bar.setFixedHeight(16)
            bar.setStyleSheet(f"""
                QProgressBar {{ border: none; border-radius: 8px; background: rgba(255,255,255,0.1); text-align: center; }}
                QProgressBar::chunk {{ background: {color}; border-radius: 8px; }}
            """)
            layout.addWidget(bar)

        children = [c for c in layout.children() if isinstance(c, QProgressBar)]
        self._bars = children
        self.setStyleSheet(theme_mgr.glass_card_css("telemetry_widget"))

    def _update_telemetry(self) -> None:
        if psutil is None:
            return
        self._cpu = psutil.cpu_percent(interval=0.1)
        self._ram = psutil.virtual_memory().percent
        battery = psutil.sensors_battery()
        self._battery = battery.percent if battery else 0.0

        for i, val in enumerate([self._cpu, self._ram, self._battery]):
            if i < len(self._bars):
                self._bars[i].setValue(int(val))
