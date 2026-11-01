# -*- coding: utf-8 -*-
"""Tests del adaptador de memoria SQLite de ARIA (5 capas + FTS5).

Solo biblioteca estandar: no red, no puertos, no dependencias nuevas.
La base se crea en un temporal (ARIA_MEMORY_DB), nunca en la de ARIA.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import sys
from pathlib import Path

import pytest

ARIA_APP = Path(__file__).resolve().parent.parent / "ARIA_APP"
ADAPTER_PATH = ARIA_APP / "memory" / "sqlite_adapter.py"

if str(ARIA_APP) not in sys.path:
    sys.path.insert(0, str(ARIA_APP))


def _load_adapter(db_path: Path):
    """Carga el adaptador con la base en un temporal."""
    os.environ["ARIA_MEMORY_DB"] = str(db_path)
    spec = importlib.util.spec_from_file_location("aria_mem_test_adapter", str(ADAPTER_PATH))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def adapter(tmp_path, monkeypatch):
    monkeypatch.setenv("ARIA_MEMORY_SQLITE", "true")
    module = _load_adapter(tmp_path / "mem.db")
    module.set_enabled(True)
    yield module
    module.set_enabled(None)


@pytest.fixture()
def core(tmp_path, monkeypatch):
    """El nucleo VA con la memoria apuntando a una base temporal."""
    monkeypatch.setenv("ARIA_MEMORY_SQLITE", "true")
    monkeypatch.setenv("ARIA_MEMORY_DB", str(tmp_path / "core.db"))
    import aria_va_core

    aria_va_core._memory_adapter_cache.clear()
    yield aria_va_core
    aria_va_core._memory_adapter_cache.clear()


# -- flag ---------------------------------------------------------------------

def test_flag_apagado_no_guarda_nada(tmp_path, monkeypatch):
    monkeypatch.setenv("ARIA_MEMORY_SQLITE", "false")
    module = _load_adapter(tmp_path / "off.db")
    module.set_enabled(None)
    assert module.get_adapter().retain("algo que no se guarda") is None
    assert module.get_adapter().recall("algo") == []


def test_flag_apagado_no_toca_la_base(tmp_path, monkeypatch):
    monkeypatch.setenv("ARIA_MEMORY_SQLITE", "false")
    module = _load_adapter(tmp_path / "off2.db")
    module.set_enabled(None)
    module.get_adapter().retain("nada")
    assert not (tmp_path / "off2.db").exists()


def test_interruptor_en_caliente(adapter):
    adapter.set_enabled(False)
    assert adapter.get_adapter().retain("fuera") is None
    assert adapter.get_adapter().recall("fuera") == []
    adapter.set_enabled(True)
    assert adapter.get_adapter().retain("dentro") is not None


# -- capas --------------------------------------------------------------------

def test_retain_en_cada_capa(adapter):
    db = adapter.get_adapter()
    for capa in adapter.LAYERS:
        rid = db.retain(f"contenido de la capa {capa}", tipo=capa)
        assert rid is not None, capa
    listado = db.listar(limite=50)
    capas = {e["capa"] for e in listado}
    assert capas == set(adapter.LAYERS)


def test_listar_filtra_por_capa(adapter):
    db = adapter.get_adapter()
    db.retain("hecho numero uno", tipo="hechos")
    db.retain("regla del usuario", tipo="reglas", confianza="usuario")
    reglas = db.listar("reglas")
    assert len(reglas) == 1
    assert reglas[0]["texto"] == "regla del usuario"
    assert reglas[0]["confianza"] == "usuario"


# -- saneado ------------------------------------------------------------------

@pytest.mark.parametrize("texto", [
    "password: SuperSecreto123",
    "api_key=AKIAIOSFODNN7EXAMPLE",
    "Bearer eyJhbGciOiJIUzI1NiJ9.abc.def",
    "sk-abcdefghijklmnopqrstuvwxyz012345",
    "ghp_abcdefghijklmnopqrstuvwxyz012345",
])
def test_no_guarda_credenciales(adapter, texto):
    assert adapter.get_adapter().retain(texto) is None


def test_no_guarda_vacio(adapter):
    assert adapter.get_adapter().retain("   ") is None
    assert adapter.get_adapter().retain("") is None


# -- recall -------------------------------------------------------------------

def test_recall_encuentra_lo_guardado(adapter):
    db = adapter.get_adapter()
    db.retain("el usuario prefiere respuestas cortas", tipo="observaciones")
    hits = db.recall("respuestas cortas", k=5)
    assert len(hits) == 1
    assert hits[0]["capa"] == "observaciones"
    assert "prefiere respuestas cortas" in hits[0]["texto"]


def test_recall_busca_en_todas_las_capas(adapter):
    db = adapter.get_adapter()
    db.retain("regla fija del usuario", tipo="reglas", confianza="usuario")
    db.retain("hecho comprobable", tipo="hechos")
    assert len(db.recall("regla fija", k=5)) == 1
    assert len(db.recall("hecho comprobable", k=5)) == 1


def test_recall_texto_vacio_no_revienta(adapter):
    assert adapter.get_adapter().recall("") == []
    assert adapter.get_adapter().recall("   ") == []


def test_recall_texto_con_comillas_no_rompe(adapter):
    db = adapter.get_adapter()
    db.retain('el texto con "comillas" y parentesis (raros)', tipo="hechos")
    assert isinstance(db.recall('comillas " rar', k=5), list)


def test_recall_con_signos_raros(adapter):
    db = adapter.get_adapter()
    db.retain("ARIA responde en espanol, siempre", tipo="hechos")
    hits = db.recall("¿que es ARIA?", k=5)
    assert len(hits) == 1
    assert "responde en espanol" in hits[0]["texto"]


def test_recall_con_operadores_fts_no_revienta(adapter):
    db = adapter.get_adapter()
    db.retain("una entrada normal", tipo="hechos")
    for consulta in ('"', "AND OR NOT", "a*", "(", "colonna* NEAR", "^^^"):
        assert isinstance(db.recall(consulta, k=5), list)


# -- evidencia y reflect ------------------------------------------------------

def test_observaciones_repetidas_suben_evidencia(adapter):
    db = adapter.get_adapter()
    for _ in range(3):
        db.retain("el usuario habla poco", tipo="observaciones")
    obs = [e for e in db.listar("observaciones") if e["texto"] == "el usuario habla poco"]
    assert len(obs) == 1
    assert obs[0]["evidencia"] == 3


def test_reflect_promueve_a_modelos(adapter):
    db = adapter.get_adapter()
    for _ in range(3):
        db.retain("siempre pide cafe", tipo="observaciones")
    promovidas = db.reflect_basico()
    assert promovidas == 1
    modelos = db.listar("modelos")
    assert any("siempre pide cafe" in m["texto"] for m in modelos)
    # La observacion queda consolidada: ya no se vuelve a promover.
    assert db.reflect_basico() == 0


def test_reflect_promueve_mil_veces(adapter):
    db = adapter.get_adapter()
    for _ in range(3):
        db.retain("otra observacion repetida", tipo="observaciones")
    db.reflect_basico()
    assert db.reflect_basico() == 0


# -- borrar y exportar --------------------------------------------------------

def test_borrar_quita_la_entrada_y_el_indice(adapter):
    db = adapter.get_adapter()
    rid = db.retain("esto se va a borrar", tipo="hechos")
    assert db.recall("se va a borrar", k=5)
    assert db.borrar("hechos", rid) is True
    assert db.recall("se va a borrar", k=5) == []
    assert all(e["id"] != rid for e in db.listar("hechos"))


def test_borrar_capa_invalida_no_hace_nada(adapter):
    db = adapter.get_adapter()
    assert db.borrar("no_existe", 1) is False


def test_exportar_trae_todo(adapter):
    db = adapter.get_adapter()
    db.retain("uno", tipo="hechos")
    db.retain("dos", tipo="reglas", confianza="usuario")
    exportado = db.exportar()
    assert len(exportado) == 2
    assert {e["capa"] for e in exportado} == {"hechos", "reglas"}


def test_conteo_por_capa(adapter):
    db = adapter.get_adapter()
    db.retain("a", tipo="hechos")
    db.retain("b", tipo="hechos")
    db.retain("c", tipo="modelos")
    conteo = db.conteo()
    assert conteo["hechos"] == 2
    assert conteo["modelos"] == 1
    assert conteo["reglas"] == 0


# -- nucleo VA ----------------------------------------------------------------

def test_retain_many_importa_varias(adapter):
    db = adapter.get_adapter()
    res = db.retain_many([
        {"texto": "uno", "capa": "hechos"},
        {"texto": "dos", "capa": "reglas", "confianza": "usuario"},
    ])
    assert res["importadas"] == 2
    assert res["omitidas"] == 0
    assert len(db.listar()) == 2


def test_retain_many_omite_credenciales(adapter):
    db = adapter.get_adapter()
    res = db.retain_many([
        {"texto": "password: Secreto123", "capa": "hechos"},
        {"texto": "esto si entra", "capa": "hechos"},
    ])
    assert res["importadas"] == 1
    assert res["omitidas"] == 1


def test_retain_many_con_el_flag_apagado_no_hace_nada(adapter):
    adapter.set_enabled(False)
    res = adapter.get_adapter().retain_many([{"texto": "nada"}])
    assert res["importadas"] == 0


def test_retain_many_dedup_observaciones(adapter):
    """Al importar, lo repetido no infla la evidencia: cuenta como duplicado."""
    db = adapter.get_adapter()
    res = db.retain_many([{"texto": "repetido", "capa": "observaciones"}] * 3)
    obs = db.listar("observaciones")
    assert len(obs) == 1
    assert obs[0]["evidencia"] == 1
    assert res["importadas"] == 1
    assert res["duplicadas"] == 2


def test_retain_many_no_duplica_entradas_existentes(adapter):
    db = adapter.get_adapter()
    db.retain("ya estaba", tipo="hechos")
    res = db.retain_many([{"texto": "ya estaba", "capa": "hechos"},
                           {"texto": "nuevo", "capa": "hechos"}])
    assert res["importadas"] == 1
    assert res["duplicadas"] == 1
    assert len(db.listar("hechos")) == 2


def test_recall_devuelve_el_id_de_la_entrada(adapter):
    db = adapter.get_adapter()
    rid = db.retain("para borrar desde la busqueda", tipo="hechos")
    hits = db.recall("busqueda", k=5)
    assert hits[0]["id"] == rid


def test_core_retain_recall(core):
    assert core.memory_retain("memoria viva", tipo="hechos") is not None
    hits = core.memory_recall("memoria viva", k=3)
    assert hits and hits[0]["capa"] == "hechos"


def test_core_fijar_manda_a_reglas(core):
    rid = core.memory_fijar("regla que fija el usuario")
    assert rid is not None
    reglas = core.memory_reglas()
    assert any(r["texto"] == "regla que fija el usuario" for r in reglas)


def test_core_reflect_promueve(core):
    for _ in range(3):
        core.memory_retain("se repite mucho", tipo="observaciones")
    assert core.memory_reflect() == 1


def test_core_borrar_y_exportar(core):
    rid = core.memory_retain("para borrar", tipo="hechos")
    assert core.memory_borrar("hechos", rid) is True
    assert core.memory_borrar("hechos", rid) is False
    core.memory_retain("para exportar", tipo="modelos")
    assert core.memory_exportar()


def test_core_apagado_no_guarda(core, monkeypatch):
    monkeypatch.setenv("ARIA_MEMORY_SQLITE", "false")
    core._memory_override = None
    assert core.memory_retain("nada") is None
    assert core.memory_recall("nada") == []


def test_core_interruptor_en_caliente(core):
    assert core.set_memory_enabled(False) is False
    assert core.memory_retain("nada") is None
    assert core.set_memory_enabled(True) is True
    assert core.memory_retain("ahora si") is not None
    core.set_memory_enabled(None)


def test_core_process_text_usa_la_memoria(core, monkeypatch):
    core.memory_retain("el usuario se llama Ada", tipo="hechos")
    capturado = {}

    def fake_chat(msg):
        capturado["msg"] = msg
        return {"response": "ok", "source": "local"}

    # Sin cargar el modelo local: esto prueba la memoria, no el LLM.
    monkeypatch.setattr(core.LocalAIBrain, "_load_local_model", lambda self: None)
    va = core.get_va()
    monkeypatch.setattr(va.brain, "chat", fake_chat)
    va.process_text("Ada")
    assert "[MEM:" in capturado["msg"]
    assert "el usuario se llama Ada" in capturado["msg"]


# -- EXE empaquetado (PyInstaller) --------------------------------------------

def test_el_adaptador_se_busca_tambien_en_el_exe_congelado(core, tmp_path, monkeypatch):
    """En el EXE, PyInstaller deja los datos en la carpeta temporal."""
    congelado = tmp_path / "MEIPASS"
    (congelado / "memory").mkdir(parents=True)
    shutil.copy(str(ADAPTER_PATH), str(congelado / "memory" / "sqlite_adapter.py"))
    monkeypatch.setattr(sys, "_MEIPASS", str(congelado), raising=False)
    rutas = core._memory_adapter_candidates()
    assert (congelado / "memory" / "sqlite_adapter.py") in rutas


def test_el_adaptador_carga_desde_el_exe_congelado(core, tmp_path, monkeypatch):
    """El modulo se carga por ruta: en el EXE debe funcionar igual."""
    congelado = tmp_path / "MEIPASS"
    (congelado / "memory").mkdir(parents=True)
    shutil.copy(str(ADAPTER_PATH), str(congelado / "memory" / "sqlite_adapter.py"))
    monkeypatch.setattr(sys, "_MEIPASS", str(congelado), raising=False)
    monkeypatch.setattr(core, "_MEMORY_ADAPTER_PATH", tmp_path / "no-existe.py")
    core._memory_adapter_cache.clear()
    modulo = core._memory_module()
    assert modulo is not None
    assert hasattr(modulo, "get_adapter")


def test_la_base_no_vive_en_la_carpeta_temporal_del_exe(tmp_path, monkeypatch):
    """Congelado, la base va a %LOCALAPPDATA% y no a la carpeta temporal."""
    monkeypatch.setenv("ARIA_MEMORY_DB", str(tmp_path / "mem.db"))
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "localappdata"))
    module = _load_adapter(tmp_path / "mem2.db")
    esperado = tmp_path / "localappdata" / "ARIA_OS" / "data" / "memory"
    assert module._data_dir() == esperado
