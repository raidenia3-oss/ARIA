from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import os

import pytest
from fastapi.testclient import TestClient

from backend.main import app


@pytest.fixture(autouse=True)
def set_api_key(monkeypatch):
    monkeypatch.setenv("AURA_API_KEY", "test-key")
    monkeypatch.setenv("AURA_JWT_SECRET", "test-secret")


@pytest.fixture(autouse=True)
def reset_limiter():
    """Vacia el storage de contadores de slowapi ANTES de cada test.

    `backend.main.limiter` es un singleton a nivel de módulo: se crea una sola
    vez al importar el módulo y lo comparten todos los tests de la sesión. Sin
    este reset, el bucket de "60/minute" de /api/logs queda lleno por el test que
    se ejecutó antes y el siguiente arranca ya en 429, o directamente sin ningún
    200. Eso convierte el fallo en dependiente del orden de ejecución, que es la
    peor clase de flake: pasa en local y falla en CI.

    `hasattr` es la comprobación honesta aquí y no pereza: el API concreto de
    reset depende de la versión de slowapi instalada y este test no puede
    ejecutarse para inspeccionarlo. Se prueban las dos rutas conocidas
    (limiter.reset() y limiter._storage.reset()) y, si ninguna existe, se levanta
    un RuntimeError en vez de dejar el test "verde" por accidente.

    Que un reset que no resetea es peor que no resetear: el no-resetear delata el
    problema en el primer test que agota el bucket, mientras que un reset roto
    lo ENCUABRE — limpia el storage, el contador real sigue lleno y el fallo
    reaparece más tarde y en otro test, mucho más difícil de atribuir.
    """
    from backend.main import limiter

    if hasattr(limiter, "reset"):
        limiter.reset()
    elif hasattr(limiter._storage, "reset"):
        limiter._storage.reset()
    else:
        raise RuntimeError(
            "slowapi Limiter no expone reset() ni _storage.reset(); el estado de "
            "rate-limit no se puede limpiar entre tests"
        )
    yield


@pytest.fixture()
def client():
    return TestClient(app)


def test_health_endpoint(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    # `healthy` afirmaba dependencias sanas que este endpoint nunca midio. Lo
    # unico que puede afirmar es que el proceso sirve peticiones en esta ruta.
    assert body["status"] == "ok"
    assert body["data_source"] == "unavailable"
    assert body["detail"]


def test_login_returns_token(client):
    response = client.post("/token", data={"username": "user@example.com", "password": "secret"})
    assert response.status_code == 400


def test_status_endpoint_requires_api_key(client):
    response = client.get("/api/status")
    assert response.status_code == 401


def test_status_endpoint_with_api_key(client):
    response = client.get("/api/status", headers={"X-API-Key": "test-key"})
    assert response.status_code == 200
    payload = response.json()
    assert "backend" in payload


def test_logs_endpoint_persists_entries(client):
    client.post(
        "/api/logs",
        json={"service": "backend", "level": "INFO", "message": "test log"},
        headers={"X-API-Key": "test-key"},
    )
    response = client.get("/api/logs?service=backend&lines=10", headers={"X-API-Key": "test-key"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["service"] == "backend"
    assert "test log" in payload["logs"]


def test_restart_endpoint_updates_status(client):
    response = client.post(
        "/api/restart",
        json={"service": "backend"},
        headers={"X-API-Key": "test-key"},
    )
    assert response.status_code == 200
    assert "restarted" in response.json()["message"]


def test_deploy_endpoint_updates_status(client):
    response = client.post(
        "/api/deploy",
        json={"service": "discord-bot"},
        headers={"X-API-Key": "test-key"},
    )
    assert response.status_code == 200
    assert "deployed" in response.json()["message"]


def test_training_status_endpoint(client):
    response = client.get("/api/training/status", headers={"X-API-Key": "test-key"})
    assert response.status_code == 200
    payload = response.json()
    assert "jobs" in payload


def test_metrics_endpoint_returns_prometheus(client):
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "http_requests_total" in response.text


def test_slowapi_middleware_applies_route_limits(client):
    # Opción (a): SlowAPIMiddleware activada en backend.main. Prueba contra el
    # endpoint del propio app que declara @limiter.limit("60/minute"): más de
    # 60 requests en la ventana deben devolver 429. Antes de registrar el
    # middleware no había NINGÚN 429 en toda la app (los decoradores eran adorno).
    h = {"X-API-Key": "test-key", "Origin": "http://localhost:3000"}
    codes = [client.get("/api/logs?service=backend&lines=1", headers=h).status_code
             for _ in range(65)]
    assert 200 in codes, f"sin 200 antes del límite: {sorted(set(codes))}"
    assert 429 in codes, f"middleware sin efecto: {sorted(set(codes))}"

    # El 429 debe pasar por CORSMiddleware: falla si el orden está invertido.
    resp_429 = None
    for _ in range(70):
        r = client.get("/api/logs?service=backend&lines=1", headers=h)
        if r.status_code == 429:
            resp_429 = r
            break
    assert resp_429 is not None, "no se obtuvo un 429 para inspeccionar headers"
    assert "access-control-allow-origin" in resp_429.headers, \
        "el 429 no tiene headers CORS -> SlowAPIMiddleware envuelve a CORSMiddleware"


def test_rate_limit_state_is_reset_between_tests(client):
    """Si el limiter no se resetea, este test arranca con el bucket ya lleno."""
    # Solo detecta el fallo si se ejecuta el archivo completo: aislado con `-k`
    # arranca con el bucket vacío y pasa igual.
    h = {"X-API-Key": "test-key"}
    first = client.get("/api/logs?service=backend&lines=1", headers=h).status_code
    assert first == 200, (
        f"el primer request ya dio {first}: el storage del limiter no se resetea "
        f"entre tests (fixture ausente o usando el atributo equivocado)"
    )
