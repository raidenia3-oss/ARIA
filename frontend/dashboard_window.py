"""Dashboard de Operaciones y Configuración para AURA — Module 30.

Panel PySide6 accesible desde la bandeja del sistema del HUD con 4 pestañas:
- Modelos & IA: gestión e importación de modelos locales (Ollama/GGUF).
- Personajes: visualización y carga de tarjetas PNG V2/JSON.
- Enjambre & Tareas: monitor de tareas activas y consola de logs en tiempo real.
- Estado del Sistema: indicadores de salud, métricas y circuit breakers.

Se comunica con el backend AURA vía REST API (requests).
"""

from __future__ import annotations

import os
import sys
import json
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests

from PySide6.QtCore import Qt, QTimer, Signal, QThread, QSize
from PySide6.QtGui import QFont, QColor, QIcon
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QPushButton,
    QLabel, QTableWidget, QTableWidgetItem, QTextEdit, QInputDialog,
    QMessageBox, QHeaderView, QProgressBar, QStyle,
)

DEFAULT_BASE_URL = os.getenv("AURA_API_URL", "http://localhost:8000")


class APIWorker(QThread):
    """Worker thread para peticiones API no bloqueantes."""
    result_ready = Signal(str, object)
    error_occurred = Signal(str, str)

    def __init__(self, method: str, path: str, base_url: str = DEFAULT_BASE_URL, **kwargs) -> None:
        super().__init__()
        self.method = method
        self.path = path
        self.base_url = base_url
        self.kwargs = kwargs

    def run(self) -> None:
        try:
            resp = requests.request(
                self.method, f"{self.base_url}{self.path}", timeout=15, **self.kwargs
            )
            resp.raise_for_status()
            try:
                data = resp.json()
            except ValueError:
                data = {"raw": resp.text}
            self.result_ready.emit(self.path, data)
        except Exception as exc:
            self.error_occurred.emit(self.path, str(exc))


class RefreshableTab(QWidget):
    """Pestaña base con botón de actualización y temporizador de refresco."""

    def __init__(self, base_url: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.base_url = base_url
        self._setup_base_ui()

    def _setup_base_ui(self) -> None:
        self._layout = QVBoxLayout(self)
        self._header = QHBoxLayout()
        self._title = QLabel()
        self._title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        self._refresh_btn = QPushButton("↻ Actualizar")
        self._refresh_btn.clicked.connect(self._on_refresh)
        self._status_label = QLabel("Listo")
        self._status_label.setStyleSheet("color: gray; font-size: 11px;")
        self._header.addWidget(self._title)
        self._header.addStretch()
        self._header.addWidget(self._status_label)
        self._header.addWidget(self._refresh_btn)
        self._layout.addLayout(self._header)
        self._content = QVBoxLayout()
        self._layout.addLayout(self._content)

    def _set_title(self, title: str) -> None:
        self._title.setText(title)

    def _set_status(self, msg: str, error: bool = False) -> None:
        color = "red" if error else "gray"
        self._status_label.setStyleSheet(f"color: {color}; font-size: 11px;")
        self._status_label.setText(msg)

    def _on_refresh(self) -> None:
        self._set_status("Actualizando...")
        worker = APIWorker("GET", self._api_path, base_url=self.base_url)
        worker.result_ready.connect(self._on_api_result)
        worker.error_occurred.connect(self._on_api_error)
        worker.start()

    _api_path: str = "/"

    def _on_api_result(self, path: str, data: Any) -> None:
        self._set_status("Actualizado")

    def _on_api_error(self, path: str, error: str) -> None:
        self._set_status(f"Error: {error[:50]}", error=True)


class ModelsTab(RefreshableTab):
    _api_path = "/api/local-ai/models"

    def __init__(self, base_url: str) -> None:
        super().__init__(base_url)
        self._set_title("Modelos & IA")
        self._table = QTableWidget()
        self._table.setColumnCount(2)
        self._table.setHorizontalHeaderLabels(["Modelo", "Proveedor"])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.StretchMode.Stretch)
        self._table.verticalHeader().setVisible(False)
        self._pull_btn = QPushButton("⬇️ Importar Modelo")
        self._pull_btn.clicked.connect(self._on_pull_model)
        self._content.addWidget(self._table)
        self._content.addWidget(self._pull_btn)
        self._on_refresh()

    def _on_pull_model(self) -> None:
        name, ok = QInputDialog.getText(self, "Importar Modelo", "Nombre del modelo (ej: llama3.2:latest):")
        if ok and name:
            worker = APIWorker("POST", "/api/local-ai/models", base_url=self.base_url,
                               json={"model_name": name})
            worker.result_ready.connect(lambda p, d: self._set_status(f"Modelo importado: {d.get('status')}"))
            worker.error_occurred.connect(lambda p, e: self._set_status(f"Error: {e[:50]}", error=True))
            worker.start()

    def _on_api_result(self, path: str, data: Any) -> None:
        models = data.get("models", [])
        self._table.setRowCount(len(models))
        for i, model in enumerate(models):
            self._table.setItem(i, 0, QTableWidgetItem(str(model.get("name", model.get("model", "?")))))
            self._table.setItem(i, 1, QTableWidgetItem(str(model.get("provider", "local"))))
        self._table.setRowCount(len(models))
        self._set_status(f"{len(models)} modelos")


