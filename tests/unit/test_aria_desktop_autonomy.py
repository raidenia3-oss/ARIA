"""El latido de ARIA: la autonomía se mueve sola, en su proceso.

El escritorio no era quien movía al runtime: nadie llamaba a `tick()`, así
que la agenda se llenaba pero nadie ejecutaba nada. Estos tests comprueban
que el latido da vueltas de verdad, que lo que ARIA dice sola se puede ver,
y que ni el latido ni la franja levantan la app si algo falla.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for _path in (str(ROOT), str(ROOT / "ARIA_APP")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import desktop_autonomy  # noqa: E402
from ARIA_APP.autonomy.runtime import Runtime  # noqa: E402


class FakeSkills:
    def __init__(self) -> None:
        self.calls: list = []

    def list(self):
        return [{"id": "note_list", "name": "Listar notas"}]

    def run(self, skill_id, params):
        self.calls.append((skill_id, params))
        if skill_id == "file_read":
            return {"status": "error", "error": "archivo no encontrado"}
        return {"status": "ok", "notes": [], "count": 0}


@pytest.fixture()
def fake_runtime(monkeypatch, tmp_path):
    """Un runtime de mentira en el sitio del runtime del escritorio."""
    instance = Runtime(data_dir=tmp_path / "autonomy", skills=FakeSkills())
    monkeypatch.setattr(desktop_autonomy, "_runtime", instance)
    monkeypatch.setattr(desktop_autonomy, "set_runtime", lambda _r: None)
    return instance


# ── El latido ───────────────────────────────────────────────────────────────


def test_el_latido_da_una_vuelta_de_verdad(fake_runtime):
    """Un latido es un `tick()` real, no una lectura de estado."""
    fake_runtime.ingest("chat", "apunta lista mis notas", "escritorio", {"answered": True})

    beat = desktop_autonomy.Heartbeat(interval=999)
    result = beat.beat()

    assert beat.beats == 1
    assert result["status"] == "ok"
    assert fake_runtime.agenda()["agenda"][0]["state"] == "ejecutada"


def test_el_latido_avisa_a_quien_lo_escucha(fake_runtime):
    recibidos = []
    beat = desktop_autonomy.Heartbeat(interval=999, on_beat=recibidos.append)

    beat.beat()

    assert len(recibidos) == 1
    assert recibidos[0]["status"] in {"ok", "idle"}


def test_un_oyente_roto_no_tumba_el_latido(fake_runtime):
    def _explota(_resultado):
        raise RuntimeError("el oyente se ha caido")

    beat = desktop_autonomy.Heartbeat(interval=999, on_beat=_explota)

    result = beat.beat()

    assert result["status"] in {"ok", "idle"}
    assert beat.beats == 1


def test_arrancar_y_parar_el_latido(fake_runtime):
    beat = desktop_autonomy.Heartbeat(interval=0.05)
    beat.start()
    try:
        for _ in range(200):
            if beat.beats:
                break
            import time

            time.sleep(0.02)
    finally:
        beat.stop()

    assert beat.beats >= 1


def test_el_latido_compartido_es_el_mismo(fake_runtime):
    primero = desktop_autonomy.start_heartbeat(interval=999)
    try:
        segundo = desktop_autonomy.start_heartbeat(interval=999)
        assert primero is segundo
        assert desktop_autonomy.heartbeat() is primero
    finally:
        desktop_autonomy.stop_heartbeat()

    assert desktop_autonomy.heartbeat() is None


# ── Lo que ARIA hace, a la vista ────────────────────────────────────────────


def test_se_ve_lo_ultimo_que_aria_hizo(fake_runtime):
    fake_runtime.ingest("chat", "apunta lista mis notas", "escritorio", {"answered": True})
    fake_runtime.tick()

    linea = desktop_autonomy.episode_line(desktop_autonomy.last_episode(fake_runtime))

    assert linea
    assert "notas" in linea.lower()


def test_lo_que_aria_hace_sola_dice_de_quien_es(fake_runtime):
    fake_runtime._state["drives"] = {"curiosity": 0.95, "care": 0.2, "mastery": 0.1}
    fake_runtime.tick()

    agenda = fake_runtime.agenda()["agenda"]
    assert agenda
    assert agenda[0]["origin"] == "propia"
    assert "sola" in desktop_autonomy.goal_line(agenda[0])


def test_sin_historial_no_hay_linea_que_enseñar(fake_runtime):
    assert desktop_autonomy.episode_line(desktop_autonomy.last_episode(fake_runtime)) == ""


# ── Lo que ARIA hace, contado y dicho (P1, P3) ───────────────────────────────


def test_el_latido_cuenta_lo_que_aria_hace(fake_runtime):
    """Después de actuar, se ve: cuántas veces y qué aprendió."""
    fake_runtime.ingest("chat", "apunta lista mis notas", "escritorio", {"answered": True})
    fake_runtime.tick()

    linea = desktop_autonomy.lesson_line(fake_runtime.status())

    assert "acciones" in linea
    assert "latidos" in linea


def test_la_linea_del_latido_cuenta_lo_que_paso(fake_runtime):
    """Lo que ARIA ha hecho sale en una línea, tal y como quedo."""
    fake_runtime.ingest("chat", "apunta lista mis notas", "escritorio", {"answered": True})
    resultado = fake_runtime.tick()

    linea = desktop_autonomy.beat_summary(resultado)

    assert linea
    assert "notas" in linea.lower()


def test_el_latido_calla_cuando_no_pasa_nada(fake_runtime):
    """ARIA no dice "nada" cada 45 segundos: eso es ruido."""
    resultado = fake_runtime.tick()

    assert resultado["status"] == "idle"
    assert desktop_autonomy.beat_summary(resultado) == ""


def test_el_latido_cuenta_un_fallo_sin_echarle_la_culpa(fake_runtime):
    """Un fallo se cuenta como fallo, no como unaerteria."""
    fake_runtime.agenda_add("lee un archivo que no existe")
    resultado = fake_runtime.tick()

    linea = desktop_autonomy.beat_summary(resultado)

    assert linea
    assert linea.startswith("No pude")


# ── El escritorio: el runtime tiene manos y cabeza ──────────────────────────


def test_el_runtime_del_escritorio_tiene_manos():
    """El runtime del escritorio se apoya en el núcleo VA, no en un servicio."""
    instance = desktop_autonomy.runtime()

    assert instance is not None
    assert instance.skills is not None
    assert len(instance._capabilities()) > 0
