"""Gate: el nucleo VA de ARIA se puede instanciar y arrancar.

El 2026-10-21 la clase `LocalVoice` habia perdido su linea de cabecera en
`ARIA_APP/aria_va_core.py`. Con el cuerpo de la clase pegado al de
`LocalAIBrain`, el `__init__` de la voz pisaba el del cerebro y
`get_va()` reventaba con `NameError: LocalVoice no esta definido`.

El escritorio no arranca sin ese nucleo, asi que la rotura era total: la
autonomia se quedaba sin manos y sin cabeza, y la app no llegaba a abrir la
ventana. El sintoma era silencioso en los tests (nadie instanciaba el
nucleo) y ruidoso en la app (pantalla en blanco, sin ventana).

Este gate instancia el nucleo de verdad y comprueba que cada clase tiene lo
que dice tener. Si vuelve a pasar algo parecido, falla aqui y no en pantalla.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for _path in (str(ROOT), str(ROOT / "ARIA_APP")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from aria_va_core import (  # noqa: E402
    LocalAIBrain,
    LocalSkills,
    LocalVoice,
    VirtualAssistant,
    get_va,
)


def test_el_nucleo_se_instancia():
    """`get_va()` no puede reventar: el escritorio depende de el."""
    va = get_va()
    assert isinstance(va, VirtualAssistant)


def test_cada_pieza_esta_en_su_lugar():
    va = get_va()

    assert isinstance(va.brain, LocalAIBrain)
    assert isinstance(va.voice, LocalVoice)
    assert isinstance(va.skills, LocalSkills)


def test_el_cerebro_no_esta_pisado_por_la_voz():
    """El cerebro y la voz son clases distintas, con __init__ distintos.

    Es el sintoma exacto de la rotura: la cabecera de `LocalVoice` se habia
    perdido, sus metodos acabaron dentro de `LocalAIBrain` y su `__init__`
    sustituyo al del cerebro.
    """
    assert LocalVoice.__init__ is not LocalAIBrain.__init__

    brain = LocalAIBrain()
    assert brain.history == []
    assert isinstance(brain.system_prompt, str)
    assert brain.system_prompt.strip()
    assert hasattr(brain, "_model_loaded")

    voice = LocalVoice()
    assert voice.wake_words
    assert voice.listening is False


def test_la_voz_tiene_voz():
    voice = LocalVoice()

    caps = voice.capabilities()
    assert caps["local_only"] is True
    assert set(caps) >= {"stt", "tts", "mic", "wake_word"}

    for metodo in ("speak", "speak_async", "start_listening", "stop_listening"):
        assert callable(getattr(voice, metodo))


def test_aria_responde_sin_servidor():
    """El nucleo contesta de verdad, en local, sin nada encendido."""
    va = get_va()

    respuesta = va.process_text("hola ARIA, estas ahi?")

    assert isinstance(respuesta, str)
    assert respuesta.strip()


def test_el_estado_no_revienta():
    va = get_va()

    status = va.get_status()

    assert status["mode"] == "100% local"
    assert status["skills"] >= 0
    assert status["model"] in {"rules", "transformers"}
    assert status["voice_caps"]["local_only"] is True


@pytest.mark.parametrize("nombre", ["LocalAIBrain", "LocalVoice", "LocalSkills"])
def test_las_clases_publicas_son_clases(nombre):
    import aria_va_core

    clase = getattr(aria_va_core, nombre)
    assert isinstance(clase, type)


def test_ninguna_clase_llama_a_un_metodo_que_no_existe():
    """Ninguna clase llama a un metodo suyo que no este definido.

    Es la otra mitad de la rotura del 2026-10-21: al perder una cabecera
    `def`, el cuerpo se pegaba al metodo anterior y las llamadas se
    rompian en silencio (la clase existia, el metodo no). Un `AttributeError`
    en tiempo de ejecucion no lo veia nadie hasta que ARIA lo usaba.
    """
    import ast

    import aria_va_core

    arbol = ast.parse(Path(aria_va_core.__file__).read_text(encoding="utf-8"))

    roturas = []
    for clase in [n for n in ast.walk(arbol) if isinstance(n, ast.ClassDef)]:
        definidos = {
            n.name
            for n in clase.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        # Atributos de instancia (self._tokenizer, self._on_wake...): son
        # objetos asignados, no metodos de la clase, y llamarlos es correcto.
        atributos = {
            n.attr
            for n in ast.walk(clase)
            if isinstance(n, ast.Attribute)
            and isinstance(n.ctx, ast.Store)
            and isinstance(n.value, ast.Name)
            and n.value.id == "self"
        }
        for nodo in ast.walk(clase):
            if not isinstance(nodo, ast.Call):
                continue
            func = nodo.func
            if not isinstance(func, ast.Attribute):
                continue
            if not isinstance(func.value, ast.Name) or func.value.id != "self":
                continue
            if func.attr.startswith("__") or func.attr in definidos or func.attr in atributos:
                continue
            roturas.append(f"{clase.name}.{func.attr} (linea {nodo.lineno})")

    assert not roturas, (
        "metodos que se llaman y no existen (cabecera `def` perdida): " + ", ".join(roturas)
    )


@pytest.mark.parametrize("skill_id", ["system_status", "memory_status", "note_list", "conversation_history"])
def test_toda_skill_de_lectura_responde(skill_id):
    """Las skills que ARIA ofrece de verdad existen y contestan.

    `LocalSkills.list()` anunciaba `note_list` y `conversation_history` pero
    sus metodos no estaban: el dispatcher reventaba con AttributeError en
    cuanto la autonomia intentaba usarlas.
    """
    skills = LocalSkills(LocalAIBrain())

    assert any(item["id"] == skill_id for item in skills.list())

    resultado = skills.run(skill_id, {})
    assert resultado.get("status") == "ok", resultado


def test_toda_skill_anunciada_tiene_metodo():
    """Lo que `list()` anuncia tiene que existir, sin excepciones."""
    import inspect

    skills = LocalSkills(LocalAIBrain())
    fuente = inspect.getsource(type(skills).run)

    for item in skills.list():
        skill_id = item["id"]
        assert f'"{skill_id}"' in fuente, (
            f"la skill {skill_id} se anuncia pero el dispatcher no la conoce"
        )
