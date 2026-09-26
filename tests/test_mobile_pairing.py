import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.mobile_pairing import router as pairing_router
from backend.story_memory.session_context import clear_all
from backend.story_routes import router as story_router


@pytest.fixture
def client(monkeypatch, tmp_path):
    """Cliente FastAPI con routers de pairing + story en store temporal."""
    monkeypatch.setenv("AURA_STORY_DIR", str(tmp_path))
    clear_all()
    app = FastAPI()
    app.include_router(pairing_router)
    app.include_router(story_router)
    yield TestClient(app)
    clear_all()


def _pair(client, device_id="ame_test_1"):
    profile = client.get("/api/mobile/pairing/profile").json()
    r = client.post(
        "/api/mobile/pairing/handshake",
        json={
            "code": profile["code"],
            "token": profile["token"],
            "device_id": device_id,
            "device_name": "AME Test",
        },
    )
    assert r.status_code == 200, r.text
    return profile, r.json()


def test_ping_pong(client):
    r = client.get("/api/mobile/pairing/ping")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["service"] == "aura-host"


def test_profile_shape_and_lan_ip(client):
    r = client.get("/api/mobile/pairing/profile")
    assert r.status_code == 200
    body = r.json()
    assert body["port"] == 8000
    assert body["backend_url"].startswith("http://")
    assert len(body["code"]) == 6 and body["code"].isdigit()
    assert len(body["token"]) >= 32
    assert "aura_pairing" in body["qr_payload"]
    # La IP debe ser LAN (privada) o loopback — nunca 0.0.0.0
    assert body["host_ip"] != "0.0.0.0"
    assert len(body["host_ips"]) >= 1


def test_pairing_handshake_happy_path(client):
    profile, body = _pair(client)
    assert body["status"] == "paired"
    assert body["device_id"] == "ame_test_1"
    assert body["device_token"]  # token de dispositivo presente
    assert body["backend_url"].startswith("http://")


def test_pairing_code_single_use(client):
    profile, _ = _pair(client, "ame_single_1")
    # Segundo canje del mismo código → 409 ya usado / 404 no encontrado
    r = client.post(
        "/api/mobile/pairing/handshake",
        json={"code": profile["code"], "token": profile["token"], "device_id": "ame_2"},
    )
    assert r.status_code in (404, 409)


def test_pairing_wrong_token_rejected(client):
    client.get("/api/mobile/pairing/profile")
    profile = client.get("/api/mobile/pairing/profile").json()
    r = client.post(
        "/api/mobile/pairing/handshake",
        json={"code": profile["code"], "token": "f" * 64, "device_id": "ame_x"},
    )
    assert r.status_code == 401


def test_pairing_new_code_invalidates_previous(client):
    first = client.get("/api/mobile/pairing/profile").json()
    second = client.get("/api/mobile/pairing/profile").json()
    assert first["code"] != second["code"]
    r = client.post(
        "/api/mobile/pairing/handshake",
        json={"code": first["code"], "token": first["token"], "device_id": "ame_old"},
    )
    assert r.status_code == 404
    r = client.post(
        "/api/mobile/pairing/handshake",
        json={"code": second["code"], "token": second["token"], "device_id": "ame_new"},
    )
    assert r.status_code == 200


def test_paired_device_can_use_story_api(client):
    """Un dispositivo emparejado consulta la API de historia sin fricción."""
    _pair(client, "ame_story_1")
    r = client.post("/api/story/works", json={"work_id": "pw", "title": "Obra Pair"})
    assert r.status_code == 200
    r = client.get("/api/story/works")
    assert r.status_code == 200
    assert any(w["work_id"] == "pw" for w in r.json()["works"])
