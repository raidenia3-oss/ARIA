"""El runtime autónomo de ARIA vive en su proceso, no en un servicio.

Estos tests comprueban lo que de verdad importa: que ARIA perceives, decide,
actúa y aprende sin necesitar que nada más esté encendido.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for _path in (str(ROOT), str(ROOT / "ARIA_APP")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from ARIA_APP.autonomy.runtime import Runtime  # noqa: E402


class FakeSkills:
    """Skills de mentira: no tocan el disco, pero responden de verdad."""

    def __init__(self) -> None:
        self.calls: list = []

    def list(self):
        return [{"id": "note_add", "name": "Agregar nota"}]

    def run(self, skill_id, params):
        self.calls.append((skill_id, params))
        if skill_id == "note_add":
            return {"status": "ok", "note": {"ts": 1.0, "text": params.get("text", "")}}
        if skill_id == "file_read":
            return {"status": "error", "error": "archivo no encontrado"}
        return {"status": "ok", "result": "hecho"}


@pytest.fixture()
def runtime(tmp_path):
    return Runtime(data_dir=tmp_path / "autonomy", skills=FakeSkills())


def test_perception_has_real_local_worlds(runtime):
    runtime.ingest("chat", "hola ARIA", "escritorio", {"answered": True})
    snapshot = runtime.perception()

    assert snapshot["status"] == "ok"
    worlds = snapshot["perception"]["worlds"]
    ids = [world["id"] for world in worlds]
    assert "escritorio" in ids
    assert "memoria" in ids
    assert "consola" in ids
    assert all(world["connected"] for world in worlds)
    assert runtime.status()["server"] == "in-process"


def test_a_quiet_console_is_not_pretending_to_be_connected(runtime):
    snapshot = runtime.perception()

    consola = [w for w in snapshot["perception"]["worlds"] if w["id"] == "consola"][0]
    assert consola["connected"] is False
    assert consola["status"] == "en silencio"


def test_ingest_keeps_the_goal_the_user_asked_for(runtime):
    runtime.ingest("chat", "apunta revisar los logs del servidor", "escritorio", {"answered": True})

    agenda = runtime.agenda()
    assert agenda["count"] == 1
    assert agenda["agenda"][0]["goal"] == "revisar los logs del servidor"
    assert agenda["agenda"][0]["state"] == "pendiente"


def test_tick_runs_the_goal_and_marks_it_done(runtime):
    runtime.ingest("chat", "apunta listar los archivos", "escritorio", {"answered": True})

    result = runtime.tick()

    assert result["status"] == "ok"
    assert result["ok"] is True
    assert result["initiative"]["state"] == "ejecutada"
    assert runtime.agenda()["agenda"][0]["state"] == "ejecutada"


def test_a_failure_becomes_a_lesson(runtime):
    runtime.ingest("chat", "apunta leer un archivo que no existe", "escritorio", {"answered": True})

    result = runtime.tick()

    assert result["ok"] is False
    lessons = runtime.lessons()["lessons"]
    assert lessons, "un fallo debe dejar lección"
    assert lessons[0]["text"]
    assert lessons[0]["source"] == "episodio"


def test_a_lesson_can_be_silenced(runtime):
    runtime.ingest("chat", "apunta leer un archivo que no existe", "escritorio", {"answered": True})
    runtime.tick()

    lesson = runtime.lessons()["lessons"][0]
    muted = runtime.mute_lesson(lesson["id"])

    assert muted["status"] == "ok"
    assert muted["lesson"]["suppressed"] is True
    assert all(item["suppressed"] for item in runtime.lessons()["lessons"])


def test_outside_needs_permission(runtime):
    runtime.ingest("chat", "apunta buscar en internet qué es ARIA", "escritorio", {"answered": True})

    blocked = runtime.tick()
    assert blocked["ok"] is False
    assert runtime.agenda()["agenda"][0]["state"] == "esperando"

    runtime.permissions(True)
    assert runtime.agenda()["agenda"][0]["state"] == "pendiente"

    allowed = runtime.tick()
    assert allowed["status"] == "ok"


def test_a_blocked_goal_is_not_a_failure(runtime):
    runtime.ingest("chat", "apunta buscar en internet qué es ARIA", "escritorio", {"answered": True})

    runtime.tick()

    assert runtime.status()["stats"]["errors"] == 0
    assert runtime.lessons()["count"] == 0


def test_permission_can_be_withdrawn(runtime):
    runtime.permissions(True)
    assert runtime.permissions()["allow_external"] is True

    runtime.permissions(False)
    assert runtime.permissions()["allow_external"] is False


def test_dropping_a_goal_removes_it(runtime):
    runtime.ingest("chat", "apunta revisar los logs", "escritorio", {"answered": True})
    initiative_id = runtime.agenda()["agenda"][0]["id"]

    dropped = runtime.agenda_drop(initiative_id)

    assert dropped["removed"] is True
    assert runtime.agenda()["count"] == 0


def test_user_can_say_what_to_forget(runtime):
    runtime.ingest("chat", "apunta revisar los logs", "escritorio", {"answered": True})

    runtime.ingest("chat", "suelta revisar los logs", "escritorio", {"answered": True})

    assert runtime.agenda()["count"] == 0


def test_events_are_kept_in_order(runtime):
    runtime.ingest("chat", "hola", "escritorio", {"answered": True})
    runtime.ingest("chat", "apunta algo", "escritorio", {"answered": True})

    events = runtime.events()["events"]

    assert len(events) == 2
    assert events[0]["text"] == "hola"
    assert events[1]["payload"].get("initiative")


def test_events_since_filters_the_old_ones(runtime):
    runtime.ingest("chat", "primero", "escritorio", {"answered": True})
    mark = runtime.events()["events"][-1]["at"]
    runtime.ingest("chat", "segundo", "escritorio", {"answered": True})

    recent = runtime.events(since=mark)["events"]

    assert [item["text"] for item in recent] == ["segundo"]


def test_paused_runtime_does_nothing(runtime):
    runtime.toggle(False)
    runtime.ingest("chat", "apunta listar los archivos", "escritorio", {"answered": True})

    result = runtime.tick()

    assert result["status"] == "paused"
    assert runtime.agenda()["agenda"][0]["state"] == "pendiente"


def test_runtime_survives_a_restart(tmp_path):
    data_dir = tmp_path / "autonomy"
    first = Runtime(data_dir=data_dir, skills=FakeSkills())
    first.ingest("chat", "apunta revisar los logs", "escritorio", {"answered": True})

    second = Runtime(data_dir=data_dir, skills=FakeSkills())

    assert second.agenda()["count"] == 1
    assert second.agenda()["agenda"][0]["goal"] == "revisar los logs"


def test_speak_says_something_truthful(runtime):
    said = runtime.speak("¿qué tal?")

    assert said["status"] == "ok"
    assert said["said"]
    assert runtime.status()["stats"]["utterances"] == 1


def test_act_runs_a_skill_on_demand(runtime):
    result = runtime.act(skill_id="note_add", input={"text": "una nota"})

    assert result["status"] == "ok"
    assert result["episode"]["ok"] is True
    assert runtime.skills.calls[-1][0] == "note_add"


# ── ARIA no depende de que haya un generador ───────────────────────────────


def test_aria_actua_sin_generador(tmp_path):
    """Sin cerebro, con reglas: ARIA sigue Fulminando lo que puede."""
    runtime = Runtime(data_dir=tmp_path / "autonomy", skills=FakeSkills(), brain=None)
    runtime.ingest("chat", "apunta listar los archivos", "escritorio", {"answered": True})

    result = runtime.tick()

    assert result["status"] == "ok"
    assert result["ok"] is True
    assert runtime.agenda()["agenda"][0]["state"] == "ejecutada"


def test_aria_habla_sin_generador(tmp_path):
    runtime = Runtime(data_dir=tmp_path / "autonomy", skills=FakeSkills(), brain=None)

    said = runtime.speak("¿qué tal?")

    assert said["status"] == "ok"
    assert said["said"]


def test_un_cerebro_roto_no_tumba_aria(tmp_path):
    """Un generador que falla es un problema suyo, no de ARIA."""

    class BrokenBrain:
        def chat(self, prompt):
            raise RuntimeError("el modelo se ha caido")

    runtime = Runtime(data_dir=tmp_path / "autonomy", skills=FakeSkills(), brain=BrokenBrain())

    said = runtime.speak("hola")

    assert said["status"] == "ok"
    assert said["said"]


def test_el_runtime_no_necesita_skills_para_percibir(tmp_path):
    """Percibir y decidir no dependen de tener manos (skills)."""
    runtime = Runtime(data_dir=tmp_path / "autonomy", skills=None, brain=None)

    snapshot = runtime.perception()

    assert snapshot["status"] == "ok"
    assert snapshot["perception"]["worlds"]


# ── El matcher de skills: preciso, sin adivinar (P6) ────────────────────────


@pytest.mark.parametrize(
    "objetivo,skill",
    [
        ("listar los archivos", "file_list"),
        ("leer un archivo que no existe", "file_read"),
        ("lista mis notas", "note_list"),
        ("anota la cita de mañana", "note_add"),
        ("estado del sistema", "system_status"),
        ("memoria", "memory_status"),
        ("historial de conversaciones", "conversation_history"),
    ],
)
def test_el_matcher_elige_la_skill_correcta(tmp_path, objetivo, skill):
    from ARIA_APP.autonomy.runtime import _match_skill

    elegido, _params = _match_skill(objetivo)
    assert elegido == skill


def test_el_matcher_no_confunde_palabras_semejantes(tmp_path):
    """"nota" no es "notas" y "anota" no es "anotar"."""
    from ARIA_APP.autonomy.runtime import _match_skill

    assert _match_skill("anotar una idea")[0] == "note_add"
    assert _match_skill("las notas")[0] == "note_list"
    # "servidor" no contiene "nota": no hay skill, y ARIA no inventa una.
    elegido, _params = _match_skill("revisar los logs del servidor")
    assert elegido == ""


def test_encargarse_de_algo_es_apuntarlo(tmp_path):
    """"ponte a X" quiere decir: toma nota de X."""
    from ARIA_APP.autonomy.runtime import _match_skill

    elegido, params = _match_skill("ponte a revisar los logs")
    assert elegido == "note_add"
    assert "revisar los logs" in params["text"]


# ── ARIA se propone objetivos sola (P2) ─────────────────────────────────────


def test_aria_se_propone_un_objetivo_cuando_una_pulsion_aprieta(tmp_path):
    """Con la pulsión por encima del umbral, ARIA propone algo por su cuenta."""
    runtime = Runtime(data_dir=tmp_path / "autonomy", skills=FakeSkills())
    runtime._state["drives"] = {"curiosity": 0.95, "care": 0.2, "mastery": 0.1}

    result = runtime.tick()

    assert result["status"] == "ok"
    assert result["initiative"]["origin"] == "propia"
    assert result["initiative"]["goal"] == "lista mis notas"
    assert runtime.agenda()["count"] == 1


def test_aria_no_se_propone_nada_si_no_aprieta(tmp_path):
    runtime = Runtime(data_dir=tmp_path / "autonomy", skills=FakeSkills())

    result = runtime.tick()

    assert result["status"] == "idle"
    assert runtime.agenda()["count"] == 0


def test_aria_no_repite_la_misma_propuesta_enseguida(tmp_path):
    """La propuesta propia tiene memoria: no se machaca cada latido."""
    runtime = Runtime(data_dir=tmp_path / "autonomy", skills=FakeSkills())
    runtime._state["drives"] = {"curiosity": 0.95, "care": 0.2, "mastery": 0.1}

    runtime.tick()
    runtime._state["drives"] = {"curiosity": 0.95, "care": 0.2, "mastery": 0.1}
    runtime.tick()

    pendientes = [i for i in runtime.agenda()["agenda"] if i["state"] == "pendiente"]
    assert len(pendientes) <= 1


def test_la_propuesta_propia_es_local(tmp_path):
    """Lo que ARIA se propone no necesita permiso de internet."""
    runtime = Runtime(data_dir=tmp_path / "autonomy", skills=FakeSkills())
    runtime._state["drives"] = {"curiosity": 0.95, "care": 0.2, "mastery": 0.1}

    runtime.tick()

    iniciativa = runtime.agenda()["agenda"][0]
    assert "buscar" not in iniciativa["goal"]
    assert runtime.status()["allow_external"] is False


# ── Las pulsiones se mueven solas (P2) ──────────────────────────────────────


def test_las_pulsiones_suben_solas_cuando_nadie_habla(tmp_path):
    """Sin nadie que la llame, a ARIA le dan ganas de mirar sus cosas.

    Las pulsiones tienen que ajustarse en cada vuelta: si solo cambiaran
    al actuar, ARIA no tendria nada entre manos que ajustar y jamas llegaria
    al umbral por su cuenta.
    """
    runtime = Runtime(data_dir=tmp_path / "autonomy", skills=FakeSkills())

    antes = dict(runtime.status()["drives"])
    for _ in range(12):
        runtime.tick()
    despues = runtime.status()["drives"]

    assert despues["curiosity"] > antes["curiosity"]


def test_aria_se_propone_sola_sin_que_nadie_le_pida_nada(tmp_path):
    """El ciclo completo: nadie se lo pide y aun asi ARIA se mueve."""
    runtime = Runtime(data_dir=tmp_path / "autonomy", skills=FakeSkills())

    resultados = [runtime.tick() for _ in range(12)]
    acciones = [item for item in resultados if item["status"] == "ok"]

    assert acciones
    assert acciones[0]["initiative"]["origin"] == "propia"
    assert runtime.status()["stats"]["actions"] >= 1


def test_aria_no_inventa_tareas_que_nadie_le_ha_pedido(tmp_path):
    """Una mención no es una orden: "notas" dentro de una frase no es una tarea."""
    from ARIA_APP.autonomy.runtime import _match_skill

    assert _match_skill("las notas")[0] == "note_list"
    assert _match_skill("no tengo notas de esto")[0] == ""
    assert _match_skill("quiero saber el estado de todo el sistema")[0] == ""


def test_aria_prueba_otra_idea_si_la_de_siempre_no_sirve(tmp_path):
    """Con la idea de siempre en marcha, ARIA propone la siguiente.

    "lista mis notas" puede quedarse esperando permiso (fuera de su
    alcance). Entonces ARIA no se queda quieta: se propone otra cosa, que
    si es suya y local.
    """
    runtime = Runtime(data_dir=tmp_path / "autonomy", skills=FakeSkills())
    runtime._state["drives"] = {"curiosity": 0.95, "care": 0.2, "mastery": 0.1}
    runtime.agenda_add("lista mis notas", "ya esta en marcha")
    runtime._agenda[0]["state"] = "esperando"
    runtime._persist()

    resultado = runtime.tick()

    assert resultado["status"] == "ok"
    assert resultado["initiative"]["origin"] == "propia"
    objetivos = [item["goal"] for item in runtime.agenda()["agenda"]]
    assert "lista mis notas" in objetivos
    assert len(objetivos) >= 2
