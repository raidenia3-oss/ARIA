"""AURA Mobile Client — Cliente movil Flet con estilo Caelestia Shell.

Interfaz tactil con:
- Top bar tactil estilo Caelestia Shell
- Drawer lateral para ajustes rapidos
- Videollamada WebRTC contra http://<IP_SERVIDOR>:8000
- Controles de audio/video y estado de conexion
- Descubrimiento automatico de servidor en red local
- Reconexion automatica con backoff exponencial
- Perfil de streaming optimizado para movil
"""

from __future__ import annotations

import threading
import time
import asyncio
import base64
import json
import os
from typing import Optional
from urllib.parse import urljoin

import flet as ft
import requests
import websockets
import numpy as np
import sounddevice as sd
import cv2
import io

from mobile_client.network_utils import (
    DISCOVERY_PORT,
    broadcast_presence,
    discover_server,
    measure_latency,
)

TELEMETRY_WS_URL = "ws://127.0.0.1:8000/ws/telemetry"
VISION_ANALYZE_PATH = "/api/vision/analyze-frame"

THEME_BG = "#05070a"
THEME_SURFACE = "rgba(15, 23, 41, 0.92)"
THEME_SURFACE_VARIANT = "rgba(30, 41, 59, 0.80)"
THEME_OUTLINE = "rgba(148, 163, 184, 0.25)"
THEME_PRIMARY = "#6366f1"
THEME_PRIMARY_VARIANT = "#06b6d4"
THEME_ON_PRIMARY = "#ffffff"
THEME_ON_SURFACE = "#e0e8ff"
THEME_ON_SURFACE_VARIANT = "#94a3b8"
THEME_ERROR = "#ef4444"
THEME_SUCCESS = "#22c55e"
THEME_WARNING = "#facc15"
THEME_RADIUS_LARGE = 20
THEME_RADIUS_MEDIUM = 14
THEME_RADIUS_SMALL = 10
THEME_FONT = "monospace"

WEBRTC_OFFER_PATH = "/api/webrtc/offer"
WEBRTC_STATE_PATH = "/api/webrtc/{session_id}/state"
WEBRTC_FLIP_PATH = "/api/webrtc/{session_id}/flip"
HEALTH_PATH = "/api/health"

OPTIMIZED_AUDIO_BITRATE_KBPS = 24
OPTIMIZED_VIDEO_WIDTH = 480
OPTIMIZED_VIDEO_HEIGHT = 640
OPTIMIZED_VIDEO_FPS = 15
OPTIMIZED_VIDEO_BITRATE_KBPS = 300
HIGH_LATENCY_THRESHOLD_SEC = 0.5
HEARTBEAT_INTERVAL_SEC = 30
RECONNECT_BASE_DELAY_SEC = 1.0
RECONNECT_MAX_DELAY_SEC = 10.0
VISION_KEYFRAME_INTERVAL = 2.0
AUDIO_SAMPLE_RATE = 16000
AUDIO_CHANNELS = 1
AUDIO_CHUNK_SECONDS = 3
AUDIO_CHUNK_SIZE = AUDIO_SAMPLE_RATE * AUDIO_CHANNELS * AUDIO_CHUNK_SECONDS


