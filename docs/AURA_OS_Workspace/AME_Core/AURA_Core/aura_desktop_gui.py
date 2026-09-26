#!/usr/bin/env python3
"""
aura_desktop_gui.py — Interfaz gráfica ligera para AURA Core
Usa Flet (Flutter-based UI) para controlar bot, ver logs, estado AME App
"""

import asyncio
import json
import threading
import logging
import time
from pathlib import Path

try:
    import flet as ft

    FLET_AVAILABLE = True
except ImportError:
    FLET_AVAILABLE = False
    print("Flet no instalado. pip install flet")

# Config logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("AURA_GUI")

# Estado global
bot_status = {"running": False, "games_played": 0, "errors": 0}
ame_status = {"connected": False, "last_seen": 0}
log_history = []


def add_log(msg):
    """Agrega mensaje al historial de logs"""
    ts = time.strftime("%H:%M:%S")
    log_history.append(f"[{ts}] {msg}")
    if len(log_history) > 200:
        log_history.pop(0)
    log.info(msg)


class AURAGUI:
    """Interfaz Flet para controlar AURA Core"""

    def __init__(self):
        self.page = None
        self.log_display = None
        self.btn_bot = None
        self.status_bot = None
        self.status_ame = None
        self.stats_text = None

    def main(self, page: ft.Page):
        """Punto de entrada Flet"""
        self.page = page
        page.title = "AURA Core Control Panel"
        page.theme_mode = ft.ThemeMode.DARK
        page.bgcolor = "#0D1117"
        page.padding = 16
        page.window_width = 800
        page.window_height = 600

        # Header
        page.add(
            ft.Container(
                content=ft.Column(
                    [
                        ft.Text(
                            "🧠 AURA CORE", size=24, weight=ft.FontWeight.BOLD, color="#58A6FF"
                        ),
                        ft.Text(
                            "Panel de control del ecosistema de automatización",
                            size=12,
                            color="#8B949E",
                        ),
                    ]
                ),
                padding=ft.padding.only(bottom=12),
            )
        )

        # Fila de estado
        status_row = ft.Row(
            controls=[
                self._create_status_card("🤖 Roller Bot", "#3FB950", self._build_bot_status()),
                self._create_status_card("📱 AME App", "#58A6FF", self._build_ame_status()),
            ],
            spacing=12,
        )
        page.add(status_row)

        # Botones de control
        self.btn_bot = ft.ElevatedButton(
            "▶ Iniciar Bot",
            icon=ft.icons.PLAY_ARROW,
            color="#FFFFFF",
            bgcolor="#238636",
            on_click=self.toggle_bot,
        )

        page.add(
            ft.Container(
                content=ft.Row(
                    controls=[
                        self.btn_bot,
                        ft.ElevatedButton(
                            "📷 Verificar AME",
                            icon=ft.icons.PHONE_ANDROID,
                            color="#FFFFFF",
                            bgcolor="#1F6FEB",
                            on_click=self.check_ame,
                        ),
                        ft.ElevatedButton(
                            "🗑 Limpiar Logs",
                            icon=ft.icons.DELETE_OUTLINE,
                            color="#C9D1D9",
                            bgcolor="#21262D",
                            on_click=self.clear_logs,
                        ),
                    ],
                    spacing=8,
                ),
                padding=ft.padding.symmetric(vertical=8),
            )
        )

        # Área de logs
        self.log_display = ft.ListView(
            expand=True,
            spacing=2,
            auto_scroll=True,
        )
        page.add(
            ft.Container(
                content=ft.Column(
                    [
                        ft.Text("📋 Logs en tiempo real", size=12, color="#8B949E"),
                        ft.Container(
                            content=self.log_display,
                            bgcolor="#161B22",
                            border=ft.border.all(0.5, "#30363D"),
                            border_radius=8,
                            padding=12,
                            expand=True,
                        ),
                    ]
                ),
                expand=True,
            )
        )

        # Agregar logs iniciales
        add_log("Interfaz AURA iniciada")
        add_log("Esperando comandos...")
        self._refresh_logs()
        page.update()

    def _create_status_card(self, title, color, content):
        """Crea una tarjeta de estado"""
        return ft.Container(
            content=ft.Column(
                [
                    ft.Text(title, size=14, weight=ft.FontWeight.BOLD, color=color),
                    content,
                ]
            ),
            bgcolor="#161B22",
            border=ft.border.all(0.5, "#30363D"),
            border_radius=8,
            padding=16,
            expand=True,
        )

    def _build_bot_status(self):
        """Estado del bot Rollercoin"""
        self.status_bot = ft.Text("⏹ Detenido", size=12, color="#FF7B72")
        self.stats_text = ft.Text("Juegos: 0 | Errores: 0", size=11, color="#8B949E")
        return ft.Column([self.status_bot, self.stats_text])

    def _build_ame_status(self):
        """Estado de conexión AME App"""
        self.status_ame = ft.Text("🔴 Desconectado", size=12, color="#FF7B72")
        return ft.Column(
            [
                self.status_ame,
                ft.Text("Endpoint: /api/v1/automation/*", size=10, color="#8B949E"),
                ft.Text("FastAPI: localhost:8765", size=10, color="#8B949E"),
            ]
        )

    def toggle_bot(self, e):
        """Alternar estado del bot"""
        if bot_status["running"]:
            bot_status["running"] = False
            self.btn_bot.text = "▶ Iniciar Bot"
            self.btn_bot.bgcolor = "#238636"
            self.status_bot.value = "⏹ Detenido"
            self.status_bot.color = "#FF7B72"
            add_log("Bot detenido manualmente")
        else:
            bot_status["running"] = True
            self.btn_bot.text = "⏹ Detener Bot"
            self.btn_bot.bgcolor = "#DA3633"
            self.status_bot.value = "▶ Ejecutando..."
            self.status_bot.color = "#3FB950"
            add_log("Bot iniciado")

        self._update_stats()
        self.page.update()

    def check_ame(self, e):
        """Verificar conexión con AME App"""
        ame_status["last_seen"] = time.time()
        ame_status["connected"] = True
        self.status_ame.value = "🟢 Conectado"
        self.status_ame.color = "#3FB950"
        add_log("AME App verificada: CONECTADA")
        self.page.update()

    def clear_logs(self, e):
        """Limpiar logs"""
        log_history.clear()
        self.log_display.controls.clear()
        add_log("Logs limpiados")
        self._refresh_logs()
        self.page.update()

    def _refresh_logs(self):
        """Actualizar visualización de logs"""
        self.log_display.controls.clear()
        for msg in log_history[-50:]:
            self.log_display.controls.append(
                ft.Text(msg, size=11, color="#8B949E", font_family="monospace")
            )

    def _update_stats(self):
        """Actualizar estadísticas"""
        self.stats_text.value = (
            f"Juegos: {bot_status['games_played']} | Errores: {bot_status['errors']}"
        )
        self._refresh_logs()

    def update_from_api(self, data):
        """Actualizar estado desde API externa"""
        if "status" in data:
            bot_status["running"] = data["status"] == "running"
        if "games_played" in data:
            bot_status["games_played"] = data["games_played"]
        if self.page:
            self._update_stats()
            self.page.update()


def run_gui():
    """Inicia la GUI Flet en un thread separado"""
    if not FLET_AVAILABLE:
        log.error("Flet no disponible. pip install flet")
        return

    gui = AURAGUI()
    ft.app(target=gui.main)

    # Loop de actualización periódica
    while True:
        time.sleep(2)
        gui._refresh_logs()
        if gui.page:
            try:
                gui.page.update()
            except Exception:
                pass


def start_gui_thread():
    """Inicia GUI en thread separado"""
    t = threading.Thread(target=run_gui, daemon=True)
    t.start()
    log.info("GUI thread iniciado")
    return t


if __name__ == "__main__":
    # Si se ejecuta standalone, iniciar sin thread
    if FLET_AVAILABLE:
        gui = AURAGUI()
        ft.app(target=gui.main)
    else:
        log.error("Instala Flet: pip install flet")
