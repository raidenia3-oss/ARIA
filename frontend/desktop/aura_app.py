# -*- coding: utf-8 -*-
"""AURA Desktop — PyQt5 UI nativa cyberpunk.

Ventana principal con:
  - Chat panel
  - Task monitor con progress bars
  - Status bar
  - System tray
  - QR pairing display

Estetica cyberpunk hacker: cyan + orange + black.
"""
from __future__ import annotations

import sys
import json
import time
import threading
import urllib.request
import logging
from typing import Optional

try:
    from PyQt5.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QListWidget, QListWidgetItem, QTextEdit, QPushButton, QLabel,
        QProgressBar, QStatusBar, QSystemTrayIcon, QMenu, QAction,
        QMessageBox, QFrame, QScrollArea, QSizePolicy, QPlainTextEdit,
    )
    from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread, QSize
    from PyQt5.QtGui import QFont, QColor, QTextCursor, QIcon, QPixmap
except ImportError:
    print("PyQt5 no instalado. Instalar: pip install PyQt5==5.15.7")
    sys.exit(1)

BG_DARK = "#0f172a"
BG_PANEL = "#1a202c"
PRIMARY = "#38bdf8"
ACCENT = "#ff6b35"
SUCCESS = "#10b981"
TEXT_DIM = "#64748b"
FONT_NAME = "Courier New"

logger = logging.getLogger("AURA.Desktop.UI")


class ChatThread(QThread):
    """Thread para recibir respuestas del backend."""
    message_received = pyqtSignal(dict)

    def __init__(self, port: int):
        super().__init__()
        self.port = port
        self.running = True

    def run(self):
        while self.running:
            try:
                url = f"http://127.0.0.1:{self.port}/api/aura/tasks/live"
                req = urllib.request.Request(url, headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=2) as resp:
                    data = json.loads(resp.read().decode())
                    self.message_received.emit(data)
            except Exception:
                pass
            time.sleep(3)

    def stop(self):
        self.running = False


class ChatMessageThread(QThread):
    """Thread que monitorea el chat del backend."""
    message_received = pyqtSignal(str, str)

    def __init__(self, port: int):
        super().__init__()
        self.port = port
        self.running = True

    def run(self):
        while self.running:
            try:
                url = f"http://127.0.0.1:{self.port}/api/aura/status/full"
                req = urllib.request.Request(url)
                with urllib.request.urlopen(req, timeout=2) as resp:
                    data = json.loads(resp.read().decode())
                    daemon_status = data.get("daemon", {})
                    active = daemon_status.get("daemon_active", False)
                    self.message_received.emit("status", json.dumps({"active": active}))
            except Exception:
                pass
            time.sleep(5)

    def stop(self):
        self.running = False


