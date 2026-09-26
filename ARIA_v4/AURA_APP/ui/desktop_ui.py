"""Desktop UI — PyQt5 main window"""

import sys
from typing import Dict

try:
    from PyQt5.QtWidgets import (
        QMainWindow, QVBoxLayout, QHBoxLayout, QTextEdit, QLineEdit,
        QPushButton, QWidget, QApplication, QLabel, QListWidget,
    )
    from PyQt5.QtCore import Qt, QThread, pyqtSignal
    PYQT5_AVAILABLE = True
except ImportError:
    PYQT5_AVAILABLE = False


class IPCThread(QThread):
    """Thread IPC"""
    message_received = pyqtSignal(dict)

    def __init__(self, pipe_name: str = "aria_ipc"):
        super().__init__()
        self.pipe_name = pipe_name
        self.running = True

    def run(self):
        import time
        while self.running:
            time.sleep(0.5)

    def stop(self):
        self.running = False


class DesktopUI:
    """Interfaz principal ARIA (PyQt5)"""

    def __init__(self, engine=None):
        self.engine = engine
        self.ipc_client = None
        self.ipc_thread = None
        self.running = False

        if PYQT5_AVAILABLE:
            self.app = QApplication.instance() or QApplication(sys.argv)
            self.window = QMainWindow()
            self._init_ui()
        else:
            self.app = None
            self.window = None
            print("[DesktopUI] PyQt5 no disponible - modo consola")

    def _init_ui(self):
        self.window.setWindowTitle("ARIA v4.0")
        self.window.setGeometry(100, 100, 800, 600)

        central = QWidget()
        self.window.setCentralWidget(central)
        layout = QVBoxLayout(central)

        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setText("ARIA v4.0 — Asistente Virtual Inteligente\n\n")
        layout.addWidget(self.chat_display)

        input_layout = QHBoxLayout()
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Escribe un comando o pregunta (o 'Prendete')...")
        self.input_field.returnPressed.connect(self.send_message)
        input_layout.addWidget(self.input_field)

        send_btn = QPushButton("Enviar")
        send_btn.clicked.connect(self.send_message)
        input_layout.addWidget(send_btn)
        layout.addLayout(input_layout)

    def send_message(self):
        if not self.window:
            return
        text = self.input_field.text()
        if text.strip():
            self.chat_display.append(f"Tú: {text}")
            self.input_field.clear()

            if self.engine:
                import asyncio
                result = asyncio.run(self.engine.process_input(text))
                response = result.get('intent', 'unknown')
                self.chat_display.append(f"ARIA: [{response}]\n")

    def run(self):
        if PYQT5_AVAILABLE and self.window:
            self.window.show()
            self.app.exec_()
        else:
            print("[DesktopUI] Modo consola - ingresa mensajes:")
            try:
                while True:
                    text = input("tú: ").strip()
                    if text.lower() == 'salir':
                        break
                    self.send_message()
            except KeyboardInterrupt:
                pass


if __name__ == "__main__":
    ui = DesktopUI()
    ui.run()
