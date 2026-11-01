# -*- coding: utf-8 -*-
"""Smoke test del panel de Memoria de ARIA (PyQt5, sin ventana real).

Se ejecuta con QT_QPA_PLATFORM=offscreen: la UI es nativa, pero el test
no necesita display. Si PyQt5 no esta disponible, el test se salta.

El nucleo VA real (que carga torch) no se instancia: se usa un sustituto
minimo para el enrutado del VAAdapter, que es lo que se quiere comprobar.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ARIA_APP = Path(__file__).resolve().parent.parent / "ARIA_APP"
if str(ARIA_APP) not in sys.path:
    sys.path.insert(0, str(ARIA_APP))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PyQt5")

from PyQt5.QtWidgets import QApplication, QMessageBox  # noqa: E402


class StubVA:
    """Lo mismo que el nucleo VA, pero sin cargar el modelo local."""

    def __init__(self, core):
        self._core = core

    def memory_list(self, capa="", limite=50):
        return self._core.memory_listar(capa, limite=limite)

    def memory_conteo(self):
        return self._core.memory_conteo()

    def memory_enabled(self):
        return self._core._memory_enabled()

    def memory_borrar(self, capa, id_):
        return self._core.memory_borrar(capa, id_)

    def memory_fijar(self, texto):
        return self._core.memory_fijar(texto)

    def memory_reflect(self):
        return self._core.memory_reflect()

    def memory_export(self):
        return self._core.memory_exportar()

    def memory_recall(self, consulta, k=5):
        return self._core.memory_recall(consulta, k=k)

    def memory_set_enabled(self, activo):
        return self._core.set_memory_enabled(activo)

    def memory_add(self, texto, capa="observaciones", fuente="usuario",
                   confianza="usuario"):
        return self._core.memory_agregar(texto, capa=capa, fuente=fuente,
                                         confianza=confianza)

    def memory_import(self, ruta=""):
        return self._core.memory_importar_archivo(ruta) if ruta else \
            self._core.memory_importar_conversaciones()

    def memory_session_add(self, texto, capa="observaciones"):
        return self._core.memory_session_add(texto, capa=capa)

    def memory_session_list(self):
        return self._core.memory_session_list()

    def memory_session_clear(self):
        return self._core.memory_session_clear()


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


@pytest.fixture()
def core(tmp_path, monkeypatch):
    """Nucleo con la memoria en una base temporal y encendida."""
    monkeypatch.setenv("ARIA_MEMORY_SQLITE", "true")
    monkeypatch.setenv("ARIA_MEMORY_DB", str(tmp_path / "ui.db"))
    import aria_va_core

    aria_va_core._memory_adapter_cache.clear()
    aria_va_core.memory_session_clear()
    aria_va_core.set_memory_enabled(True)
    yield aria_va_core
    aria_va_core.memory_session_clear()
    aria_va_core.set_memory_enabled(None)
    aria_va_core._memory_adapter_cache.clear()


@pytest.fixture()
def panel(qapp, core, monkeypatch):
    import desktop_ui

    monkeypatch.setattr(
        QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.Yes)
    )
    va = desktop_ui.VAAdapter.__new__(desktop_ui.VAAdapter)
    va.va = StubVA(core)
    p = desktop_ui.MemoryPanel(va)
    yield p
    p.close()


def test_panel_nace_activo(panel):
    assert "Activa" in panel.state_lbl.text()


def test_panel_lista_lo_guardado(panel, core):
    core.memory_retain("el usuario prefiere respuestas cortas", tipo="observaciones")
    panel._refresh()
    assert len(panel._entries) == 1
    assert panel._entries[0]["capa"] == "observaciones"


def test_panel_filtra_por_capa(panel, core):
    core.memory_retain("un hecho", tipo="hechos")
    core.memory_fijar("una regla del usuario")
    panel.capa_combo.setCurrentIndex(2)
    panel._refresh()
    assert len(panel._entries) == 1
    assert panel._entries[0]["capa"] == "hechos"


def test_panel_busca(panel, core):
    core.memory_retain("el usuario prefiere respuestas cortas", tipo="observaciones")
    core.memory_retain("otra cosa distinta", tipo="hechos")
    panel.search_input.setText("respuestas")
    panel._search()
    assert len(panel._entries) == 1
    assert "respuestas cortas" in panel._entries[0]["texto"]


def test_panel_fija_como_regla(panel, core):
    core.memory_retain("una regla candidata", tipo="observaciones")
    panel._refresh()
    panel.table.selectRow(0)
    panel._fijar()
    reglas = core.memory_reglas()
    assert any(r["texto"] == "una regla candidata" for r in reglas)


def test_panel_borra(panel, core):
    rid = core.memory_retain("para borrar desde la UI", tipo="hechos")
    panel._refresh()
    panel.table.selectRow(0)
    panel._borrar()
    panel._refresh()
    assert all(e["id"] != rid for e in panel._entries)


def test_panel_consolida(panel, core):
    for _ in range(3):
        core.memory_retain("se repite mucho", tipo="observaciones")
    panel._refresh()
    panel._consolidar()
    modelos = core.memory_listar("modelos")
    assert any("se repite mucho" in m["texto"] for m in modelos)


def test_panel_apaga_la_memoria(panel):
    panel._toggle()
    assert "Inactiva" in panel.state_lbl.text()
    panel._toggle()
    assert "Activa" in panel.state_lbl.text()


# -- alta manual, importacion y recuerdos de sesion ---------------------------

def test_panel_guarda_una_entrada_a_mano(panel, core):
    panel.new_input.setText("el servidor es el de produccion")
    panel.new_capa_combo.setCurrentIndex(panel.new_capa_combo.findData("hechos"))
    panel._guardar()
    hechos = core.memory_listar("hechos")
    assert any(h["texto"] == "el servidor es el de produccion" for h in hechos)
    assert panel.new_input.text() == ""


def test_panel_no_guarda_texto_vacio(panel, core):
    panel.new_input.setText("   ")
    panel._guardar()
    assert core.memory_listar("hechos") == []


def test_panel_importa_un_json(panel, core, tmp_path, monkeypatch):
    import desktop_ui
    import json as _json

    archivo = tmp_path / "memoria.json"
    archivo.write_text(
        _json.dumps([{"capa": "hechos", "texto": "importado desde la UI"}]),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        desktop_ui.QFileDialog, "getOpenFileName",
        staticmethod(lambda *a, **k: (str(archivo), "")),
    )
    panel._importar()
    assert any(h["texto"] == "importado desde la UI"
               for h in core.memory_listar("hechos"))


def test_panel_muestra_los_recuerdos_de_sesion(panel, core):
    core.memory_session_add("recuerdo de esta sesion")
    indice = panel.capa_combo.findData("sesion")
    assert indice >= 0
    panel.capa_combo.setCurrentIndex(indice)
    panel._refresh()
    assert len(panel._entries) == 1
    assert panel._entries[0]["capa"] == "sesion"


def test_panel_recorda_en_la_sesion(panel, core):
    panel.new_input.setText("recuerdo rapido")
    panel._recordar()
    assert any("recuerdo rapido" in s["texto"]
               for s in core.memory_session_list())


def test_panel_vacia_la_sesion(panel, core):
    core.memory_session_add("uno")
    core.memory_session_add("dos")
    panel._vaciar_sesion()
    assert core.memory_session_list() == []


def test_panel_borra_un_recuerdo_de_sesion(panel, core):
    rid = core.memory_session_add("para borrar de la sesion")
    indice = panel.capa_combo.findData("sesion")
    panel.capa_combo.setCurrentIndex(indice)
    panel._refresh()
    panel.table.selectRow(0)
    panel._borrar()
    assert core.memory_session_list() == []