class AURADesktopApp(QMainWindow):
    """Ventana principal nativa de AURA Desktop."""

    def __init__(self, backend_port: int = 8000, backend_host: str = "127.0.0.1",
                 local_ip: str = "127.0.0.1", pairing_code: str = ""):
        super().__init__()
        self.backend_port = backend_port
        self.backend_host = backend_host
        self.local_ip = local_ip
        self.pairing_code = pairing_code
        self.chat_history: list = []

        self.setWindowTitle("AURA OS v1.0 — Desktop")
        self.setMinimumSize(900, 700)
        self.setStyleSheet(self._build_stylesheet())
        self.setFont(QFont(FONT_NAME, 11))

        self._build_ui()
        self._build_tray()
        self._start_threads()
        self._show_qr()

    def _build_stylesheet(self) -> str:
        return f"""
            QMainWindow {{ background: {BG_DARK}; }}
            QWidget {{ background: {BG_DARK}; color: {PRIMARY}; font-family: {FONT_NAME}; }}
            QListWidget {{
                background: {BG_PANEL}; border: 1px solid {PRIMARY};
                border-radius: 4px; color: {PRIMARY}; font-family: {FONT_NAME};
            }}
            QListWidget::item {{ padding: 6px; border-radius: 2px; }}
            QListWidget::item:selected {{ background: rgba(56,189,248,0.15); }}
            QTextEdit, QPlainTextEdit {{
                background: {BG_PANEL}; border: 1px solid {PRIMARY};
                color: {PRIMARY}; font-family: {FONT_NAME}; font-size: 12px;
                border-radius: 4px; padding: 8px;
            }}
            QTextEdit:focus, QPlainTextEdit:focus {{ border-color: {ACCENT}; }}
            QPushButton {{
                background: {BG_PANEL}; border: 1px solid {PRIMARY};
                color: {PRIMARY}; font-family: {FONT_NAME};
                padding: 8px 16px; border-radius: 4px; font-size: 12px;
            }}
            QPushButton:hover {{ background: rgba(56,189,248,0.15); border-color: {ACCENT}; }}
            QPushButton:pressed {{ background: rgba(255,107,53,0.2); }}
            QProgressBar {{
                background: {BG_DARK}; border: 1px solid {PRIMARY};
                border-radius: 3px; text-align: center; color: {SUCCESS}; font-size: 10px;
            }}
            QProgressBar::chunk {{ background: {SUCCESS}; border-radius: 2px; }}
            QLabel {{ color: {PRIMARY}; font-family: {FONT_NAME}; }}
            QStatusBar {{
                background: {BG_PANEL}; color: {PRIMARY};
                border-top: 1px solid {PRIMARY}; font-family: {FONT_NAME};
            }}
            QFrame {{ border: 1px solid {PRIMARY}; border-radius: 4px; }}
            QScrollArea {{ border: none; }}
            QMenu {{
                background: {BG_PANEL}; border: 1px solid {PRIMARY};
                color: {PRIMARY}; font-family: {FONT_NAME};
            }}
            QMenu::item {{ padding: 6px 20px; }}
            QMenu::item:selected {{ background: rgba(56,189,248,0.15); }}
            QSystemTrayIcon {{ icon: window; }}
        """

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(6)

        # Header
        header = QFrame()
        header.setStyleSheet(f"background: {BG_PANEL}; border: 1px solid {PRIMARY}; border-radius: 4px; padding: 10px;")
        header_layout = QHBoxLayout(header)
        title_label = QLabel("🤖 AURA OS v1.0 — DESKTOP")
        title_label.setStyleSheet(f"color: {PRIMARY}; font-size: 16px; font-weight: bold;")
        header_layout.addWidget(title_label)
        self.status_indicator = QLabel("● Offline")
        self.status_indicator.setStyleSheet(f"color: {ACCENT}; font-size: 12px;")
        header_layout.addStretch()
        header_layout.addWidget(self.status_indicator)
        main_layout.addWidget(header)

        # Chat section
        chat_label = QLabel("💬 Chat AURA")
        chat_label.setStyleSheet(f"color: {PRIMARY}; font-weight: bold; padding: 4px;")
        main_layout.addWidget(chat_label)

        self.chat_list = QListWidget()
        self.chat_list.setStyleSheet(f"""
            QListWidget {{ background: {BG_PANEL}; border: 1px solid {PRIMARY};
            border-radius: 4px; color: {PRIMARY}; }}
        """)
        self.chat_list.setMaximumHeight(220)
        main_layout.addWidget(self.chat_list)

        # Chat input
        input_layout = QHBoxLayout()
        self.chat_input = QPlainTextEdit()
        self.chat_input.setPlaceholderText("Escribe un mensaje para AURA...")
        self.chat_input.setMaximumHeight(60)
        input_layout.addWidget(self.chat_input)
        send_btn = QPushButton("Enviar")
        send_btn.clicked.connect(self._send_chat)
        send_btn.setStyleSheet(f"border-color: {ACCENT}; color: {ACCENT};")
        input_layout.addWidget(send_btn)
        main_layout.addLayout(input_layout)

        # Tasks section
        tasks_label = QLabel("📊 Tareas en Ejecución")
        tasks_label.setStyleSheet(f"color: {PRIMARY}; font-weight: bold; padding: 4px;")
        main_layout.addWidget(tasks_label)

        self.tasks_container = QVBoxLayout()
        self.tasks_container.setSpacing(4)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none;")
        tasks_widget = QWidget()
        tasks_widget.setLayout(self.tasks_container)
        scroll.setWidget(tasks_widget)
        main_layout.addWidget(scroll)

        # QR section
        qr_label = QLabel("📱 Pairing QR")
        qr_label.setStyleSheet(f"color: {PRIMARY}; font-weight: bold; padding: 4px;")
        main_layout.addWidget(qr_label)
        self.pairing_display = QLabel(f"Código: {self.pairing_code}\nIP: {self.local_ip}:{self.backend_port}\nVálido: 5 min")
        self.pairing_display.setStyleSheet(f"background: {BG_PANEL}; border: 1px solid {ACCENT}; border-radius: 4px; padding: 8px; color: {ACCENT}; font-size: 12px;")
        self.pairing_display.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.pairing_display)

    def _build_tray(self):
        self.tray = QSystemTrayIcon(self)
        self.tray.setToolTip("AURA Desktop")
        tray_menu = QMenu(self)
        open_action = QAction("Abrir ventana", self)
        open_action.triggered.connect(self.show)
        tray_menu.addAction(open_action)
        quit_action = QAction("Salir", self)
        quit_action.triggered.connect(self._quit)
        tray_menu.addAction(quit_action)
        self.tray.setContextMenu(tray_menu)
        self.tray.activated.connect(self._tray_activated)
        if self.tray.isSystemTrayAvailable():
            self.tray.show()

    def _start_threads(self):
        self.chat_thread = ChatThread(self.backend_port)
        self.chat_thread.message_received.connect(self._on_tasks_update)
        self.chat_thread.start()

        self.chat_msg_thread = ChatMessageThread(self.backend_port)
        self.chat_msg_thread.message_received.connect(self._on_status_update)
        self.chat_msg_thread.start()

        # Timer para actualizar status
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self._fetch_health)
        self.status_timer.start(5000)
        self._fetch_health()

    def _send_chat(self):
        text = self.chat_input.toPlainText().strip()
        if not text:
            return
        self.chat_input.clear()
        self._add_chat_message("Tú", text, is_user=True)

        def _send():
            try:
                import urllib.request
                data = json.dumps({"message": text}).encode()
                req = urllib.request.Request(
                    f"http://127.0.0.1:{self.backend_port}/api/aura/chat",
                    data=data,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    result = json.loads(resp.read().decode())
                    self._add_chat_message("AURA", result.get("response", "Sin respuesta"))
            except Exception as e:
                self._add_chat_message("AURA", f"Error: {e}")

        threading.Thread(target=_send, daemon=True).start()

    def _add_chat_message(self, sender: str, text: str, is_user: bool = False):
        if is_user:
            display = f"📝 {sender}: {text}"
            color = SUCCESS
        else:
            display = f"🤖 {sender}: {text}"
            color = PRIMARY
        item = QListWidgetItem(display)
        item.setForeground(QColor(color))
        item.setFont(QFont(FONT_NAME, 10))
        self.chat_list.addItem(item)
        self.chat_list.scrollToBottom()
        self.chat_history.append({"sender": sender, "text": text, "is_user": is_user})

    def _on_tasks_update(self, data: dict):
        tasks = data.get("tasks", [])
        self.tasks_container.takeWhile(lambda x: True)
        while self.tasks_container.count():
            child = self.tasks_container.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        for t in tasks:
            task_widget = QFrame()
            task_layout = QHBoxLayout(task_widget)
            task_layout.setContentsMargins(4, 2, 4, 2)

            name = QLabel(t.get("name", "?"))
            name.setStyleSheet(f"color: {PRIMARY}; width: 100px; font-weight: bold;")
            task_layout.addWidget(name)

            progress = QProgressBar()
            progress.setValue(t.get("progress", 0))
            progress.setTextVisible(True)
            progress.setFormat(f"{t.get('progress', 0)}%")
            progress.setStyleSheet(f"""
                QProgressBar {{ background: {BG_DARK}; border: 1px solid {PRIMARY};
                border-radius: 3px; text-align: center; color: {SUCCESS}; font-size: 10px; }}
                QProgressBar::chunk {{ background: {SUCCESS}; border-radius: 2px; }}
            """)
            progress.setFixedWidth(200)
            task_layout.addWidget(progress)

            earned = t.get("earned")
            info = QLabel(f"{t.get('status', '...')}" + (f" | ${earned:.3f}" if earned else ""))
            info.setStyleSheet(f"color: {TEXT_DIM}; font-size: 11px;")
            task_layout.addWidget(info)

            self.tasks_container.addWidget(task_widget)

        self.tasks_container.addStretch()

    def _on_status_update(self, channel: str, data: str):
        try:
            parsed = json.loads(data)
            active = parsed.get("active", False)
            if active:
                self.status_indicator.setText("● Running")
                self.status_indicator.setStyleSheet(f"color: {SUCCESS}; font-size: 12px;")
            else:
                self.status_indicator.setText("● Stopped")
                self.status_indicator.setStyleSheet(f"color: {ACCENT}; font-size: 12px;")
        except Exception:
            pass

    def _fetch_health(self):
        def _fetch():
            try:
                req = urllib.request.Request(f"http://127.0.0.1:{self.backend_port}/health")
                with urllib.request.urlopen(req, timeout=3) as resp:
                    data = json.loads(resp.read().decode())
                    if data.get("status") == "ok":
                        self._on_status_update("health", json.dumps({"active": True}))
            except Exception:
                self.status_indicator.setText("● No conexion")
                self.status_indicator.setStyleSheet(f"color: {ACCENT}; font-size: 12px;")

        threading.Thread(target=_fetch, daemon=True).start()

    def _show_qr(self):
        pass

    def _tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.show()

    def _quit(self):
        if hasattr(self, 'chat_thread'):
            self.chat_thread.stop()
            self.chat_thread.wait(2000)
        if hasattr(self, 'chat_msg_thread'):
            self.chat_msg_thread.stop()
            self.chat_msg_thread.wait(2000)
        QApplication.quit()

    def closeEvent(self, event):
        self._quit()
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = AURADesktopApp()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
