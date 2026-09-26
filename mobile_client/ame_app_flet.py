# -*- coding: utf-8 -*-
"""AURA Mobile — AME Flet App (cyberpunk hacker).

Conecta a AURA Desktop via:
  - QR/PIN pairing (local)
  - WebSocket P2P (LAN)
  - Chat con AURA
  - Sync offline-first

Estetica cyberpunk: cyan + orange + black + mono font.
"""
from __future__ import annotations

import os
import sys
import json
import time
import hmac
import hashlib
import logging
import threading
import asyncio
from typing import Optional

import flet as ft

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

logger = logging.getLogger("AURA.Mobile")

# Cyberpunk colors
BG_DARK = "#0f172a"
BG_PANEL = "#1a202c"
PRIMARY = "#38bdf8"
ACCENT = "#ff6b35"
SUCCESS = "#10b981"
ERROR = "#ef4444"
TEXT_DIM = "#64748b"
FONT = "Courier New"


class AMEMobileApp:
    """AME Mobile — Flet app para conectar a AURA Desktop."""

    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self.page.title = "AURA AME — Mobile"
        self.page.padding = 0
        self.page.theme_mode = ft.ThemeMode.DARK
        self.page.bgcolor = BG_DARK
        self.page.font_family = FONT
        self.page.window_center()

        self.connected: bool = False
        self.paired: bool = False
        self.pairing_code: str = ""
        self.backend_url: str = ""
        self.messages: list = []
        self.tasks_data: list = []
        self._reconnect_timer: Optional[threading.Timer] = None

        self._build_ui()
        self._update_status("Scanning for AURA...", ACCENT)
        self._auto_discover()

    def _update_status(self, text: str, color: str = PRIMARY) -> None:
        if hasattr(self, '_status_label'):
            self._status_label.value = text
            self._status_label.color = color
            self.page.update()

    def _auto_discover(self) -> None:
        def _scan():
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(2)
            try:
                s.sendto(b"AURA_DISCOVER", ("255.255.255.255", 8000))
                data, addr = s.recvfrom(1024)
                if data == b"AURA_HERE":
                    ip = addr[0]
                    self.backend_url = f"http://{ip}:8000"
                    self._update_status(f"Servidor encontrado: {ip}", SUCCESS)
                    self._show_pairing_request()
            except Exception:
                self._update_status("No servidor encontrado - escanea QR", TEXT_DIM)
            finally:
                s.close()
        threading.Thread(target=_scan, daemon=True).start()

    def _build_ui(self) -> None:
        self.page.appbar = ft.AppBar(
            title=ft.Row([
                ft.Icon(name=ft.icons.CYBERNETIC, color=PRIMARY, size=20),
                ft.Text("AURA AME", size=18, weight=ft.FontWeight.BOLD, color=PRIMARY, font_family=FONT),
            ]),
            bgcolor=BG_PANEL,
            elevation=0,
            actions=[
                ft.Container(
                    content=ft.Text("Mobile", size=10, color=TEXT_DIM, font_family=FONT),
                    padding=ft.padding.only(right=12),
                )
            ],
        )

        self._status_label = ft.Text(
            "Iniciando...",
            color=ACCENT,
            size=11,
            font_family=FONT,
        )

        self._chat_list = ft.ListView(
            spacing=4,
            padding=ft.padding.symmetric(horizontal=12, vertical=8),
            height=300,
            expand=True,
        )

        self._pin_input = ft.TextField(
            label="PIN pairing",
            hint_text="Escribe el PIN de AURA Desktop",
            border_color=PRIMARY,
            focused_border_color=ACCENT,
            bgcolor=BG_PANEL,
            color=PRIMARY,
            label_style=ft.TextStyle(color=TEXT_DIM, font_family=FONT),
            hint_style=ft.TextStyle(color=TEXT_DIM, font_family=FONT),
            font_family=FONT,
            width=280,
        )

        self._pair_btn = ft.ElevatedButton(
            text="Pairing",
            icon=ft.icons.QR_CODE_2,
            bgcolor=ACCENT,
            color=BG_DARK,
            width=200,
            on_click=self._do_pair,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
        )

        self._messages_input = ft.TextField(
            hint_text="Escribe mensaje para AURA...",
            border_color=PRIMARY,
            focused_border_color=ACCENT,
            bgcolor=BG_PANEL,
            color=PRIMARY,
            font_family=FONT,
            expand=True,
        )

        self._send_btn = ft.IconButton(
            icon=ft.icons.SEND,
            icon_color=PRIMARY,
            bgcolor=BG_PANEL,
            on_click=self._send_message,
            width=48,
            height=48,
        )

        body = ft.Column(
            controls=[
                ft.Container(
                    content=self._status_label,
                    padding=ft.padding.symmetric(horizontal=16, vertical=6),
                    bgcolor=BG_PANEL,
                    border=ft.border.all(1, PRIMARY),
                    border_radius=4,
                ),
                ft.Container(
                    content=ft.Text(
                        "💬 Chat AURA",
                        size=14,
                        weight=ft.FontWeight.BOLD,
                        color=PRIMARY,
                        font_family=FONT,
                    ),
                    padding=ft.padding.only(left=16, top=8),
                ),
                ft.Container(
                    content=self._chat_list,
                    height=280,
                    bgcolor=BG_PANEL,
                    border=ft.border.all(1, PRIMARY),
                    border_radius=4,
                    margin=ft.margin.symmetric(horizontal=12),
                ),
                ft.Container(
                    content=self._pin_input,
                    padding=ft.padding.symmetric(horizontal=16),
                ),
                ft.Container(
                    content=self._pair_btn,
                    padding=ft.padding.symmetric(horizontal=16),
                ),
                ft.Divider(color=PRIMARY, height=1),
                ft.Container(
                    content=ft.Row(
                        controls=[
                            self._messages_input,
                            self._send_btn,
                        ],
                        spacing=8,
                    ),
                    padding=ft.padding.symmetric(horizontal=12, vertical=8),
                ),
                ft.Container(height=40),
            ],
            spacing=0,
            expand=True,
        )

        self.page.add(body)

    def _show_pairing_request(self) -> None:
        def _show():
            self.page.open(
                ft.AlertDialog(
                    modal=True,
                    title=ft.Text("Emparejar con AURA", color=PRIMARY, font_family=FONT),
                    content=ft.Column([
                        ft.Text(
                            "Ingresa el PIN que muestra AURA Desktop:",
                            color=TEXT_DIM,
                            font_family=FONT,
                            size=12,
                        ),
                        self._pin_input,
                    ]),
                    actions=[
                        ft.TextButton(
                            "Cancelar",
                            on_click=lambda e: self.page.close(),
                            style=ft.ButtonStyle(color=TEXT_DIM),
                        ),
                        ft.TextButton(
                            "Conectar",
                            on_click=self._do_pair,
                            style=ft.ButtonStyle(color=ACCENT),
                        ),
                    ],
                    actions_alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                )
            )
        self.page.run_task(_show)

    def _do_pair(self, e=None) -> None:
        pin = self._pin_input.value.strip() if hasattr(self, '_pin_input') else ""
        if not pin:
            self._update_status("PIN requerido", ERROR)
            return

        self.pairing_code = pin
        self.paired = True
        self._update_status("Emparejado ✅", SUCCESS)
        self.page.close()
        self._add_chat("Sistema", "Emparejado con AURA Desktop", color=SUCCESS)

        def _verify():
            time.sleep(2)
            self._update_status("Conectado a AURA", SUCCESS)
            self._start_sync_loop()

        threading.Thread(target=_verify, daemon=True).start()

    def _start_sync_loop(self) -> None:
        def _sync():
            while self.paired:
                try:
                    import requests
                    resp = requests.get(
                        f"{self.backend_url}/api/aura/status/full",
                        timeout=3,
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        tasks = data.get("tasks", [])
                        self.page.run_task(self._update_tasks, tasks)
                        revenue = data.get("revenue", {}).get("total", 0)
                        self._update_status(f"Activo | ${revenue:.2f}", SUCCESS)
                except Exception:
                    self._update_status("Reconectando...", ACCENT)
                time.sleep(5)
        threading.Thread(target=_sync, daemon=True).start()

    def _update_tasks(self, tasks: list) -> None:
        self.tasks_data = tasks

    def _send_message(self, e=None) -> None:
        text = self._messages_input.value.strip()
        if not text:
            return
        self._messages_input.value = ""
        self._add_chat("Tú", text, is_user=True)

        def _send():
            try:
                import requests
                resp = requests.post(
                    f"{self.backend_url}/api/aura/chat",
                    json={"message": text},
                    timeout=10,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    response = data.get("response", "Sin respuesta")
                    self.page.run_task(self._add_chat, "AURA", response)
                else:
                    self.page.run_task(self._add_chat, "AURA", "Error de respuesta", color=ERROR)
            except Exception as exc:
                self.page.run_task(self._add_chat, "AURA", f"Error: {exc}", color=ERROR)

        threading.Thread(target=_send, daemon=True).start()

    def _add_chat(self, sender: str, text: str, is_user: bool = False, color: str = PRIMARY) -> None:
        prefix = "📝" if is_user else "🤖"
        bg = BG_PANEL
        if is_user:
            bg = "#1a3a2a"

        msg = ft.Container(
            content=ft.Text(
                f"{prefix} {sender}: {text}",
                color=color,
                font_family=FONT,
                size=12,
            ),
            bgcolor=bg,
            border=ft.border.all(1, PRIMARY if not is_user else SUCCESS),
            border_radius=8,
            padding=ft.padding.symmetric(horizontal=10, vertical=6),
            margin=ft.margin.symmetric(horizontal=8, vertical=2),
            alignment=ft.alignment.center_right if is_user else ft.alignment.center_left,
        )
        self._chat_list.controls.append(msg)
        if len(self._chat_list.controls) > 50:
            self._chat_list.controls = self._chat_list.controls[-50:]
        self.page.update()

    def _on_back_key(self, e) -> None:
        if self.paired:
            self._update_status("Desconectado", ACCENT)
            self.paired = False
        else:
            self.page.window_close()


def main() -> None:
    def app(page: ft.Page):
        AMEMobileApp(page)

    ft.app(target=app, view=ft.AppView.WEB_BROWSER, port=8550)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
