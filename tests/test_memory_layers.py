"""Test de las tres capas de memoria de ARIA OS.

Mnemosyne (operativa), Hindsight (reflexion) y Obsidian Wiki (mundo) son
complementarias: cada una responde a una pregunta distinta y ninguna suple a
otra. El test verifica el ciclo completo de cada capa de forma autonoma, sin
LLM ni red.

Los modulos se cargan por ruta: `backend` existe tambien en la raiz del repo y
en ARIA_APP, y meter ARIA_APP en sys.path romperia el resto de la suite.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ARIA_APP = ROOT / "ARIA_APP"
MEM_DIR = ARIA_APP / "backend" / "memory"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


mnemosyne_mod = _load("aria_mem_mnemosyne", MEM_DIR / "mnemosyne.py")
hindsight_mod = _load("aria_mem_hindsight", MEM_DIR / "hindsight.py")
wiki_mod = _load("aria_mem_wiki", MEM_DIR / "obsidian_wiki.py")


# ─── Mnemosyne ──────────────────────────────────────────────────────────────


def test_mnemosyne_guarda_y_busca(tmp_path):
    mem = mnemosyne_mod.MnemosyneMemory(data_dir=str(tmp_path / "mnemosyne"))
    mem.set_session("sesion-1")
    mem.add(role="user", content="quiero un panel de control en tiempo real",
            importance=0.8, tags=["ui"])
    mem.add(role="assistant", content="hecho, usei electron con three.js",
            importance=0.6)

    assert mem.stats()["entries"] == 2
    assert mem.stats()["session_id"] == "sesion-1"

    hits = mem.search("tiempo real")
    assert hits, "no encontro la entrada por palabras clave"
    assert hits[0]["source"] == "mnemosyne"
    assert "tiempo real" in hits[0]["content"]

    assert len(mem.get_by_importance(0.7)) == 1
    assert len(mem.get_recent(1)) == 1


def test_mnemosyne_persiste_entre_instancias(tmp_path):
    data_dir = str(tmp_path / "mnemosyne")
    mem = mnemosyne_mod.MnemosyneMemory(data_dir=data_dir)
    mem.add(role="user", content="esto debe sobrevivir al reinicio")
    mem.set_session("sesion-2")

    otra = mnemosyne_mod.MnemosyneMemory(data_dir=data_dir)
    assert otra.stats()["entries"] == 1
    assert otra.stats()["session_id"] == "sesion-2"

    payload = json.loads((Path(data_dir) / "mnemosyne.json").read_text(encoding="utf-8"))
    assert payload["entries"][0]["content"] == "esto debe sobrevivir al reinicio"


def test_mnemosyne_evicta_respetando_el_limite(tmp_path):
    mem = mnemosyne_mod.MnemosyneMemory(data_dir=str(tmp_path / "mnemosyne"), max_entries=3)
    for i in range(6):
        mem.add(role="user", content=f"mensaje {i}")
    assert mem.stats()["entries"] == 3
    contents = [e.content for e in mem.get_recent()]
    assert "mensaje 5" in contents
    assert "mensaje 0" not in contents


# ─── Hindsight ──────────────────────────────────────────────────────────────


def test_hindsight_sin_llm_igual_guarda_la_reflexion(tmp_path):
    mem = hindsight_mod.HindsightMemory(data_dir=str(tmp_path / "hindsight"))
    reflexion = mem.reflect_on_session("sesion-1", "el usuario quiere Spanish y pocas palabras")
    assert reflexion.reflection_id
    assert reflexion.session_id == "sesion-1"
    assert reflexion.summary
    assert mem.stats()["total_reflections"] == 1


def test_hindsight_con_llm_extrae_preferencias(tmp_path):
    mem = hindsight_mod.HindsightMemory(data_dir=str(tmp_path / "hindsight"))
    respuesta = json.dumps({
        "summary": "Se trabajo en el panel de control",
        "preferences": ["responder en espanol", "preferir codigo conciso"],
        "patterns": ["trabaja de noche", "usa electron"],
    })

    mem.set_llm_provider(lambda prompt: respuesta)
    reflexion = mem.reflect_on_session("sesion-1", "conversacion de prueba")
    assert len(reflexion.preferences_learned) == 2
    assert len(reflexion.patterns_identified) == 2
    assert reflexion.insights_found

    insights = mem.get_insights()
    assert len(insights) == 4
    titulos = {i.title for i in insights}
    assert "responder en espanol" in titulos
    assert "trabaja de noche" in titulos


def test_hindsight_refuerza_en_lugar_of_duplicar(tmp_path):
    mem = hindsight_mod.HindsightMemory(data_dir=str(tmp_path / "hindsight"))
    respuesta = json.dumps({
        "summary": "s", "preferences": ["responder en espanol"], "patterns": [],
    })
    mem.set_llm_provider(lambda prompt: respuesta)
    mem.reflect_on_session("sesion-1", "a")
    mem.reflect_on_session("sesion-2", "b")

    insights = mem.get_insights()
    assert len(insights) == 1, "no debe duplicar el mismo insight"
    assert insights[0].evidence_count == 2
    assert insights[0].confidence > 0.7


def test_hindsight_contexto_para_consulta(tmp_path):
    mem = hindsight_mod.HindsightMemory(data_dir=str(tmp_path / "hindsight"))
    respuesta = json.dumps({
        "summary": "s",
        "preferences": ["preferir siempre el panel de control en tiempo real"],
        "patterns": [],
    })
    mem.set_llm_provider(lambda prompt: respuesta)
    mem.reflect_on_session("sesion-1", "x")
    contexto = mem.get_context_for_query("panel de control en tiempo real")
    assert contexto
    assert contexto[0]["source"] == "hindsight"


# ─── Obsidian Wiki ──────────────────────────────────────────────────────────


def test_wiki_escribe_y_relee_en_markdown(tmp_path):
    wiki = wiki_mod.ObsidianWiki(data_dir=str(tmp_path / "wiki"))
    note_id = wiki.add_note(
        title="Arquitectura ARIA",
        content="Tres capas: [[Mnemosyne]], [[Hindsight]] y el wiki.",
        tags=["arquitectura", "memoria"],
    )
    assert note_id == "Arquitectura_ARIA"

    path = Path(wiki._note_path(note_id))
    assert path.exists()
    texto = path.read_text(encoding="utf-8")
    assert texto.startswith("# Arquitectura ARIA")
    assert "tags: arquitectura, memoria" in texto

    nota = wiki.get_note_by_title("Arquitectura ARIA")
    assert nota is not None
    assert nota.tags == ["arquitectura", "memoria"]


def test_wiki_busqueda_por_contenido_y_tag(tmp_path):
    wiki = wiki_mod.ObsidianWiki(data_dir=str(tmp_path / "wiki"))
    wiki.add_note(title="Nota Uno", content="habla de electron y threejs", tags=["ui"])
    wiki.add_note(title="Nota Dos", content="habla de backend en rust", tags=["backend"])

    hits = wiki.search("electron")
    assert len(hits) == 1
    assert hits[0]["title"] == "Nota Uno"
    assert hits[0]["source"] == "obsidian_wiki"

    assert len(wiki.get_by_tag("backend")) == 1
    assert wiki.stats()["total_notes"] == 2


def test_wiki_resuelve_enlaces_de_tipo_wiki(tmp_path):
    wiki = wiki_mod.ObsidianWiki(data_dir=str(tmp_path / "wiki"))
    enlaces = wiki.resolve_links("ver [[Mnemosyne]] y [[Hindsight]]")
    assert enlaces == ["Mnemosyne", "Hindsight"]


def test_wiki_persiste_entre_instancias(tmp_path):
    data_dir = str(tmp_path / "wiki")
    wiki = wiki_mod.ObsidianWiki(data_dir=data_dir)
    wiki.add_note(title="Persistente", content="contenido", tags=["x"])

    otra = wiki_mod.ObsidianWiki(data_dir=data_dir)
    assert otra.stats()["total_notes"] == 1
    assert otra.get_note_by_title("Persistente").content == "contenido"


# ─── El paquete exporta las tres capas ──────────────────────────────────────


def test_el_paquete_de_memoria_exporta_las_tres_capas():
    """El paquete `backend.memory` debe exponer las tres capas.

    Se comprueba en un subproceso: en la suite, `backend` ya puede estar
    importado desde la raiz del repo, donde no existe `backend.memory`.
    """
    codigo = (
        "import sys; sys.path.insert(0, r'%s'); "
        "from backend.memory import MnemosyneMemory, HindsightMemory, ObsidianWiki; "
        "print('OK')" % ARIA_APP
    )
    resultado = subprocess.run(
        [sys.executable, "-c", codigo],
        capture_output=True, text=True, timeout=120, cwd=str(ROOT),
    )
    assert resultado.returncode == 0, resultado.stderr
    assert "OK" in resultado.stdout
