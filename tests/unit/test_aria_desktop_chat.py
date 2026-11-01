"""El chat de ARIA no puede tumbar la app.

El 2026-10-21 la barra de acciones (Copiar / Guardar / Refine) era codigo de
QtWebEngine aplicado a un QTextEdit: `chat_history.page()` reventaba con
AttributeError 1,8 s despues de cada respuesta. PyQt5 aborta el proceso
cuando una excepcion escapa de un slot, asi que ARIA se caia cada vez que
el usuario escribia algo.

Este test recorre el camino completo (mensaje -> respuesta -> acciones) y
comprueba que no se escapa ninguna excepcion y que la respuesta se ve.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for _path in (str(ROOT), str(ROOT / "ARIA_APP")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PyQt5")

from PyQt5.QtCore import QEventLoop, QTimer  # noqa: E402
from PyQt5.QtWidgets import QApplication  # noqa: E402


class StubSkills:
    """Skills de mentira: registran lo que se les pide."""

    def __init__(self) -> None:
        self.calls = []

    def list(self):
        return []

    def run(self, skill_id, params):
        self.calls.append((skill_id, params))
        return {"status": "ok", "result": {"path": params.get("path", ""), "bytes": 0}}


class StubVA:
    """El nucleo VA sin cargar el modelo: solo lo que el chat necesita."""

    def __init__(self) -> None:
        self.autonomous = False
        self.last = ""
        self.skills = StubSkills()

    def process_text(self, text: str) -> str:
        self.last = text
        return f"Respuesta local a: {text}"

    def get_status(self) -> dict:
        return {"mode": "100% local", "skills": 10, "model": "rules"}


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


@pytest.fixture()
def ventana(qapp):
    import desktop_ui

    adapter = desktop_ui.VAAdapter.__new__(desktop_ui.VAAdapter)
    adapter.va = StubVA()
    adapter.healthy = True
    window = desktop_ui.ChatWindow(adapter)

    # Lo mismo que hace run_desktop al recibir una respuesta.
    def on_response(resultado):
        respuesta = resultado.get("response", "")
        window._append_streaming("ARIA", respuesta, "#38bdf8", "src:local")
        QTimer.singleShot(100, lambda: window._add_action_buttons(respuesta))

    window.response_received.connect(on_response)
    yield window
    window.close()


def _pump(ms: int = 1500) -> None:
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec_()


def test_la_app_no_muere_al_responder(ventana, monkeypatch):
    """Mensaje -> respuesta -> acciones, sin que se escape nada."""
    errores = []
    monkeypatch.setattr(sys, "excepthook", lambda t, v, tb: errores.append((t, v)))

    ventana.msg_input.setText("hola ARIA")
    ventana._send_message()
    _pump(1500)

    assert not errores, f"la excepcion se escapo del slot: {errores}"
    assert "Respuesta local" in ventana.chat_history.toPlainText()
    assert ventana.act_copy.isEnabled()


def test_las_acciones_nativas_no_usan_motor_web():
    """Ni una llamada a QtWebEngine: esto es una ventana, no una pagina."""
    import inspect

    import desktop_ui

    for metodo in ("_add_action_buttons", "_act_copy", "_act_save", "_act_refine"):
        fuente = inspect.getsource(getattr(desktop_ui.ChatWindow, metodo))
        codigo = fuente.split('"""')[-1]
        assert ".page()" not in codigo, metodo
        assert "evaluateJavaScript" not in codigo, metodo


def test_copiar_deja_la_respuesta_en_el_portapapeles(ventana):
    ventana._last_response_text = "texto para copiar"
    ventana._act_copy()

    assert QApplication.clipboard().text() == "texto para copiar"


def test_refine_devuelve_el_texto_al_cuadro(ventana):
    ventana._last_response_text = "pulsa esto"
    ventana._act_refine()

    assert ventana.msg_input.text() == "pulsa esto"


def test_guardar_pide_que_se_escriba_el_archivo(ventana):
    ventana._last_response_text = "cinco"
    ventana._act_save()

    llamadas = ventana.va.va.skills.calls
    assert llamadas, "guardar deberia pasar por la skill de escribir"
    skill_id, params = llamadas[-1]
    assert skill_id == "file_write"
    assert params.get("content") == "cinco"
    assert params.get("path", "").endswith(".txt")


def test_aria_sin_generador_sigue_contestando(ventana):
    """Sin modelo, ARIA contesta igual: el chat no depende de un generador."""
    ventana.va.va.process_text = lambda text: "sin modelo, pero contesto"
    ventana.msg_input.setText("hola")
    ventana._send_message()
    _pump(1500)

    assert "contesto" in ventana.chat_history.toPlainText()
