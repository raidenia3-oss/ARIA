# -*- coding: utf-8 -*-
"""AURA AME — Netrunner AR Mode (Flet + ARCore).

Gamifica el mundo real como red hackeable:
  - Camara AR muestra nodos sobre el entorno
  - HUD muestra accesos cercanos
  - Tap-to-hack gameplay
  - Conecta a backend AURA via WebSocket local

Aesthetic: cyberpunk hacker (cyan + orange + black + mono font).
"""
from __future__ import annotations

import os
import sys
import json
import time
import logging
import threading
import random
from typing import Optional

import flet as ft

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__)).parent
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

logger = logging.getLogger("AURA.AME.Netrunner")

BG_DARK = "#0f172a"
BG_PANEL = "#1a202c"
PRIMARY = "#38bdf8"
ACCENT = "#ff6b35"
SUCCESS = "#10b981"
ERROR = "#ef4444"
TEXT_DIM = "#64748b"
FONT = "Courier New"

AR_NODE_COLORS = {
    "low": SUCCESS,
    "medium": PRIMARY,
    "high": ACCENT,
    "critical": ERROR,
}


class NetrunnerHUD:
    """HUD de realidad aumentada para modo Netrunner."""

    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self.nodes: list = []
        self.hacked: list = []
        self.camera_active: bool = False
        self.scan_active: bool = False
        self._ar_canvas: ft.Canvas | None = None
        self._hud_overlay: ft.Stack | None = None

    def render_ar_view(self) -> ft.Container:
        """Renderiza vista AR con nodos flotantes."""
        camera_preview = ft.Container(
            content=ft.Stack(
                controls=[
                    ft.Container(
                        bgcolor="#0a0e17",
                        width="100%",
                        height=300,
                        border=ft.border.all(2, PRIMARY),
                        border_radius=8,
                        content=ft.Column(
                            controls=[
                                ft.Icon(name=ft.icons.VIDEOSCAN, color=PRIMARY, size=48),
                                ft.Text(
                                    "CAMARA AR",
                                    color=PRIMARY,
                                    font_family=FONT,
                                    size=10,
                                ),
                                ft.Text(
                                    "Point at devices to scan",
                                    color=TEXT_DIM,
                                    font_family=FONT,
                                    size=9,
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.CENTER,
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                    ),
                ],
                id="ar_stack",
            ),
            border_radius=8,
            margin=ft.margin.symmetric(horizontal=12),
        )
        self._ar_canvas = camera_preview.content
        return camera_preview

    def render_hud(self) -> ft.Stack:
        """Renderiza HUD con datos de red superpuestos."""
        hud = ft.Stack(
            controls=[
                self.render_ar_view(),
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Container(
                                content=ft.Text(
                                    "◈ SCAN",
                                    color=ACCENT,
                                    font_family=FONT,
                                    size=11,
                                    weight=ft.FontWeight.BOLD,
                                ),
                                bgcolor="#0a0e1799",
                                padding=ft.padding.symmetric(horizontal=6, vertical=2),
                                border_radius=3,
                            ),
                            ft.Container(height=4),
                            self._build_scan_status(),
                        ],
                        spacing=4,
                    ),
                    top=8,
                    left=8,
                    right=8,
                    bgcolor=BG_PANEL,
                    border=ft.border.all(1, PRIMARY),
                    border_radius=4,
                    padding=8,
                ),
            ],
            expand=True,
        )
        self._hud_overlay = hud
        return hud

    def _build_scan_status(self) -> ft.Column:
        return ft.Column(
            controls=[
                ft.Text(
                    f"Nodes: {len(self.nodes)}",
                    color=PRIMARY,
                    font_family=FONT,
                    size=10,
                ),
                ft.Text(
                    f"Hacked: {len(self.hacked)}",
                    color=SUCCESS,
                    font_family=FONT,
                    size=10,
                ),
                ft.ProgressBar(
                    width=200,
                    value=min(len(self.hacked) / max(len(self.nodes), 1), 1.0),
                    color=SUCCESS,
                    bgcolor="#1e293b",
                    height=4,
                ),
            ],
            spacing=2,
        )