class PersonasTab(RefreshableTab):
    _api_path = "/api/personas/cards"

    def __init__(self, base_url: str) -> None:
        super().__init__(base_url)
        self._set_title("Personajes")
        self._table = QTableWidget()
        self._table.setColumnCount(3)
        self._table.setHorizontalHeaderLabels(["Nombre", "Descripcion", "Tags"])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.StretchMode.Stretch)
        self._table.verticalHeader().setVisible(False)
        self._import_btn = QPushButton("📥 Importar Tarjeta")
        self._import_btn.clicked.connect(self._on_import)
        self._content.addWidget(self._table)
        self._content.addWidget(self._import_btn)
        self._on_refresh()

    def _on_import(self) -> None:
        card_json, ok = QInputDialog.getMultiLineText(self, "Importar Personaje", "JSON de la tarjeta:", "")
        if ok and card_json.strip():
            try:
                data = json.loads(card_json)
            except json.JSONDecodeError:
                QMessageBox.critical(self, "Error", "JSON invalido")
                return
            worker = APIWorker("POST", "/api/personas/cards", base_url=self.base_url,
                               json={"source": "json", "data": data})
            worker.result_ready.connect(lambda p, d: self._set_status(f"Importado: {d.get('status')}"))
            worker.error_occurred.connect(lambda p, e: self._set_status(f"Error: {e[:50]}", error=True))
            worker.start()

    def _on_api_result(self, path: str, data: Any) -> None:
        cards = data.get("cards", [])
        self._table.setRowCount(len(cards))
        for i, card in enumerate(cards):
            self._table.setItem(i, 0, QTableWidgetItem(card.get("name", "?")))
            self._table.setItem(i, 1, QTableWidgetItem(card.get("description", "")[:50]))
            self._table.setItem(i, 2, QTableWidgetItem(", ".join(card.get("tags", []))))
        self._set_status(f"{len(cards)} personajes")


class SwarmTab(RefreshableTab):
    _api_path = "/api/swarm/tasks"

    def __init__(self, base_url: str) -> None:
        super().__init__(base_url)
        self._set_title("Enjambre & Tareas")
        self._task_table = QTableWidget()
        self._task_table.setColumnCount(4)
        self._task_table.setHorizontalHeaderLabels(["ID", "Descripcion", "Estado", "Resultado"])
        self._task_table.horizontalHeader().setSectionResizeMode(QHeaderView.StretchMode.Stretch)
        self._task_table.verticalHeader().setVisible(False)

        self._log_console = QTextEdit()
        self._log_console.setReadOnly(True)
        self._log_console.setMaximumHeight(200)
        self._log_console.setFont(QFont("Courier", 9))

        self._submit_btn = QPushButton("➕ Nueva Tarea")
        self._submit_btn.clicked.connect(self._on_submit_task)

        self._content.addWidget(QLabel("Tareas Activas:"))
        self._content.addWidget(self._task_table)
        self._content.addWidget(QLabel("Logs de Auditoria:"))
        self._content.addWidget(self._log_console)
        self._content.addWidget(self._submit_btn)

        self._audit_timer = QTimer()
        self._audit_timer.timeout.connect(self._fetch_audit_logs)
        self._audit_timer.start(3000)
        self._on_refresh()

    def _on_refresh(self) -> None:
        self._set_status("Cargando tareas...")
        worker = APIWorker("GET", "/api/swarm/tasks", base_url=self.base_url)
        worker.result_ready.connect(self._on_tasks_result)
        worker.error_occurred.connect(self._on_api_error)
        worker.start()

    def _on_tasks_result(self, path: str, data: Any) -> None:
        tasks = data.get("tasks", [])
        self._task_table.setRowCount(len(tasks))
        for i, task in enumerate(tasks):
            self._task_table.setItem(i, 0, QTableWidgetItem(str(task.get("id", task.get("task_id", "?")))))
            self._task_table.setItem(i, 1, QTableWidgetItem(str(task.get("description", ""))[:40]))
            self._task_table.setItem(i, 2, QTableWidgetItem(str(task.get("status", ""))))
            self._task_table.setItem(i, 3, QTableWidgetItem(str(task.get("result", ""))[:30]))
        self._set_status(f"{len(tasks)} tareas")

    def _on_submit_task(self) -> None:
        desc, ok = QInputDialog.getText(self, "Nueva Tarea", "Descripcion:")
        if ok and desc:
            worker = APIWorker("POST", "/api/swarm/tasks", base_url=self.base_url,
                               json={"description": desc, "priority": "normal", "max_subtasks": 3, "execute": True})
            worker.result_ready.connect(lambda p, d: self._set_status(f"Tarea: {d.get('status')}"))
            worker.error_occurred.connect(lambda p, e: self._set_status(f"Error: {e[:50]}", error=True))
            worker.start()

    def _fetch_audit_logs(self) -> None:
        worker = APIWorker("GET", "/api/production/audit-logs", base_url=self.base_url)
        worker.result_ready.connect(self._on_audit_result)
        worker.start()

    def _on_audit_result(self, path: str, data: Any) -> None:
        events = data.get("events", [])
        lines = []
        for event in events[-20:]:
            ts = event.get("created_at", "")
            action = event.get("action", "?")
            result = event.get("result", "?")
            lines.append(f"[{ts}] {action}: {result}")
        self._log_console.setPlainText("\n".join(lines))


