import sys
import json
import requests
from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTextEdit,
    QLineEdit,
    QPushButton,
    QCheckBox,
    QSystemTrayIcon,
    QMenu,
)
from PyQt6.QtGui import QIcon, QTextCursor
from PyQt6.QtCore import Qt, QThread, pyqtSignal

API_URL = "http://localhost:8000/chat"


class SendWorker(QThread):
    response_received = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, message: str):
        super().__init__()
        self.message = message

    def run(self):
        try:
            r = requests.post(
                API_URL,
                json={"message": self.message},
                timeout=120,
            )
            if r.status_code == 200:
                data = r.json()
                text = data.get("response", "Sin respuesta.")
            else:
                text = f"Error {r.status_code}: {r.text}"
        except Exception as e:
            text = f"Error de conexión: {e}"
        self.response_received.emit(text)


class AuraDesktop(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowSystemMenuHint
        )
        self.setWindowTitle("AURA Desktop")
        self.resize(480, 640)
        self.apply_style()

        # System Tray
        self.tray = QSystemTrayIcon(self)
        # Icono genérico (se puede reemplazar por uno propio)
        self.tray.setVisible(True)
        tray_menu = QMenu()
        action_open = tray_menu.addAction("Abrir AURA")
        action_open.triggered.connect(self.show_normal)
        action_status = tray_menu.addAction("Ver Estado del Servidor")
        action_status.triggered.connect(self.check_server)
        tray_menu.addSeparator()
        action_exit = tray_menu.addAction("Salir")
        action_exit.triggered.connect(QApplication.instance().quit)
        self.tray.setContextMenu(tray_menu)
        self.tray.activated.connect(self.on_tray_activated)

        # Layout
        vbox = QVBoxLayout(self)
        self.chat = QTextEdit()
        self.chat.setReadOnly(True)
        vbox.addWidget(self.chat)

        hbox = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText("Escribe a AURA...")
        self.input.returnPressed.connect(self.send)
        hbox.addWidget(self.input)

        self.btn_send = QPushButton("Enviar")
        self.btn_send.clicked.connect(self.send)
        hbox.addWidget(self.btn_send)

        vbox.addLayout(hbox)

        self.chk_always_on_top = QCheckBox("Siempre al frente")
        self.chk_always_on_top.setChecked(True)
        self.chk_always_on_top.toggled.connect(self.toggle_always_on_top)
        vbox.addWidget(self.chk_always_on_top)

        self.worker: SendWorker | None = None

    def apply_style(self):
        self.setStyleSheet("""
            QWidget {
                background-color: #0b0f14;
                color: #c8d3e2;
                font-family: Segoe UI, Roboto, Helvetica, Arial;
                font-size: 13px;
            }
            QTextEdit {
                background-color: #0f1720;
                border: 1px solid #1f2a36;
                border-radius: 6px;
                padding: 8px;
            }
            QLineEdit {
                background-color: #0f1720;
                border: 1px solid #1f2a36;
                border-radius: 6px;
                padding: 6px;
            }
            QPushButton {
                background-color: #0f2a3f;
                color: #dbe9ff;
                border: 1px solid #1f3a56;
                border-radius: 6px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #143856;
            }
            QCheckBox {
                spacing: 6px;
            }
            """)

    def on_tray_activated(self, reason):
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.show_normal()

    def show_normal(self):
        self.show()
        self.raise_()
        self.activateWindow()

    def toggle_always_on_top(self, checked: bool):
        flags = self.windowFlags()
        if checked:
            self.setWindowFlags(flags | Qt.WindowType.WindowStaysOnTopHint)
        else:
            self.setWindowFlags(flags & ~Qt.WindowType.WindowStaysOnTopHint)
        self.show()

    def check_server(self):
        try:
            r = requests.get("http://localhost:8000/health", timeout=10)
            if r.status_code == 200:
                self.append_system("Servidor AURA: EN LÍNEA")
            else:
                self.append_system(f"Servidor AURA: HTTP {r.status_code}")
        except Exception as e:
            self.append_system(f"Servidor AURA: NO ALCANZABLE ({e})")

    def append_system(self, text: str):
        self.chat.moveCursor(QTextCursor.MoveOperation.End)
        self.chat.insertPlainText(f"[SYSTEM] {text}\n")
        self.chat.moveCursor(QTextCursor.MoveOperation.End)

    def append_user(self, text: str):
        self.chat.moveCursor(QTextCursor.MoveOperation.End)
        self.chat.insertPlainText(f"[TÚ] {text}\n")
        self.chat.moveCursor(QTextCursor.MoveOperation.End)

    def append_assistant(self, text: str):
        self.chat.moveCursor(QTextCursor.MoveOperation.End)
        self.chat.insertPlainText(f"[AURA] {text}\n")
        self.chat.moveCursor(QTextCursor.MoveOperation.End)

    def send(self):
        text = self.input.text().strip()
        if not text:
            return
        self.append_user(text)
        self.input.clear()
        self.btn_send.setEnabled(False)
        self.worker = SendWorker(text)
        self.worker.response_received.connect(self.on_response)
        self.worker.error_occurred.connect(self.on_error)
        self.worker.start()

    def on_response(self, text: str):
        self.append_assistant(text)
        self.btn_send.setEnabled(True)

    def on_error(self, text: str):
        self.append_system(text)
        self.btn_send.setEnabled(True)

    def closeEvent(self, event):
        # Ocultar en lugar de cerrar
        if self.tray.isVisible():
            self.hide()
            event.ignore()


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    w = AuraDesktop()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