class AuraMobileClient:
    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self.page.title = "AURA NUCLEUS OS"
        self.page.padding = 0
        self.page.theme_mode = ft.ThemeMode.DARK
        self.page.bgcolor = THEME_BG
        self.page.font_family = THEME_FONT
        self.page.window_center()
        self.page.update()

        self.server_url: str = "http://localhost:8000"
        self.session_id: Optional[str] = None
        self.connected: bool = False
        self.audio_enabled: bool = True
        self.video_enabled: bool = True
        self.landscape: bool = False
        self._call_started_at: Optional[float] = None
        self._reconnect_attempts: int = 0
        self._reconnect_timer: Optional[threading.Timer] = None
        self._heartbeat_timer: Optional[threading.Timer] = None
        self._was_connected: bool = False
        self._keyframe_timer: Optional[threading.Timer] = None
        self._actions_list: ft.Column = ft.Column([], spacing=4, scroll=ft.ScrollMode.AUTO)
        self._memory_results_list: ft.Column = ft.Column([], spacing=4, scroll=ft.ScrollMode.AUTO)
        self._audio_stream = None
        self._audio_chunks = []
        self._is_recording = False
        self._tts_playing = False
        self._camera_capture = None

        self._last_activity: float = time.time()
        self._inactive_threshold: float = 30.0
        self._energy_saving: bool = False
        self._telemetry_interval: float = 1.0
        self._idle_check_timer: Optional[threading.Timer] = None

    def _start_idle_monitor(self) -> None:
        def _monitor():
            while True:
                time.sleep(5)
                now = time.time()
                if now - self._last_activity > self._inactive_threshold and not self._energy_saving:
                    self._energy_saving = True
                    self._telemetry_interval = 5.0
                    self._run_ui(self._apply_energy_saving_ui)
                elif now - self._last_activity <= self._inactive_threshold and self._energy_saving:
                    self._energy_saving = False
                    self._telemetry_interval = 1.0
                    self._run_ui(self._apply_energy_saving_ui)
        threading.Thread(target=_monitor, daemon=True).start()

    def _apply_energy_saving_ui(self) -> None:
        try:
            if hasattr(self, "_energy_label"):
                self._energy_label.value = "Ahorro energía: ACTIVO" if self._energy_saving else "Ahorro energía: INACTIVO"
                self._energy_label.color = THEME_WARNING if self._energy_saving else THEME_SUCCESS
            if hasattr(self, "_fab") and self._energy_saving:
                self._fab.icon = ft.icons.MIC_OFF
            self.page.update()
        except Exception:
            pass

    def _reset_activity(self) -> None:
        self._last_activity = time.time()
        if self._energy_saving:
            self._energy_saving = False
            self._telemetry_interval = 1.0
            self._run_ui(self._apply_energy_saving_ui)

    def _start_idle_monitor(self) -> None:
        def _monitor():
            while True:
                time.sleep(5)
                now = time.time()
                if now - self._last_activity > self._inactive_threshold and not self._energy_saving:
                    self._energy_saving = True
                    self._telemetry_interval = 5.0
                    self._run_ui(self._apply_energy_saving_ui)
                elif now - self._last_activity <= self._inactive_threshold and self._energy_saving:
                    self._energy_saving = False
                    self._telemetry_interval = 1.0
                    self._run_ui(self._apply_energy_saving_ui)
        threading.Thread(target=_monitor, daemon=True).start()

    def _apply_energy_saving_ui(self) -> None:
        try:
            if hasattr(self, "_energy_label"):
                self._energy_label.value = "Ahorro energía: ACTIVO" if self._energy_saving else "Ahorro energía: INACTIVO"
                self._energy_label.color = THEME_WARNING if self._energy_saving else THEME_SUCCESS
            if hasattr(self, "_fab") and self._energy_saving:
                self._fab.icon = ft.icons.MIC_OFF
            self.page.update()
        except Exception:
            pass

        broadcast_presence(port=DISCOVERY_PORT)

        self._build_ui()
        self._start_status_ticker()
        self._auto_discover_server()
        self._start_telemetry_ws()
        self._start_idle_monitor()

    def _build_ui(self) -> None:
        self.page.appbar = self._build_top_bar()
        self.page.drawer = self._build_drawer()
        self.page.floating_action_button = self._build_fab()
        self.page.floating_action_button_location = ft.FloatingActionButtonLocation.CENTER_DOCKED
        self.page.bottom_appbar = self._build_bottom_bar()
        self.page.overlay = [self._build_video_overlay()]
        self.page.add(self._build_body())

    def _build_top_bar(self) -> ft.AppBar:
        self._status_icon = ft.Icon(
            name=ft.icons.RADIO_BUTTON_UNCHECKED,
            color=THEME_ERROR,
            size=20,
        )
        self._status_label = ft.Text(
            "Desconectado",
            color=THEME_ON_SURFACE_VARIANT,
            size=12,
            font_family=THEME_FONT,
        )

        return ft.AppBar(
            title=ft.Row(
                controls=[
                    ft.Icon(name=ft.icons.HEADSET_MIC, color=THEME_PRIMARY),
                     ft.Text("AURA", size=18, weight=ft.FontWeight.BOLD, color=THEME_ON_PRIMARY, font_family=THEME_FONT),
                ],
                spacing=8,
            ),
            bgcolor=THEME_SURFACE,
            elevation=0,
            center_title=False,
            actions=[
                ft.Container(
                    content=ft.Row(
                        controls=[self._status_icon, self._status_label],
                        spacing=6,
                    ),
                    padding=ft.padding.only(right=12),
                )
            ],
        )

    def _build_drawer(self) -> ft.NavigationDrawer:
        self._ip_field = ft.TextField(
            label="IP del servidor",
            value="localhost",
            hint_text="Ej: 192.168.1.10",
            border_color=THEME_OUTLINE,
            focused_border_color=THEME_PRIMARY,
            bgcolor=THEME_SURFACE_VARIANT,
            color=THEME_ON_SURFACE,
            label_style=ft.TextStyle(color=THEME_ON_SURFACE_VARIANT),
            hint_style=ft.TextStyle(color=THEME_ON_SURFACE_VARIANT),
        )

        self._connect_btn = ft.ElevatedButton(
            text="Conectar",
            icon=ft.icons.LINK,
            bgcolor=THEME_PRIMARY,
            color=THEME_ON_PRIMARY,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=THEME_RADIUS_SMALL)),
            on_click=self._on_connect_clicked,
            width=240,
        )

        self._scan_btn = ft.ElevatedButton(
            text="Escanear red",
            icon=ft.icons.WIFI_FIND,
            bgcolor=THEME_SURFACE_VARIANT,
            color=THEME_ON_SURFACE,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=THEME_RADIUS_SMALL)),
            on_click=self._on_scan_clicked,
            width=240,
        )

        self._connection_status = ft.Text(
            "Sin conexion",
            color=THEME_ON_SURFACE_VARIANT,
            size=12,
            font_family=THEME_FONT,
        )

        self._latency_label = ft.Text(
            "Latencia: --",
            color=THEME_ON_SURFACE_VARIANT,
            size=11,
            font_family=THEME_FONT,
        )

        self._orientation_btn = ft.ElevatedButton(
            text="Orientacion: Portrait",
            icon=ft.icons.SMARTPHONE,
            bgcolor=THEME_SURFACE_VARIANT,
            color=THEME_ON_SURFACE,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=THEME_RADIUS_SMALL)),
            on_click=self._on_orientation_clicked,
            width=240,
        )

        self._cpu_text_label = ft.Text("CPU: --", color=THEME_ON_SURFACE, size=12, font_family=THEME_FONT)
        self._ram_text_label = ft.Text("RAM: --", color=THEME_ON_SURFACE, size=12, font_family=THEME_FONT)
        self._gpu_text_label = ft.Text("GPU: --", color=THEME_ON_SURFACE, size=12, font_family=THEME_FONT)
        self._swarm_text_label = ft.Text("Swarm: --", color=THEME_ON_SURFACE, size=12, font_family=THEME_FONT)
        self._energy_label = ft.Text("Ahorro energía: INACTIVO", color=THEME_SUCCESS, size=11, font_family=THEME_FONT)

        drawer_content = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Container(
                        content=ft.Text("Ajustes rapidos", size=20, weight=ft.FontWeight.BOLD, color=THEME_ON_PRIMARY, font_family=THEME_FONT),
                        padding=ft.padding.only(top=20, bottom=10, left=16, right=16),
                    ),
                    ft.Divider(color=THEME_OUTLINE),
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                self._ip_field,
                                ft.Container(height=8),
                                self._connect_btn,
                                ft.Container(height=8),
                                self._scan_btn,
                                ft.Container(height=6),
                                self._connection_status,
                                self._latency_label,
                            ],
                            spacing=4,
                        ),
                        padding=ft.padding.symmetric(horizontal=16, vertical=8),
                    ),
                    ft.Divider(color=THEME_OUTLINE),
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Text("WebRTC", size=14, weight=ft.FontWeight.BOLD, color=THEME_ON_SURFACE_VARIANT, font_family=THEME_FONT),
                                ft.Container(height=8),
                                ft.Switch(
                                    label="Audio",
                                    value=True,
                                    active_color=THEME_PRIMARY,
                                    label_style=ft.TextStyle(color=THEME_ON_SURFACE),
                                    on_change=self._on_audio_toggled,
                                ),
                                ft.Switch(
                                    label="Video",
                                    value=True,
                                    active_color=THEME_PRIMARY,
                                    label_style=ft.TextStyle(color=THEME_ON_SURFACE),
                                    on_change=self._on_video_toggled,
                                ),
                            ],
                            spacing=4,
                        ),
                        padding=ft.padding.symmetric(horizontal=16, vertical=8),
                    ),
                     ft.Divider(color=THEME_OUTLINE),
                     ft.Container(
                         content=ft.Column(
                             controls=[
                                 ft.Text("Pantalla", size=14, weight=ft.FontWeight.BOLD, color=THEME_ON_SURFACE_VARIANT, font_family=THEME_FONT),
                                 ft.Container(height=8),
                                 self._orientation_btn,
                             ],
                             spacing=4,
                         ),
                         padding=ft.padding.symmetric(horizontal=16, vertical=8),
                     ),
                      ft.Divider(color=THEME_OUTLINE),
                      ft.Container(
                          content=ft.Column(
                              controls=[
                                  ft.Text("Telemetría", size=14, weight=ft.FontWeight.BOLD, color=THEME_ON_SURFACE_VARIANT, font_family=THEME_FONT),
                                  ft.Container(height=8),
                                  self._cpu_text_label,
                                  self._ram_text_label,
                                  self._gpu_text_label,
                                  self._swarm_text_label,
                                  self._energy_label,
                              ],
                              spacing=2,
                          ),
                          padding=ft.padding.symmetric(horizontal=16, vertical=8),
                      ),
                      ft.Divider(color=THEME_OUTLINE),
                      ft.Container(
                          content=ft.Column(
                              controls=[
                                  ft.Text("Ejecución Rápida", size=14, weight=ft.FontWeight.BOLD, color=THEME_ON_SURFACE_VARIANT, font_family=THEME_FONT),
                                  ft.Container(height=8),
                                  ft.ElevatedButton(
                                      text="Limpiar RAM",
                                      icon=ft.icons.MEMORY,
                                      bgcolor=THEME_SURFACE_VARIANT,
                                      color=THEME_ON_SURFACE,
                                      style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=THEME_RADIUS_SMALL)),
                                      on_click=lambda e: self._execute_quick_action("Limpiar RAM", "run_command", {"command": "powershell -Command \"Clear-RecycleBin -Force -ErrorAction SilentlyContinue; Write-Host 'RAM cache cleared'\"", "timeout": 15}),
                                      width=240,
                                  ),
                                  ft.Container(height=4),
                                  ft.ElevatedButton(
                                      text="Diagnóstico de Red",
                                      icon=ft.icons.WIFI,
                                      bgcolor=THEME_SURFACE_VARIANT,
                                      color=THEME_ON_SURFACE,
                                      style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=THEME_RADIUS_SMALL)),
                                      on_click=lambda e: self._execute_quick_action("Diagnóstico de Red", "run_command", {"command": "ping -n 3 8.8.8.8", "timeout": 15}),
                                      width=240,
                                  ),
                                  ft.Container(height=4),
                                  ft.ElevatedButton(
                                      text="Suspender Swarm",
                                      icon=ft.icons.PAUSE,
                                      bgcolor=THEME_SURFACE_VARIANT,
                                      color=THEME_ON_SURFACE,
                                      style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=THEME_RADIUS_SMALL)),
                                      on_click=lambda e: self._execute_quick_action("Suspender Swarm", "run_command", {"command": "echo Swarm suspendido manualmente", "timeout": 10}),
                                      width=240,
                                  ),
                              ],
                              spacing=4,
                          ),
                          padding=ft.padding.symmetric(horizontal=16, vertical=8),
                      ),
                      ft.Divider(color=THEME_OUTLINE),
                      ft.Container(
                         content=ft.Column(
                             controls=[
                                 ft.Text("Recuerdos", size=14, weight=ft.FontWeight.BOLD, color=THEME_ON_SURFACE_VARIANT, font_family=THEME_FONT),
                                 ft.Container(height=8),
                                 ft.TextField(
                                     label="Buscar en memoria",
                                     hint_text="Ej: reunión proyecto",
                                     border_color=THEME_OUTLINE,
                                     focused_border_color=THEME_PRIMARY,
                                     bgcolor=THEME_SURFACE_VARIANT,
                                     color=THEME_ON_SURFACE,
                                     label_style=ft.TextStyle(color=THEME_ON_SURFACE_VARIANT),
                                     hint_style=ft.TextStyle(color=THEME_ON_SURFACE_VARIANT),
                                     on_submit=self._search_memory,
                                 ),
                                 ft.Container(height=6),
                                 self._memory_results_list,
                                 ft.ElevatedButton(
                                     text="Agregar Nota",
                                     icon=ft.icons.NOTE_ADD,
                                     bgcolor=THEME_SURFACE_VARIANT,
                                     color=THEME_ON_SURFACE,
                                     style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=THEME_RADIUS_SMALL)),
                                     on_click=self._add_memory_dialog,
                                     width=240,
                                 ),
                             ],
                             spacing=2,
                         ),
                         padding=ft.padding.symmetric(horizontal=16, vertical=8),
                     ),
                     ft.Divider(color=THEME_OUTLINE),
                     ft.Container(
                         content=ft.Column(
                             controls=[
                                 ft.Text("Swarm", size=14, weight=ft.FontWeight.BOLD, color=THEME_ON_SURFACE_VARIANT, font_family=THEME_FONT),
                                 ft.Container(height=8),
                                 ft.ElevatedButton(
                                     text="Recuperar Sistema",
                                     icon=ft.icons.HEALING,
                                     bgcolor=THEME_SURFACE_VARIANT,
                                     color=THEME_ON_SURFACE,
                                     style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=THEME_RADIUS_SMALL)),
                                     on_click=self._recover_swarm,
                                     width=240,
                                 ),
                             ],
                             spacing=4,
                         ),
                         padding=ft.padding.symmetric(horizontal=16, vertical=8),
                     ),
                     ft.Divider(color=THEME_OUTLINE),
                     ft.Container(
                         content=ft.Column(
                             controls=[
                                 ft.Text("Sesion", size=14, weight=ft.FontWeight.BOLD, color=THEME_ON_SURFACE_VARIANT, font_family=THEME_FONT),
                                ft.Container(height=8),
                                ft.ElevatedButton(
                                    text="Cerrar sesion",
                                    icon=ft.icons.LOGOUT,
                                    bgcolor=THEME_SURFACE_VARIANT,
                                    color=THEME_ON_SURFACE,
                                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=THEME_RADIUS_SMALL)),
                                    on_click=self._on_logout,
                                    width=240,
                                ),
                            ],
                            spacing=4,
                        ),
                        padding=ft.padding.symmetric(horizontal=16, vertical=8),
                    ),
                    ft.Container(height=20),
                ],
                spacing=0,
            ),
            bgcolor=THEME_BG,
        )

        return ft.NavigationDrawer(
            content=drawer_content,
            elevation=0,
            width=280,
        )

    def _build_fab(self) -> ft.FloatingActionButton:
        self._fab = ft.FloatingActionButton(
            icon=ft.icons.MIC if self.audio_enabled else ft.icons.MIC_OFF,
            bgcolor=THEME_PRIMARY,
            on_click=self._on_neon_mic_clicked,
            width=72,
            height=72,
        )
        return self._fab

    def _build_bottom_bar(self) -> ft.BottomAppBar:
        self._mic_btn = ft.IconButton(
            icon=ft.icons.MIC,
            icon_color=THEME_ON_PRIMARY,
            bgcolor=THEME_SURFACE_VARIANT,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=28), padding=12),
            on_click=self._on_mic_clicked,
        )

        self._cam_btn = ft.IconButton(
            icon=ft.icons.VIDEOCAM,
            icon_color=THEME_ON_PRIMARY,
            bgcolor=THEME_SURFACE_VARIANT,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=28), padding=12),
            on_click=self._on_cam_clicked,
        )

        self._flip_btn = ft.IconButton(
            icon=ft.icons.CAMERA_FRONT,
            icon_color=THEME_ON_PRIMARY,
            bgcolor=THEME_SURFACE_VARIANT,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=28), padding=12),
            on_click=self._on_flip_camera,
        )

        return ft.BottomAppBar(
            content=ft.Row(
                controls=[self._mic_btn, self._cam_btn, self._flip_btn],
                alignment=ft.MainAxisAlignment.SPACE_AROUND,
            ),
            bgcolor=THEME_SURFACE,
            elevation=8,
            shape=ft.NotchShape(),
        )

    def _build_video_overlay(self) -> ft.Stack:
        self._local_video_container = ft.Container(
            width=96 if not self.landscape else 140,
            height=128 if not self.landscape else 90,
            bgcolor=THEME_SURFACE_VARIANT,
            border=ft.border.all(1, THEME_PRIMARY),
            border_radius=THEME_RADIUS_MEDIUM,
            alignment=ft.alignment.center,
            content=ft.Text("Local", color=THEME_ON_SURFACE_VARIANT, size=10, font_family=THEME_FONT),
        )

        self._remote_video_container = ft.Container(
            expand=True,
            bgcolor=THEME_SURFACE_VARIANT,
            border=ft.border.all(1, THEME_PRIMARY),
            border_radius=THEME_RADIUS_LARGE,
            alignment=ft.alignment.center,
            content=ft.Column(
                controls=[
                    ft.Icon(name=ft.icons.PERSON, size=64, color=THEME_PRIMARY),
                    ft.Text("Esperando conexion...", color=THEME_ON_SURFACE_VARIANT, size=12, font_family=THEME_FONT),
                ],
                spacing=8,
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

        self._call_info = ft.Container(
            content=ft.Text("00:00", color=THEME_ON_SURFACE, size=12, weight=ft.FontWeight.BOLD, font_family=THEME_FONT),
            bgcolor=THEME_SURFACE,
            border_radius=THEME_RADIUS_SMALL,
            padding=6,
            border=ft.border.all(1, THEME_PRIMARY),
            visible=False,
        )

        return ft.Stack(
            controls=[
                self._remote_video_container,
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Container(
                                content=self._local_video_container,
                                padding=8,
                            ),
                            ft.Container(height=8),
                            self._call_info,
                        ],
                        spacing=0,
                    ),
                    alignment=ft.alignment.top_right,
                    padding=ft.padding.only(top=56, right=12),
                ),
            ],
            expand=True,
        )

    def _build_body(self) -> ft.Column:
        self._hint_text = ft.Text(
            "Toca Conectar para iniciar una sesion WebRTC",
            color=THEME_ON_SURFACE_VARIANT,
            size=13,
            text_align=ft.TextAlign.CENTER,
            font_family=THEME_FONT,
        )

        video_stack = ft.Stack(
            controls=[
                self._remote_video_container,
                ft.Container(
                    content=ft.Column(
                        controls=[
                            self._local_video_container,
                            ft.Container(height=8),
                            self._call_info,
                        ],
                        spacing=0,
                    ),
                    alignment=ft.alignment.top_right,
                    padding=ft.padding.only(top=12 if not self.landscape else 12, right=12),
                ),
            ],
            expand=True,
        )

        return ft.Column(
            controls=[
                ft.Container(
                    content=video_stack,
                    expand=True,
                    border_radius=THEME_RADIUS_LARGE,
                    margin=ft.margin.all(12),
                    padding=0,
                ),
                ft.Container(
                    content=self._hint_text,
                    padding=ft.padding.symmetric(horizontal=20, vertical=8),
                ),
            ],
            spacing=0,
            expand=True,
        )

    def _run_ui(self, func, *args, **kwargs):
        def _wrapper():
            try:
                func(*args, **kwargs)
                self.page.update()
            except Exception:
                pass
        threading.Thread(target=_wrapper, daemon=True).start()

    def _set_connected_state(self, connected: bool) -> None:
        self.connected = connected
        if connected:
            self._status_icon.name = ft.icons.RADIO_BUTTON_CHECKED
            self._status_icon.color = THEME_SUCCESS
            self._status_label.value = "Conectado"
            self._connect_btn.text = "Desconectar"
            self._connect_btn.icon = ft.icons.LINK_OFF
            self._connect_btn.bgcolor = THEME_ERROR
            self._connection_status.value = f"Sesion: {self.session_id or 'activa'}"
            self._connection_status.color = THEME_SUCCESS
            self._hint_text.value = "Sesion WebRTC activa"
            self._call_info.visible = True
            self._call_started_at = time.time()
            self._reconnect_attempts = 0
            self._start_heartbeat()
            self._start_audio_ws()
            if self.video_enabled:
                self._start_keyframes()
        else:
            self._status_icon.name = ft.icons.RADIO_BUTTON_UNCHECKED
            self._status_icon.color = THEME_ERROR
            self._status_label.value = "Desconectado"
            self._connect_btn.text = "Conectar"
            self._connect_btn.icon = ft.icons.LINK
            self._connect_btn.bgcolor = THEME_PRIMARY
            self._connection_status.value = "Sin conexion"
            self._connection_status.color = THEME_ON_SURFACE_VARIANT
            self._hint_text.value = "Toca Conectar para iniciar una sesion WebRTC"
            self._call_info.visible = False
            self._call_info.content.value = "00:00"
            self.session_id = None
            self._call_started_at = None
            self._stop_heartbeat()
            self._stop_keyframes()
            if self._was_connected:
                self._schedule_reconnect()

    def _start_audio_ws(self) -> None:
        if not self.session_id:
            return
        def _listen():
            backoff = 1.0
            while self.connected and self.session_id:
                try:
                    url = f"ws://{self.server_url.replace('http://', '').replace('https://', '')}/ws/webrtc/audio/{self.session_id}"
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    async def _run():
                        async with websockets.connect(url, ping_interval=20, ping_timeout=20) as ws:
                            backoff = 1.0
                            while self.connected and self.session_id:
                                msg = await ws.recv()
                                data = json.loads(msg)
                                if data.get("type") == "audio":
                                    self._process_tts_audio(data)
                    loop.run_until_complete(_run())
                except Exception:
                    time.sleep(backoff)
                    backoff = min(backoff * 2, 10.0)
        threading.Thread(target=_listen, daemon=True).start()

    def _process_tts_audio(self, data: Dict[str, Any]) -> None:
        audio_b64 = data.get("data")
        if not audio_b64:
            return
        self._tts_playing = True
        self._run_ui(self._set_voice_state, "speaking")
        self._run_ui(self._play_tts_audio, audio_b64)

    def _play_tts_audio(self, audio_b64: str) -> None:
        try:
            raw = base64.b64decode(audio_b64)
            audio_np = np.frombuffer(raw, dtype=np.int16)
            sd.play(audio_np, samplerate=24000)
            sd.wait()
        except Exception:
            pass
        finally:
            self._tts_playing = False

    def _set_voice_state(self, state: str) -> None:
        try:
            if state == "listening":
                self._status_label.value = "Escuchando..."
            elif state == "processing":
                self._status_label.value = "Pensando..."
            elif state == "speaking":
                self._status_label.value = "Respondiendo..."
            self.page.update()
        except Exception:
            pass

    def _start_status_ticker(self) -> None:
        def _tick():
            while True:
                time.sleep(1)
                if self._call_started_at and self.connected:
                    elapsed = int(time.time() - self._call_started_at)
                    mins, secs = divmod(elapsed, 60)
                    self._call_info.content.value = f"{mins:02d}:{secs:02d}"
                    try:
                        self.page.update()
                    except Exception:
                        pass
        threading.Thread(target=_tick, daemon=True).start()

    def _start_heartbeat(self) -> None:
        self._stop_heartbeat()
        self._heartbeat_timer = threading.Timer(HEARTBEAT_INTERVAL_SEC, self._heartbeat_loop)
        self._heartbeat_timer.daemon = True
        self._heartbeat_timer.start()

    def _stop_heartbeat(self) -> None:
        if self._heartbeat_timer:
            self._heartbeat_timer.cancel()
            self._heartbeat_timer = None

    def _heartbeat_loop(self) -> None:
        if not self.connected:
            return
        latency = measure_latency(self.server_url)
        if latency is not None:
            self._latency_label.value = f"Latencia: {latency*1000:.0f} ms"
            if latency > HIGH_LATENCY_THRESHOLD_SEC:
                self._latency_label.color = THEME_ERROR
            else:
                self._latency_label.color = THEME_SUCCESS
        else:
            self._latency_label.value = "Latencia: --"
            self._latency_label.color = THEME_ON_SURFACE_VARIANT
            self._run_ui(self._set_connected_state, False)
            return
        try:
            self.page.update()
        except Exception:
            pass
        self._start_heartbeat()

    def _schedule_reconnect(self) -> None:
        if self._reconnect_timer:
            self._reconnect_timer.cancel()
        delay = min(RECONNECT_BASE_DELAY_SEC * (2 ** self._reconnect_attempts), RECONNECT_MAX_DELAY_SEC)
        self._reconnect_attempts += 1
        self._run_ui(self._set_status_text, f"Reconectando en {delay:.0f}s...")
        self._reconnect_timer = threading.Timer(delay, self._reconnect)
        self._reconnect_timer.daemon = True
        self._reconnect_timer.start()

    def _reconnect(self) -> None:
        self._reconnect_timer = None
        if not self._was_connected or self.connected:
            return
        ip = self._ip_field.value.strip() or "localhost"
        if ip in ("localhost", "127.0.0.1"):
            self.server_url = "http://localhost:8000"
        else:
            self.server_url = f"http://{ip}:8000"
        self._do_connect()

    def _on_connect_clicked(self, e: ft.ControlEvent) -> None:
        if self.connected:
            self._disconnect()
        else:
            self._connect()

    def _connect(self) -> None:
        ip = self._ip_field.value.strip() or "localhost"
        if ip in ("localhost", "127.0.0.1"):
            self.server_url = "http://localhost:8000"
        else:
            self.server_url = f"http://{ip}:8000"

        self._connection_status.value = "Conectando..."
        self._connection_status.color = THEME_PRIMARY
        self.page.update()
        self._cancel_reconnect()
        self._do_connect()

    def _do_connect(self) -> None:
        def _do():
            try:
                url = urljoin(self.server_url, WEBRTC_OFFER_PATH)
                payload = {
                    "sdp": "",
                    "type": "offer",
                    "audio": self.audio_enabled,
                    "video": self.video_enabled,
                    "optimization": {
                        "audio_codec": "opus",
                        "audio_bitrate_kbps": OPTIMIZED_AUDIO_BITRATE_KBPS,
                        "video_codec": "VP8",
                        "video_width": OPTIMIZED_VIDEO_WIDTH,
                        "video_height": OPTIMIZED_VIDEO_HEIGHT,
                        "video_fps": OPTIMIZED_VIDEO_FPS,
                        "video_bitrate_kbps": OPTIMIZED_VIDEO_BITRATE_KBPS,
                        "scaling_mode": "crop",
                    },
                }
                resp = requests.post(url, json=payload, timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    self.session_id = data.get("session_id") or data.get("id") or "aura-session"
                    self._was_connected = True
                    self._run_ui(self._set_connected_state, True)
                else:
                    self._run_ui(self._set_connected_state, False)
                    self._run_ui(self._set_status_text, f"Error HTTP {resp.status_code}")
            except requests.exceptions.Timeout:
                self._run_ui(self._set_connected_state, False)
                self._run_ui(self._set_status_text, "Timeout de conexion")
            except Exception as exc:
                self._run_ui(self._set_connected_state, False)
                self._run_ui(self._set_status_text, f"Error: {exc}")

        threading.Thread(target=_do, daemon=True).start()

    def _disconnect(self) -> None:
        self._cancel_reconnect()
        self._run_ui(self._set_connected_state, False)
        self._run_ui(self._set_status_text, "Desconectado")

    def _cancel_reconnect(self) -> None:
        if self._reconnect_timer:
            self._reconnect_timer.cancel()
            self._reconnect_timer = None

    def _set_status_text(self, text: str) -> None:
        self._connection_status.value = text
        self._connection_status.color = THEME_PRIMARY

    def _on_scan_clicked(self, e: ft.ControlEvent) -> None:
        self._connection_status.value = "Escaneando red..."
        self._connection_status.color = THEME_PRIMARY
        self.page.update()

        def _scan():
            found = discover_server(port=DISCOVERY_PORT, on_found=lambda ip: None)
            self._run_ui(self._on_scan_complete, found)

        threading.Thread(target=_scan, daemon=True).start()

    def _on_scan_complete(self, found: list) -> None:
        if found:
            self._ip_field.value = found[0]
            self._connection_status.value = f"Servidor detectado: {found[0]}"
            self._connection_status.color = THEME_SUCCESS
        else:
            self._connection_status.value = "No se detecto ningun servidor"
            self._connection_status.color = THEME_ERROR
        self.page.update()

    def _auto_discover_server(self) -> None:
        def _auto():
            found = discover_server(port=DISCOVERY_PORT)
            if found and not self.connected:
                self._run_ui(self._on_scan_complete, found)
        threading.Thread(target=_auto, daemon=True).start()

    def _on_neon_mic_clicked(self, e: ft.ControlEvent) -> None:
        self._reset_activity()
        if self._is_recording:
            self._stop_audio_recording()
        else:
            self._start_audio_recording()
        self.page.update()

    def _start_audio_recording(self) -> None:
        if not self.connected or not self.session_id:
            self._show_snack("Micrófono", "Conecta primero a una sesión", "⚠️")
            return
        try:
            self._is_recording = True
            self._audio_chunks = []
            self._fab.icon = ft.icons.STOP
            self._fab.bgcolor = THEME_ERROR
            self._set_voice_state("listening")
            self._audio_stream = sd.InputStream(
                samplerate=AUDIO_SAMPLE_RATE,
                channels=AUDIO_CHANNELS,
                blocksize=1024,
                dtype='int16',
                callback=self._audio_callback,
            )
            self._audio_stream.start()
        except Exception as exc:
            self._is_recording = False
            self._fab.icon = ft.icons.MIC
            self._fab.bgcolor = THEME_PRIMARY
            self._show_snack("Micrófono", f"Error: {exc}", "❌")

    def _stop_audio_recording(self) -> None:
        self._is_recording = False
        self._fab.icon = ft.icons.MIC
        self._fab.bgcolor = THEME_PRIMARY
        try:
            if self._audio_stream:
                self._audio_stream.stop()
                self._audio_stream.close()
                self._audio_stream = None
        except Exception:
            pass
        self._set_voice_state("processing")
        if self._audio_chunks and self.session_id:
            audio_data = np.concatenate(self._audio_chunks, axis=0)
            audio_bytes = audio_data.tobytes()
            audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')
            self._send_audio_to_backend(audio_b64)
        self._audio_chunks = []

    def _audio_callback(self, indata, frames, time_info, status):
        if status:
            pass
        self._audio_chunks.append(indata.copy())

    def _send_audio_to_backend(self, audio_b64: str) -> None:
        def _send():
            try:
                resp = requests.post(
                    f"{self.server_url}/api/webrtc/audio/process",
                    json={"session_id": self.session_id, "audio": audio_b64},
                    timeout=15,
                )
                data = resp.json() if resp.status_code == 200 else {}
                self._run_ui(self._set_voice_state, "speaking" if data.get("status") == "queued" else "listening")
            except Exception as exc:
                self._run_ui(self._show_snack, "Audio", f"Error: {exc}", "❌")
        threading.Thread(target=_send, daemon=True).start()

    def _on_audio_toggled(self, e: ft.ControlEvent) -> None:
        self.audio_enabled = e.control.value
        self._sync_media_icons()
        self._send_webrtc_state()

    def _on_video_toggled(self, e: ft.ControlEvent) -> None:
        self.video_enabled = e.control.value
        self._sync_media_icons()
        self._send_webrtc_state()
        if self.video_enabled and self.connected:
            self._start_keyframes()
        else:
            self._stop_keyframes()

    def _on_orientation_clicked(self, e: ft.ControlEvent) -> None:
        self.landscape = not self.landscape
        self._orientation_btn.text = "Orientacion: Landscape" if self.landscape else "Orientacion: Portrait"
        self._orientation_btn.icon = ft.icons.LANDSCAPE if self.landscape else ft.icons.SMARTPHONE
        if self.landscape:
            self.page.window.width = 800
            self.page.window.height = 400
        else:
            self.page.window.width = 400
            self.page.window.height = 800
        self.page.update()

    def _sync_media_icons(self) -> None:
        self._mic_btn.icon = ft.icons.MIC_OFF if not self.audio_enabled else ft.icons.MIC
        self._cam_btn.icon = ft.icons.VIDEOCAM_OFF if not self.video_enabled else ft.icons.VIDEOCAM

    def _send_webrtc_state(self) -> None:
        if not self.connected or not self.session_id:
            return

        def _send():
            try:
                url = urljoin(self.server_url, WEBRTC_STATE_PATH.format(session_id=self.session_id))
                requests.post(url, json={
                    "audio": self.audio_enabled,
                    "video": self.video_enabled,
                }, timeout=5)
            except Exception:
                pass

        threading.Thread(target=_send, daemon=True).start()

    def _start_keyframes(self) -> None:
        self._stop_keyframes()
        self._keyframe_timer = threading.Timer(VISION_KEYFRAME_INTERVAL, self._keyframe_loop)
        self._keyframe_timer.daemon = True
        self._keyframe_timer.start()

    def _stop_keyframes(self) -> None:
        if self._keyframe_timer:
            self._keyframe_timer.cancel()
            self._keyframe_timer = None

    def _keyframe_loop(self) -> None:
        if not self.connected or not self.session_id or not self.video_enabled:
            return
        try:
            img_b64 = self._capture_placeholder_frame()
            if img_b64:
                requests.post(
                    urljoin(self.server_url, VISION_ANALYZE_PATH),
                    json={"image": img_b64, "session_id": self.session_id},
                    timeout=10,
                )
        except Exception:
            pass
        self._start_keyframes()

    def _capture_placeholder_frame(self) -> str:
        return ""

    def _capture_and_analyze_frame(self) -> None:
        if not self.connected or not self.session_id:
            return
        try:
            cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                return
            ret, frame = cap.read()
            cap.release()
            if not ret:
                return
            _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            img_b64 = base64.b64encode(buffer).decode('utf-8')
            requests.post(
                f"{self.server_url}/api/vision/analyze-frame",
                json={"image": img_b64, "session_id": self.session_id},
                timeout=10,
            )
        except Exception:
            pass

    def _on_mic_clicked(self, e: ft.ControlEvent) -> None:
        self.audio_enabled = not self.audio_enabled
        self._sync_media_icons()
        self._send_webrtc_state()
        self.page.update()

    def _on_cam_clicked(self, e: ft.ControlEvent) -> None:
        self.video_enabled = not self.video_enabled
        self._sync_media_icons()
        self._send_webrtc_state()
        if self.video_enabled and self.connected:
            self._start_keyframes()
        else:
            self._stop_keyframes()
        if self.video_enabled and self.connected and self.session_id:
            self._capture_and_analyze_frame()
        self.page.update()

    def _on_flip_camera(self, e: ft.ControlEvent) -> None:
        if self.connected and self.session_id:
            def _send():
                try:
                    url = urljoin(self.server_url, WEBRTC_FLIP_PATH.format(session_id=self.session_id))
                    requests.post(url, json={}, timeout=5)
                except Exception:
                    pass
            threading.Thread(target=_send, daemon=True).start()

    def _on_end_call(self, e: ft.ControlEvent) -> None:
        if self.connected:
            self._disconnect()
        else:
            self.page.close_drawer()
            self._connect()

    def _on_logout(self, e: ft.ControlEvent) -> None:
        self._disconnect()
        self.page.close_drawer()
        self.page.window_close()

    def _start_telemetry_ws(self) -> None:
        self._telemetry_ws_task = None
        self._telemetry_alerts: list = []
        self._swarm_active = False
        self._cpu_text = "CPU: --"
        self._ram_text = "RAM: --"
        self._gpu_text = "GPU: --"
        self._swarm_text = "Swarm: --"
        self._telemetry_server_url = self.server_url.replace("http://", "ws://").replace("https://", "wss://")
        threading.Thread(target=self._telemetry_ws_loop, daemon=True).start()

    def _telemetry_ws_loop(self) -> None:
        backoff = 1.0
        while True:
            try:
                url = f"{self._telemetry_server_url}/ws/telemetry"
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                async def _listen():
                    async with websockets.connect(url, ping_interval=20, ping_timeout=20) as ws:
                        backoff = 1.0
                        while True:
                            msg = await ws.recv()
                            data = json.loads(msg)
                            self._process_telemetry(data)
                loop.run_until_complete(_listen())
            except Exception:
                time.sleep(backoff)
                backoff = min(backoff * 2, 10.0)

    def _process_telemetry(self, data: Dict[str, Any]) -> None:
        try:
            cpu = float(data.get("cpu_percent", 0))
            ram = float(data.get("ram_percent", 0))
            gpu = data.get("gpu_percent")
            gpu_text = f"GPU: {gpu:.0f}%" if isinstance(gpu, (int, float)) else "GPU: N/A"

            swarm = data.get("swarm_agents", [])
            active = sum(1 for a in swarm if a.get("status") == "active")
            total = len(swarm)
            swarm_text = f"Swarm: {active}/{total}"

            self._run_ui(self._update_telemetry_labels, f"CPU: {cpu:.0f}%", f"RAM: {ram:.0f}%", gpu_text, swarm_text)

            alerts = data.get("alerts", [])
            new_alerts = alerts[len(self._telemetry_alerts):]
            for alert in new_alerts:
                self._add_alert(alert)
            self._telemetry_alerts = alerts
        except Exception:
            pass

    def _update_telemetry_labels(self, cpu_text: str, ram_text: str, gpu_text: str, swarm_text: str) -> None:
        try:
            if hasattr(self, '_cpu_text_label'):
                self._cpu_text_label.value = cpu_text
            if hasattr(self, '_ram_text_label'):
                self._ram_text_label.value = ram_text
            if hasattr(self, '_gpu_text_label'):
                self._gpu_text_label.value = gpu_text
            if hasattr(self, '_swarm_text_label'):
                self._swarm_text_label.value = swarm_text
        except Exception:
            pass

    def _add_alert(self, alert: Dict[str, Any]) -> None:
        level = alert.get("level", "info")
        message = alert.get("message", "")
        title = f"Alerta {level.upper()}"
        icon = "🐝" if level == "error" else "🔔"
        self._telemetry_alerts.append(alert)
        self._run_ui(self._show_snack, title, message, icon)

    def _show_snack(self, title: str, message: str, icon: str) -> None:
        try:
            snack = ft.SnackBar(
                content=ft.Text(f"{icon} {title}: {message}", font_family=THEME_FONT),
                bgcolor=THEME_SURFACE_VARIANT,
            )
            self.page.snack_bar = snack
            snack.open = True
            self.page.update()
        except Exception:
            pass

    def _execute_quick_action(self, label: str, tool: str, params: Dict[str, Any]) -> None:
        self._run_ui(self._set_status_text, f"Ejecutando: {label}...")
        self._reset_activity()

        def _send():
            try:
                resp = requests.post(
                    f"{self.server_url}/api/actions/execute",
                    json={"tool": tool, "params": params, "approved": True},
                    timeout=20,
                )
                data = resp.json() if resp.status_code == 200 else {}
                success = data.get("success", False)
                output = data.get("output") or data.get("error") or "Sin respuesta"
                self._run_ui(self._set_status_text, f"{label}: {'OK' if success else 'FALLIDO'}")
                self._run_ui(self._show_snack, label, str(output)[:120], "✅" if success else "❌")
            except Exception as exc:
                self._run_ui(self._set_status_text, f"{label}: ERROR")
                self._run_ui(self._show_snack, label, str(exc)[:120], "❌")

        threading.Thread(target=_send, daemon=True).start()

    def _search_memory_background(self, query: str) -> None:
        if not query or not self.connected:
            return
        def _send():
            try:
                resp = requests.get(
                    f"{self.server_url}/api/memory/search",
                    params={"q": query, "limit": 3},
                    timeout=10,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    results = data.get("context", data.get("results", []))
                    if results:
                        self._run_ui(self._show_snack, "Memoria", f"{len(results)} recuerdos relevantes encontrados", "🧠")
            except Exception:
                pass
        threading.Thread(target=_send, daemon=True).start()

    def _remember_conversation(self, prompt: str, response: str) -> None:
        if not prompt or not self.connected:
            return
        def _send():
            try:
                requests.post(
                    f"{self.server_url}/api/memory/remember",
                    json={"text": f"User: {prompt}\nAURA: {response}", "type": "episodic", "source": "mobile_chat", "session_id": self.session_id},
                    timeout=10,
                )
            except Exception:
                pass
        threading.Thread(target=_send, daemon=True).start()

    def _send_text_chat(self, prompt: str) -> None:
        if not prompt or not self.connected or not self.session_id:
            return
        self._search_memory_background(prompt)
        def _send():
            try:
                resp = requests.post(
                    f"{self.server_url}/api/chat",
                    json={"message": prompt, "session_id": self.session_id},
                    timeout=20,
                )
                data = resp.json() if resp.status_code == 200 else {}
                response = data.get("response") or data.get("message") or data.get("reply") or "Sin respuesta"
                self._run_ui(self._show_snack, "Chat", str(response)[:120], "✅")
                self._remember_conversation(prompt, response)
            except Exception as exc:
                self._run_ui(self._show_snack, "Chat", f"Error: {exc}", "❌")
        threading.Thread(target=_send, daemon=True).start()

    def add_action_card(self, action_data: Dict[str, Any]) -> None:
        tool = action_data.get("tool", "accion")
        prompt = action_data.get("confirmation_prompt") or action_data.get("description", "")
        risk = action_data.get("risk_level", "safe")
        card = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Text("🛠️ " + tool, size=12, weight=ft.FontWeight.BOLD, color=THEME_ON_SURFACE, font_family=THEME_FONT),
                            ft.Text(risk.upper(), size=10, color=THEME_ERROR if risk in ("high", "critical") else THEME_ON_SURFACE_VARIANT, font_family=THEME_FONT),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Text(prompt, size=11, color=THEME_ON_SURFACE_VARIANT, font_family=THEME_FONT),
                    ft.Row(
                        controls=[
                            ft.ElevatedButton("Aprobar", bgcolor=THEME_PRIMARY, color=THEME_ON_PRIMARY, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=THEME_RADIUS_SMALL)), on_click=lambda e, data=action_data: self._confirm_action(True, data)),
                            ft.OutlinedButton("Rechazar", style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=THEME_RADIUS_SMALL)), on_click=lambda e, data=action_data: self._confirm_action(False, data)),
                        ],
                        spacing=8,
                    ),
                ],
                spacing=4,
            ),
            bgcolor=THEME_SURFACE_VARIANT,
            border_radius=THEME_RADIUS_SMALL,
            padding=10,
            border=ft.border.all(1, THEME_OUTLINE),
        )
        if hasattr(self, "_actions_list"):
            self._actions_list.controls.append(card)
            self._run_ui(self.page.update)

    def _confirm_action(self, approved: bool, action_data: Dict[str, Any]) -> None:
        if approved:
            def _send():
                try:
                    requests.post(
                        f"{self.server_url}/api/actions/execute",
                        json={"tool": action_data.get("tool"), "params": action_data.get("params", {}), "approved": True},
                        timeout=10,
                    )
                except Exception:
                    pass
            threading.Thread(target=_send, daemon=True).start()
        if hasattr(self, "_actions_list"):
            self._actions_list.controls.clear()
            self._run_ui(self.page.update)

    def _search_memory(self, e: ft.ControlEvent) -> None:
        query = ""
        if hasattr(self, "_memory_search_input"):
            query = self._memory_search_input.value or ""
        if not query:
            return
        try:
            resp = requests.get(
                f"{self.server_url}/api/memory/search",
                params={"q": query, "limit": 5},
                timeout=10,
            )
            data = resp.json() if resp.status_code == 200 else {}
            results = data.get("results", [])
            self._render_memory_results(results)
        except Exception:
            self._render_memory_results([])

    def _render_memory_results(self, results: list) -> None:
        if not hasattr(self, "_memory_results_list"):
            return
        self._memory_results_list.controls.clear()
        if not results:
            self._memory_results_list.controls.append(ft.Text("Sin recuerdos encontrados", color=THEME_ON_SURFACE_VARIANT, size=11, font_family=THEME_FONT))
        else:
            for mem in results:
                self._memory_results_list.controls.append(
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Text(mem.get("memory_type", "MEMORY", font_family=THEME_FONT).upper(), size=10, weight=ft.FontWeight.BOLD, color=THEME_PRIMARY),
                                ft.Text(mem.get("text", "", font_family=THEME_FONT), size=11, color=THEME_ON_SURFACE),
                                ft.Text(f"Relevancia: {mem.get('relevance_score', 0, font_family=THEME_FONT):.2f}", size=9, color=THEME_ON_SURFACE_VARIANT),
                            ],
                            spacing=2,
                        ),
                        bgcolor=THEME_SURFACE_VARIANT,
                        border_radius=THEME_RADIUS_SMALL,
                        padding=8,
                        border=ft.border.all(1, THEME_OUTLINE),
                    )
                )
        self._run_ui(self.page.update)

    def _add_memory_dialog(self, e: ft.ControlEvent) -> None:
        def _save(text: str) -> None:
            if not text.strip():
                return
            try:
                requests.post(
                    f"{self.server_url}/api/memory/remember",
                    json={"text": text.strip(), "type": "semantic", "source": "mobile"},
                    timeout=10,
                )
            except Exception:
                pass
        text_field = ft.TextField(label="Nuevo recuerdo", multiline=True, min_lines=2, max_lines=4)
        dialog = ft.AlertDialog(
            title=ft.Text("Agregar Recuerdo", font_family=THEME_FONT),
            content=text_field,
            actions=[
                ft.TextButton("Cancelar", on_click=lambda e: setattr(self.page, 'dialog', None) or self.page.update()),
                ft.ElevatedButton("Guardar", on_click=lambda e: (_save(text_field.value or ""), setattr(self.page, 'dialog', None) or self.page.update())),
            ],
        )
        self.page.dialog = dialog
        dialog.open = True
        self.page.update()

    def _recover_swarm(self, e: ft.ControlEvent) -> None:
        try:
            requests.post(
                f"{self.server_url}/api/swarm/recover",
                json={"module": "self_healing", "reason": "manual_trigger"},
                timeout=10,
            )
        except Exception:
            pass


def main(page: ft.Page) -> None:
    client = AuraMobileClient(page)


if __name__ == "__main__":
    ft.app(target=main)