class SystemTab(RefreshableTab):
    _api_path = "/api/system/status/full"

    def __init__(self, base_url: str) -> None:
        super().__init__(base_url)
        self._set_title("Estado del Sistema")
        self._health_status = QLabel("Cargando...")
        self._module_status = QTableWidget()
        self._module_status.setColumnCount(3)
        self._module_status.setHorizontalHeaderLabels(["Modulo", "Estado", "Fallos"])
        self._module_status.horizontalHeader().setSectionResizeMode(QHeaderView.StretchMode.Stretch)
        self._cb_status = QTableWidget()
        self._cb_status.setColumnCount(3)
        self._cb_status.setHorizontalHeaderLabels(["Modulo", "Estado", "Fallos"])
        self._cb_status.horizontalHeader().setSectionResizeMode(QHeaderView.StretchMode.Stretch)

        self._content.addWidget(self._health_status)
        self._content.addWidget(QLabel("Modulos:"))
        self._content.addWidget(self._module_status)
        self._content.addWidget(QLabel("Circuit Breakers:"))
        self._content.addWidget(self._cb_status)
        self._on_refresh()

        self._timer = QTimer()
        self._timer.timeout.connect(self._on_refresh)
        self._timer.start(5000)

    def _on_api_result(self, path: str, data: Any) -> None:
        health = data.get("system_health", {})
        healthy = health.get("healthy", 0)
        total = health.get("total", 0)
        degraded = health.get("degraded", 0)
        critical = health.get("critical", 0)
        self._health_status.setText(
            f"Modulos: {healthy}/{total} saludables | Degradados: {degraded} | Criticos: {critical}"
        )

        modules = data.get("modules", [])
        self._module_status.setRowCount(len(modules))
        for i, mod in enumerate(modules):
            self._module_status.setItem(i, 0, QTableWidgetItem(mod))
            self._module_status.setItem(i, 1, QTableWidgetItem("OK"))
            self._module_status.setItem(i, 2, QTableWidgetItem("0"))

        breakers = data.get("circuit_breakers", [])
        self._cb_status.setRowCount(len(breakers))
        for i, cb in enumerate(breakers):
            self._cb_status.setItem(i, 0, QTableWidgetItem(cb.get("module", "")))
            self._cb_status.setItem(i, 1, QTableWidgetItem(cb.get("state", "")))
            self._cb_status.setItem(i, 2, QTableWidgetItem(str(cb.get("failure_count", 0))))
        self._set_status(f"Total: {total}, saludables: {healthy}")


class DashboardWindow(QWidget):
    """Ventana principal del panel de control."""

    def __init__(self, base_url: str = DEFAULT_BASE_URL) -> None:
        super().__init__()
        self.base_url = base_url
        self.setWindowTitle("AURA Dashboard")
        self.resize(900, 650)

        icon = QIcon()
        icon.addPixmap(self._app_icon(), QIcon.Mode.Normal, QIcon.State.Off)
        self.setWindowIcon(icon)

        layout = QVBoxLayout(self)
        self._tabs = QTabWidget()
        self._tabs.addTab(ModelsTab(base_url), "Modelos & IA")
        self._tabs.addTab(PersonasTab(base_url), "Personajes")
        self._tabs.addTab(SwarmTab(base_url), "Enjambre & Tareas")
        self._tabs.addTab(SystemTab(base_url), "Estado del Sistema")
        layout.addWidget(self._tabs)

    def _app_icon(self) -> QPixmap:
        app = QIcon()
        return app.pixmap(32, 32)

    def show_and_raise(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()
