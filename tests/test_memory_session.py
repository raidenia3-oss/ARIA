# -*- coding: utf-8 -*-
"""Tests de los recuerdos de sesion, el alta manual y la importacion de memoria.

Los recuerdos de sesion son volatiles (RAM): funcionan con la memoria
persistente apagada y desaparecen al cerrar ARIA. La importacion lee un
archivo local (JSON o JSONL): sin red, sin puertos, sin dependencias nuevas.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ARIA_APP = Path(__file__).resolve().parent.parent / "ARIA_APP"
if str(ARIA_APP) not in sys.path:
    sys.path.insert(0, str(ARIA_APP))


@pytest.fixture()
def core(tmp_path, monkeypatch):
    """Nucleo VA con la memoria persistente en una base temporal."""
    monkeypatch.setenv("ARIA_MEMORY_SQLITE", "true")
    monkeypatch.setenv("ARIA_MEMORY_DB", str(tmp_path / "sesion.db"))
    import aria_va_core

    aria_va_core._memory_adapter_cache.clear()
    aria_va_core.memory_session_clear()
    yield aria_va_core
    aria_va_core.memory_session_clear()
    aria_va_core._memory_adapter_cache.clear()


@pytest.fixture()
def core_sin_memoria(tmp_path, monkeypatch):
    """Nucleo VA con la memoria persistente APAGADA (flag off)."""
    monkeypatch.setenv("ARIA_MEMORY_SQLITE", "false")
    monkeypatch.setenv("ARIA_MEMORY_DB", str(tmp_path / "nada.db"))
    import aria_va_core

    aria_va_core._memory_adapter_cache.clear()
    aria_va_core._memory_override = None
    aria_va_core.memory_session_clear()
    yield aria_va_core
    aria_va_core.memory_session_clear()
    aria_va_core._memory_adapter_cache.clear()


# -- recuerdos de sesion ------------------------------------------------------

def test_recuerdo_de_sesion_se_guarda(core):
    rid = core.memory_session_add("el usuario quiere respuestas cortas")
    assert rid is not None
    lista = core.memory_session_list()
    assert len(lista) == 1
    assert lista[0]["texto"] == "el usuario quiere respuestas cortas"
    assert lista[0]["capa"] == "sesion"


def test_recuerdo_de_sesion_no_guarda_vacio(core):
    assert core.memory_session_add("   ") is None
    assert core.memory_session_add("") is None
    assert core.memory_session_list() == []


def test_recuerdo_de_sesion_se_borra(core):
    core.memory_session_add("uno")
    core.memory_session_add("dos")
    assert core.memory_session_clear() == 2
    assert core.memory_session_list() == []


def test_recuerdo_de_sesion_se_borra_uno(core):
    rid = core.memory_session_add("para borrar")
    assert core.memory_borrar("sesion", rid) is True
    assert core.memory_session_list() == []
    assert core.memory_borrar("sesion", rid) is False


def test_sesion_tiene_tope(core):
    for i in range(core.SESSION_MEMORY_MAX + 20):
        core.memory_session_add(f"recuerdo numero {i}")
    lista = core.memory_session_list()
    assert len(lista) == core.SESSION_MEMORY_MAX
    # Lo viejo se va: el ultimo sigue ahi.
    assert "recuerdo numero" in lista[0]["texto"]


def test_sesion_funciona_con_la_memoria_apagada(core_sin_memoria, tmp_path):
    rid = core_sin_memoria.memory_session_add("recuerdo con la memoria apagada")
    assert rid is not None
    assert len(core_sin_memoria.memory_session_list()) == 1
    # Con la memoria apagada no se crea ni el archivo de base.
    assert not (tmp_path / "nada.db").exists()


def test_recall_incluye_los_recuerdos_de_sesion(core):
    core.memory_session_add("el usuario se llama Ada")
    hits = core.memory_recall("Ada", k=3)
    assert hits
    assert any("Ada" in str(h.get("texto", "")) for h in hits)


def test_recall_con_memoria_apagada_devuelve_la_sesion(core_sin_memoria):
    core_sin_memoria.memory_session_add("el usuario se llama Ada")
    hits = core_sin_memoria.memory_recall("Ada", k=3)
    assert len(hits) == 1
    assert hits[0]["capa"] == "sesion"


def test_recall_sin_memoria_ni_sesion_devuelve_vacio(core_sin_memoria):
    assert core_sin_memoria.memory_recall("nada de nada", k=3) == []


def test_la_sesion_va_primero_en_el_recall(core):
    core.memory_session_add("el usuario se llama Ada")
    core.memory_retain("el usuario se llama Ada Lovelace", tipo="hechos")
    hits = core.memory_recall("Ada", k=3)
    assert hits
    assert hits[0]["capa"] == "sesion"


# -- alta manual ---------------------------------------------------------------

def test_alta_manual_va_a_la_capa_elegida(core):
    rid = core.memory_agregar("el servidor es el de produccion", capa="hechos",
                               fuente="usuario", confianza="usuario")
    assert rid is not None
    hechos = core.memory_listar("hechos")
    assert any(h["texto"] == "el servidor es el de produccion" for h in hechos)
    assert hechos[0]["confianza"] == "usuario"


def test_alta_manual_rechaza_credenciales(core):
    assert core.memory_agregar("password: SuperSecreto123", capa="hechos") is None


def test_alta_manual_con_la_memoria_apagada_no_guarda(core_sin_memoria):
    assert core_sin_memoria.memory_agregar("nada", capa="hechos") is None


def test_alta_manual_va_a_reglas(core):
    rid = core.memory_agregar("responde siempre en espanol", capa="reglas")
    assert rid is not None
    reglas = core.memory_reglas()
    assert any(r["texto"] == "responde siempre en espanol" for r in reglas)


# -- importacion ---------------------------------------------------------------

def test_importar_json(core, tmp_path):
    archivo = tmp_path / "memoria.json"
    archivo.write_text(json.dumps([
        {"capa": "hechos", "texto": "importado uno", "confianza": "usuario"},
        {"texto": "importado dos"},
    ], ensure_ascii=False), encoding="utf-8")
    res = core.memory_importar_archivo(str(archivo))
    assert res["error"] is None
    assert res["importadas"] == 2
    assert res["omitidas"] == 0
    textos = {h["texto"] for h in core.memory_listar()}
    assert {"importado uno", "importado dos"} <= textos


def test_importar_json_con_clave_entries(core, tmp_path):
    archivo = tmp_path / "memoria.json"
    archivo.write_text(json.dumps({"entries": [{"texto": "dentro de entries"}]}),
                       encoding="utf-8")
    res = core.memory_importar_archivo(str(archivo))
    assert res["importadas"] == 1


def test_importar_jsonl(core, tmp_path):
    archivo = tmp_path / "conversaciones.jsonl"
    lineas = [
        {"ts": 1, "user": "que hora es", "aria": "las 20:17"},
        {"ts": 2, "user": "hola", "aria": "hola"},
    ]
    archivo.write_text("\n".join(json.dumps(l, ensure_ascii=False) for l in lineas),
                       encoding="utf-8")
    res = core.memory_importar_archivo(str(archivo))
    assert res["importadas"] == 2
    experiencias = core.memory_listar("experiencias")
    assert any("que hora es" in e["texto"] for e in experiencias)


def test_importar_omite_credenciales(core, tmp_path):
    archivo = tmp_path / "memoria.json"
    archivo.write_text(json.dumps([
        {"texto": "api_key=AKIAIOSFODNN7EXAMPLE"},
        {"texto": "esto si entra"},
    ]), encoding="utf-8")
    res = core.memory_importar_archivo(str(archivo))
    assert res["importadas"] == 1
    assert res["omitidas"] == 1


def test_reimportar_el_mismo_archivo_no_duplica(core, tmp_path):
    archivo = tmp_path / "memoria.json"
    archivo.write_text(json.dumps([{"texto": "importado una vez", "capa": "hechos"}]),
                       encoding="utf-8")
    primera = core.memory_importar_archivo(str(archivo))
    segunda = core.memory_importar_archivo(str(archivo))
    assert primera["importadas"] == 1
    assert segunda["importadas"] == 0
    assert segunda["duplicadas"] == 1
    assert len(core.memory_listar("hechos")) == 1


def test_importar_archivo_inexistente(core):
    res = core.memory_importar_archivo("no/existe.json")
    assert res["importadas"] == 0
    assert res["error"]


def test_importar_archivo_vacio(core, tmp_path):
    archivo = tmp_path / "vacio.json"
    archivo.write_text("[]", encoding="utf-8")
    res = core.memory_importar_archivo(str(archivo))
    assert res["importadas"] == 0
    assert res["error"]


def test_importar_con_la_memoria_apagada_no_rompe(core_sin_memoria, tmp_path):
    archivo = tmp_path / "memoria.json"
    archivo.write_text(json.dumps([{"texto": "no entra"}]), encoding="utf-8")
    res = core_sin_memoria.memory_importar_archivo(str(archivo))
    assert res["importadas"] == 0


def test_importar_conversaciones_propias(core, tmp_path, monkeypatch):
    """El historial de ARIA (conversations.jsonl) se puede importar."""
    archivo = tmp_path / "conversations.jsonl"
    archivo.write_text(json.dumps({"ts": 1, "user": "hola", "aria": "hola"}) + "\n",
                       encoding="utf-8")
    monkeypatch.setattr(core, "CONVERSATIONS_FILE", archivo)
    res = core.memory_importar_conversaciones()
    assert res["importadas"] == 1


# -- intencion "recuerda..." en el chat ---------------------------------------

def test_recordar_en_el_chat_guarda_en_la_sesion(core, monkeypatch):
    monkeypatch.setattr(core.LocalAIBrain, "_load_local_model", lambda self: None)
    va = core.get_va()
    respuesta = va.process_text("recuerda que el deploy es los martes")
    assert "Guardado" in respuesta
    assert any("deploy" in s["texto"] for s in core.memory_session_list())


def test_recordar_en_el_chat_no_llama_al_modelo(core, monkeypatch):
    monkeypatch.setattr(core.LocalAIBrain, "_load_local_model", lambda self: None)
    va = core.get_va()

    def chat_que_falla(msg):
        raise AssertionError("no deberia llamar al modelo")

    monkeypatch.setattr(va.brain, "chat", chat_que_falla)
    respuesta = va.process_text("apunta que la clave del servidor es X")
    assert "Guardado" in respuesta


def test_recordar_sin_contenido_pide_clarificacion(core, monkeypatch):
    monkeypatch.setattr(core.LocalAIBrain, "_load_local_model", lambda self: None)
    va = core.get_va()
    respuesta = va.process_text("recuerda")
    assert "?" in respuesta


def test_el_recuerdo_de_sesion_llega_al_contexto(core, monkeypatch):
    """Lo recordado en la sesion se inyecta en el mensaje del cerebro."""
    monkeypatch.setattr(core.LocalAIBrain, "_load_local_model", lambda self: None)
    va = core.get_va()
    capturado = {}

    def fake_chat(msg):
        capturado["msg"] = msg
        return {"response": "ok", "source": "local"}

    monkeypatch.setattr(va.brain, "chat", fake_chat)
    va.process_text("recuerda que el deploy es los martes")
    va.process_text("¿y el deploy?")
    assert "[MEM:" in capturado["msg"]
    assert "deploy" in capturado["msg"]


# -- las reglas fijadas llegan al cerebro --------------------------------------

def test_las_reglas_llegan_al_prompt(core, monkeypatch):
    monkeypatch.setattr(core.LocalAIBrain, "_load_local_model", lambda self: None)
    core.memory_fijar("responde siempre en espanol y sin emojis")
    cerebro = core.LocalAIBrain()
    cerebro._model_loaded = True
    monkeypatch.setattr(cerebro, "_record", lambda *a, **k: None)
    capturado = {}

    def fake_generate(prompt, max_tokens=200):
        capturado["prompt"] = prompt
        return "respuesta"

    monkeypatch.setattr(cerebro, "generate_local", fake_generate)
    cerebro.chat("explicame el clima de manana")
    assert "responde siempre en espanol y sin emojis" in capturado["prompt"]


def test_sin_memoria_el_prompt_no_cambia(core_sin_memoria, monkeypatch):
    monkeypatch.setattr(core_sin_memoria.LocalAIBrain, "_load_local_model", lambda self: None)
    cerebro = core_sin_memoria.LocalAIBrain()
    cerebro._model_loaded = True
    monkeypatch.setattr(cerebro, "_record", lambda *a, **k: None)
    capturado = {}

    def fake_generate(prompt, max_tokens=200):
        capturado["prompt"] = prompt
        return "respuesta"

    monkeypatch.setattr(cerebro, "generate_local", fake_generate)
    cerebro.chat("explicame el clima de manana")
    assert "Reglas del usuario" not in capturado["prompt"]


def test_el_estado_menciona_las_reglas(core, monkeypatch):
    monkeypatch.setattr(core.LocalAIBrain, "_load_local_model", lambda self: None)
    core.memory_fijar("una regla del usuario")
    cerebro = core.LocalAIBrain()
    estado = cerebro._status_reply()
    assert "Reglas del usuario: 1" in estado
