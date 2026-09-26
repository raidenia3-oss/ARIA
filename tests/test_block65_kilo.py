"""BLOQUE 65 — Kilo integration tests: /api/vision/track REST endpoints + latency.

Complementa tests/test_block65.py (que cubre las clases del motor) validando:
- endpoints REST de tracking de plantillas de UI
- presupuesto de latencia de procesamiento de fotogramas locales
- higiene: sin dependencias de vision cloud (Google Cloud Vision, Azure, etc.)

Aislamiento: archivo separado de tests/test_block65.py (ediciones concurrentes).
"""

from __future__ import annotations

import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.vision.tracker import (
    MatchMode,
    get_template_tracker,
    reset_template_tracker,
    router,
)

SQUARE = [[0, 0], [10, 0], [10, 10], [0, 10]]
FAR_SQUARE = [[200, 200], [210, 200], [210, 210], [200, 210]]


@pytest.fixture
def client():
    reset_template_tracker()
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as c:
        yield c
    reset_template_tracker()


def _register(client, name, points=None, category="button"):
    r = client.post(
        "/api/vision/track/templates",
        json={
            "name": name,
            "points": points or SQUARE,
            "category": category,
        },
    )
    assert r.status_code == 200, r.text
    return r.json()["template"]


# --------------------------------------------------------------------------- #
# Rutas y registro de plantillas
# --------------------------------------------------------------------------- #


def test_router_paths():
    paths = [rt.path for rt in router.routes]
    assert router.prefix == "/api/vision/track"
    for p in (
        "/api/vision/track/status",
        "/api/vision/track/config",
        "/api/vision/track/templates",
        "/api/vision/track/templates/{name}",
        "/api/vision/track/detect",
        "/api/vision/track/last",
    ):
        assert p in paths


def test_register_list_delete_template(client):
    tpl = _register(client, "btn_reward")
    assert tpl["name"] == "btn_reward"
    assert tpl["category"] == "button"
    listed = client.get("/api/vision/track/templates").json()["templates"]
    assert any(t["name"] == "btn_reward" for t in listed)
    deleted = client.delete("/api/vision/track/templates/btn_reward")
    assert deleted.status_code == 200
    assert deleted.json()["removed"] is True
    listed2 = client.get("/api/vision/track/templates").json()["templates"]
    assert not any(t["name"] == "btn_reward" for t in listed2)


# --------------------------------------------------------------------------- #
# Deteccion via REST
# --------------------------------------------------------------------------- #


def test_detect_exact_match(client):
    _register(client, "btn_ok")
    r = client.post(
        "/api/vision/track/detect",
        json={
            "points": SQUARE,
            "mode": "exact",
        },
    )
    assert r.status_code == 200
    det = r.json()["detection"]
    assert det["error"] is None
    assert det["templates_checked"] == 1
    match = det["matches"][0]
    assert match["matched"] is True
    assert match["template_name"] == "btn_ok"
    assert match["confidence"] >= 0.99
    assert match["location"] is not None


def test_detect_no_match_low_confidence(client):
    _register(client, "btn_ok")
    r = client.post(
        "/api/vision/track/detect",
        json={
            "points": FAR_SQUARE,
            "mode": "exact",
        },
    )
    det = r.json()["detection"]
    match = det["matches"][0]
    assert match["matched"] is False
    assert match["confidence"] < 0.85


def test_detect_invalid_mode_422(client):
    _register(client, "btn_ok")
    r = client.post(
        "/api/vision/track/detect",
        json={
            "points": SQUARE,
            "mode": "not-a-mode",
        },
    )
    assert r.status_code == 422


def test_detect_filters_by_template_names(client):
    _register(client, "btn_a")
    _register(client, "btn_b", points=[[0, 0], [5, 0], [5, 5], [0, 5]])
    r = client.post(
        "/api/vision/track/detect",
        json={
            "points": SQUARE,
            "templates": ["btn_b"],
        },
    )
    det = r.json()["detection"]
    assert det["templates_checked"] == 1
    assert det["matches"][0]["template_name"] == "btn_b"


def test_detect_requires_points(client):
    r = client.post("/api/vision/track/detect", json={"points": []})
    det = r.json()["detection"]
    assert det["matches"] == []
    assert det["templates_checked"] == 0


def test_last_detection_endpoint(client):
    _register(client, "btn_ok")
    before = client.get("/api/vision/track/last").json()
    assert before["status"] == "error"
    client.post("/api/vision/track/detect", json={"points": SQUARE})
    after = client.get("/api/vision/track/last")
    assert after.status_code == 200
    assert after.json()["status"] == "ok"
    assert after.json()["detection"]["templates_checked"] == 1


# --------------------------------------------------------------------------- #
# Config y estado
# --------------------------------------------------------------------------- #


def test_status_endpoint(client):
    _register(client, "btn_status")
    r = client.get("/api/vision/track/status")
    assert r.status_code == 200
    data = r.json()
    assert data["threshold"] == pytest.approx(0.85)
    assert data["templates_registered"] == 1


def test_config_endpoint_updates_threshold_and_scale(client):
    r = client.post(
        "/api/vision/track/config",
        json={
            "threshold": 0.9,
            "scale": 2.0,
            "screen_width": 2560,
            "screen_height": 1440,
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["threshold"] == pytest.approx(0.9)
    assert data["scale"] == pytest.approx(2.0)
    assert data["screen_width"] == 2560


def test_coordinate_mapper_via_config_scale(client):
    """El mapper traduce deteccion relativa a pantalla absoluta con escala HiDPI."""
    tracker = get_template_tracker()
    tracker.update_config(scale=2.0)
    tracker.mapper.offset_x = 10
    tracker.mapper.offset_y = 20
    tracker.register_template("btn_abs", [tuple(p) for p in SQUARE])
    res = tracker.detect([tuple(p) for p in SQUARE])
    assert res.matches[0].matched is True
    ax, ay = tracker.map_coordinates(*res.matches[0].location)
    assert ax == pytest.approx(10 + 5 * 2.0)
    assert ay == pytest.approx(20 + 5 * 2.0)


# --------------------------------------------------------------------------- #
# Presupuesto de latencia (fotogramas locales)
# --------------------------------------------------------------------------- #


def test_detect_latency_budget_under_many_templates(client):
    for i in range(20):
        _register(
            client,
            f"tpl_{i}",
            points=[[i, i], [i + 10, i], [i + 10, i + 10], [i, i + 10]],
            category="button",
        )
    screen_points = [tuple(p) for p in SQUARE] * 3
    start = time.perf_counter()
    r = client.post(
        "/api/vision/track/detect",
        json={
            "points": [list(p) for p in screen_points],
        },
    )
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    assert r.status_code == 200
    det = r.json()["detection"]
    assert det["templates_checked"] == 20
    # Presupuesto: 20 plantillas contra 12 puntos debe resolverse rapido.
    assert elapsed_ms < 500.0, f"latencia excesiva: {elapsed_ms:.1f} ms"
    assert det["processing_time_ms"] < 500.0


# --------------------------------------------------------------------------- #
# Higiene: sin vision cloud, sin tokens
# --------------------------------------------------------------------------- #


def test_no_cloud_vision_deps_in_tracker():
    import backend.vision.tracker as mod

    src = open(mod.__file__, encoding="utf-8-sig").read()
    for bad in (
        "google.cloud",
        "azure",
        "boto3",
        "rekognition",
        "sentry_sdk",
        "googleapis",
        "vision.googleapis.com",
        "computervision",
        "access_token=",
        "api_key=",
        "secret=",
    ):
        assert bad not in src, f"cloud dep/token found in tracker: {bad}"
