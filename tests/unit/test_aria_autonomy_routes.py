"""Las rutas de autonomía sirven el runtime local: sin puertos, sin servicios.

El backend de v4 expone el mismo runtime que mueve el escritorio. Estos
tests comprueban que el contrato se mantiene y que nada depende de que otro
proceso esté encendido.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for _path in (str(ROOT), str(ROOT / "ARIA_APP")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from backend import autonomy_routes  # noqa: E402
from ARIA_APP.autonomy.runtime import Runtime  # noqa: E402


class FakeSkills:
    def list(self):
        return [{"id": "note_add", "name": "Agregar nota"}]

    def run(self, skill_id, params):
        if skill_id == "note_add":
            return {"status": "ok", "note": {"ts": 1.0, "text": params.get("text", "")}}
        return {"status": "error", "error": "sin detalle"}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    runtime = Runtime(data_dir=tmp_path / "autonomy", skills=FakeSkills())
    monkeypatch.setattr(autonomy_routes, "get_runtime", lambda: runtime)
    app = FastAPI()
    app.include_router(autonomy_routes.router)
    with TestClient(app) as test_client:
        test_client.runtime = runtime
        yield test_client


def test_el_estado_sale_del_runtime_local(client):
    response = client.get("/api/autonomy/status")

    assert response.status_code == 200
    body = response.json()
    assert body["server"] == "in-process"
    assert body["mode"] == "activa"
    assert body["persona"]["name"] == "ARIA"


def test_la_percepcion_tiene_mundos_locales(client):
    body = client.get("/api/perception").json()

    worlds = body["perception"]["worlds"]
    assert {world["id"] for world in worlds} >= {"escritorio", "memoria", "consola"}
    assert body["perception"]["drives"]
    assert body["perception"]["lessons"] == []


def test_la_agenda_crece_y_se_suelta(client):
    created = client.post("/api/autonomy/agenda", json={"goal": "revisar los logs"})
    assert created.status_code == 200
    initiative = created.json()["initiative"]
    assert initiative["goal"] == "revisar los logs"

    listed = client.get("/api/autonomy/agenda").json()
    assert listed["count"] == 1

    dropped = client.delete(f"/api/autonomy/agenda/{initiative['id']}").json()
    assert dropped["removed"] is True
    assert client.get("/api/autonomy/agenda").json()["count"] == 0


def test_una_ingesta_llega_al_runtime(client):
    response = client.post(
        "/api/autonomy/events",
        json={"kind": "chat", "text": "apunta revisar los logs", "source": "escritorio"},
    )

    assert response.status_code == 200
    assert client.get("/api/autonomy/agenda").json()["count"] == 1


def test_el_tick_ejecuta_lo_que_hay_entre_manos(client):
    client.post("/api/autonomy/events", json={"kind": "chat", "text": "hola"})

    body = client.post("/api/autonomy/tick", json={"reactive": True}).json()

    assert body["status"] in {"ok", "idle"}
    assert body["server"] == "in-process"


def test_el_freno_del_exterior_se_puede_cerrar(client):
    body = client.post("/api/autonomy/permissions", json={"allow_external": False}).json()

    assert body["allow_external"] is False


def test_las_lecciones_se_enseñan_y_se_silencian(client):
    created = client.post("/api/lessons", json={"text": "no abras el navegador"}).json()
    lesson_id = created["lesson"]["id"]

    listed = client.get("/api/lessons").json()
    assert listed["count"] == 1

    muted = client.patch(f"/api/lessons/{lesson_id}").json()
    assert muted["lesson"]["suppressed"] is True
    assert all(
        item["suppressed"] for item in client.get("/api/lessons").json()["lessons"]
    )


def test_presencia_y_persona(client):
    presence = client.post(
        "/api/autonomy/presence", json={"expression": "concentrada", "place": "Escritorio"}
    ).json()
    assert presence["presence"]["expression"] == "concentrada"

    persona = client.get("/api/autonomy/persona").json()
    assert persona["persona"]["language"] == "es"


def test_el_flujo_de_percepcion_esta_disponible():
    """El flujo es un `StreamingResponse`: no se serializa como JSON.

    No se pide el flujo entero: es infinito a propósito (ARIA sigue
    percibiendo mientras el cliente mire), así que lo que se comprueba es
    cómo queda montado.
    """
    import asyncio

    stream_route = [
        route for route in autonomy_routes.router.routes
        if getattr(route, "path", "") == "/api/autonomy/stream"
    ]
    assert stream_route, "el flujo de percepción debe estar montado"

    response = asyncio.run(autonomy_routes.autonomy_stream())
    assert getattr(response, "media_type", "") == "text/event-stream"