class AMENetrunnerApp:
    """AME Mobile — Netrunner AR modo de juego."""

    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self.page.title = "AURA Netrunner AR"
        self.page.padding = 0
        self.page.theme_mode = ft.ThemeMode.DARK
        self.page.bgcolor = BG_DARK
        self.page.font_family = FONT
        self.page.window_center()

        self.hud = NetrunnerHUD(page)
        self.connected: bool = False
        self.backend_url: str = "http://127.0.0.1:8000"
        self.scan_result: Optional[dict] = None
        self.hack_in_progress: bool = False

        self._build_ui()
        self._auto_connect()

    def _build_ui(self) -> None:
        self.page.appbar = ft.AppBar(
            title=ft.Row([
                ft.Icon(name=ft.icons.HACK, color=ACCENT, size=20),
                ft.Text("NETRUNNER AR", size=18, weight=ft.FontWeight.BOLD, color=ACCENT, font_family=FONT),
            ]),
            bgcolor=BG_PANEL,
            elevation=0,
            actions=[
                ft.Container(
                    content=ft.Text("AR Mode", size=10, color=TEXT_DIM, font_family=FONT),
                    padding=ft.padding.only(right=12),
                )
            ],
        )

        self._status_label = ft.Text(
            "Initializing AR...",
            color=ACCENT,
            size=11,
            font_family=FONT,
        )

        self._node_list = ft.ListView(
            spacing=3,
            padding=ft.padding.symmetric(horizontal=8),
            height=200,
        )

        self._hack_console = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("══════ HACK CONSOLE ══════", color=ACCENT, font_family=FONT, size=10),
                    ft.Text(
                        "Select a node and tap Hack",
                        color=TEXT_DIM,
                        font_family=FONT,
                        size=9,
                    ),
                ],
                spacing=2,
            ),
            bgcolor=BG_PANEL,
            border=ft.border.all(1, ACCENT),
            border_radius=4,
            padding=8,
            margin=ft.margin.symmetric(horizontal=12),
        )

        body = ft.Column(
            controls=[
                ft.Container(
                    content=self._status_label,
                    padding=ft.padding.symmetric(horizontal=12, vertical=4),
                    bgcolor=BG_PANEL,
                    border=ft.border.all(1, PRIMARY),
                    border_radius=3,
                ),
                ft.Container(
                    content=self.hud.render_hud(),
                    height=320,
                    bgcolor=BG_PANEL,
                    border=ft.border.all(1, PRIMARY),
                    border_radius=6,
                    margin=ft.margin.symmetric(horizontal=12),
                ),
                ft.Container(
                    content=ft.Text(
                        "◈ DISCOVERED NODES",
                        color=PRIMARY,
                        font_family=FONT,
                        size=12,
                        weight=ft.FontWeight.BOLD,
                    ),
                    padding=ft.padding.only(left=16, top=8),
                ),
                ft.Container(
                    content=self._node_list,
                    height=200,
                    bgcolor=BG_PANEL,
                    border=ft.border.all(1, PRIMARY),
                    border_radius=4,
                    margin=ft.margin.symmetric(horizontal=12),
                ),
                self._hack_console,
                ft.Container(height=40),
            ],
            spacing=0,
            expand=True,
        )

        self.page.add(body)

    def _auto_connect(self) -> None:
        def _connect():
            time.sleep(1)
            self.page.run_task(self._do_scan)
        threading.Thread(target=_connect, daemon=True).start()

    def _update_status(self, text: str, color: str = PRIMARY) -> None:
        self._status_label.value = text
        self._status_label.color = color
        self.page.update()

    def _add_node(self, node: dict) -> None:
        security = node.get("security", "unknown")
        color = AR_NODE_COLORS.get(security, PRIMARY)
        status = node.get("status", "")
        icon = ft.icons.LOCK if status == "firewalled" else ft.icons.OPEN_IN_NEW

        node_card = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(name=icon, color=color, size=18),
                    ft.Column(
                        controls=[
                            ft.Text(
                                node.get("hostname", node.get("ip", "?")),
                                color=color,
                                font_family=FONT,
                                size=11,
                                weight=ft.FontWeight.BOLD,
                            ),
                            ft.Text(
                                f"{node.get('ip', '?')} | {security.upper()} | {node.get('services', [])}",
                                color=TEXT_DIM,
                                font_family=FONT,
                                size=9,
                            ),
                        ],
                        spacing=0,
                        expand=True,
                    ),
                    ft.ElevatedButton(
                        text="Hack",
                        icon=ft.icons.HACK,
                        bgcolor=ACCENT,
                        color=BG_DARK,
                        width=70,
                        height=32,
                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=4)),
                        on_click=lambda e, n=node: self._hack_node(n),
                    ),
                ],
                spacing=6,
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            bgcolor=BG_DARK,
            border=ft.border.all(1, color),
            border_radius=4,
            padding=8,
            margin=ft.margin.symmetric(horizontal=4, vertical=2),
        )
        self.hud.nodes.append(node)
        self._node_list.controls.append(node_card)
        self.page.update()

    def _do_scan(self) -> None:
        self._update_status("Scanning AR network...", ACCENT)
        try:
            import requests
            resp = requests.post(
                f"{self.backend_url}/api/netrunner/scan",
                json={"subnet": "192.168.1", "count": 8, "force": True},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                self.scan_result = data
                self._update_status(f"Found {len(data.get('access_points', []))} nodes", SUCCESS)
                for ap in data.get("access_points", []):
                    self._add_node(ap)
            else:
                self._update_status("Scan failed", ERROR)
        except Exception as e:
            self._update_status(f"Scan error: {e}", ERROR)

    def _hack_node(self, node: dict) -> None:
        if self.hack_in_progress:
            return
        self.hack_in_progress = True

        target_ip = node.get("ip", "")
        target_name = node.get("hostname", target_ip)
        self._update_status(f"Hacking {target_name}...", ACCENT)

        def _hack():
            try:
                # Find mission for this target
                missions_resp = requests.get(
                    f"{self.backend_url}/api/netrunner/missions",
                    timeout=5,
                )
                missions = []
                if missions_resp.status_code == 200:
                    missions_data = missions_resp.json()
                    missions = [
                        m for m in missions_data.get("missions", [])
                        if m.get("target") == target_ip and m.get("status") == "available"
                    ]

                skill = random.randint(3, 8)
                if missions:
                    hack_resp = requests.post(
                        f"{self.backend_url}/api/netrunner/hack",
                        json={"mission_id": missions[0]["id"], "skill": skill},
                        timeout=10,
                    )
                    if hack_resp.status_code == 200:
                        result = hack_resp.json()
                        if result.get("success"):
                            self.hud.hacked.append(target_ip)
                            node["status"] = "compromised"
                            self._update_status(f"HACKED: {target_name}!", SUCCESS)
                            self._add_hack_log(target_name, True, result.get("reward", 0))
                        else:
                            damage = result.get("damage_taken", 0)
                            self._update_status(f"FAIL: {target_name} (DMG {damage})", ERROR)
                            self._add_hack_log(target_name, False, damage)
                    else:
                        self._update_status("Hack request failed", ERROR)
                else:
                    success = random.random() > 0.4
                    if success:
                        self.hud.hacked.append(target_ip)
                        self._update_status(f"HACKED: {target_name}!", SUCCESS)
                        self._add_hack_log(target_name, True, random.uniform(0.1, 0.5))
                    else:
                        self._update_status(f"FAIL: {target_name}", ERROR)
                        self._add_hack_log(target_name, False, random.randint(1, 5))

                self.hack_in_progress = False
                self._update_status(f"{len(self.hud.hacked)}/{len(self.hud.nodes)} nodes hacked", PRIMARY)
            except Exception as e:
                self._update_status(f"Hack error: {e}", ERROR)
                self.hack_in_progress = False

        threading.Thread(target=_hack, daemon=True).start()

    def _add_hack_log(self, target: str, success: bool, reward: float) -> None:
        timestamp = time.strftime("%H:%M:%S")
        color = SUCCESS if success else ERROR
        icon = "✓" if success else "✗"
        reward_text = f" +${reward:.3f}" if success and reward > 0 else ""

        log_line = ft.Text(
            f"[{timestamp}] {icon} {target}{reward_text}",
            color=color,
            font_family=FONT,
            size=10,
        )
        log_container = ft.Container(
            content=log_line,
            padding=ft.padding.symmetric(horizontal=4, vertical=2),
            bgcolor=BG_DARK,
            border_radius=2,
        )
        self._hack_console.content.controls.append(log_container)
        if len(self._hack_console.content.controls) > 20:
            self._hack_console.content.controls = self._hack_console.content.controls[-20:]
        self.page.update()

    def _on_back_key(self, e) -> None:
        self.page.window_close()


def main() -> None:
    def app(page: ft.Page):
        AMENetrunnerApp(page)

    ft.app(target=app, view=ft.AppView.WEB_BROWSER, port=8551)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
