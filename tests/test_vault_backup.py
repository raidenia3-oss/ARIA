"""Tests Bloque 32 func.3 — Discord Vault Auto-Backup (respaldo cifrado).

Valida:
- Estado de configuración sin exponer secretos.
- Cifrado/descifrado round-trip (Fernet + PBKDF2).
- Empaquetado de snapshots recientes en un bundle cifrado.
- Subida asíncrona a webhook (httpx mockeado) y camino "disabled".
- Endpoints REST de vault (/api/story/vault/status, /snapshots/backup).
"""

from __future__ import annotations

import json
import threading
import time

import pytest

from backend.story_memory.vault_backup import (
    DiscordVaultBackup,
    reset_vault_backup,
)
from backend.story_memory.versioning import set_engine_store_path


@pytest.fixture
def story_engine(tmp_path, monkeypatch):
    from backend.story_memory.versioning import get_snapshot_engine

    story_dir = str(tmp_path / "story")
    monkeypatch.setenv("AURA_STORY_DIR", story_dir)
    set_engine_store_path(story_dir)
    yield get_snapshot_engine()
    set_engine_store_path(None)
    reset_vault_backup()


@pytest.fixture
def work_with_snapshot(story_engine):
    from backend.story_memory.canon_tracker import CanonTracker
    from backend.story_memory.story_storage import StoryStorage

    store = StoryStorage(store_dir=story_engine.store_dir)
    store.create_work(
        work_id="vault_work", title="Obra Vault", universe="test", description="d", author="tester"
    )
    ct = CanonTracker()
    ct.add_canon_event(work_id="vault_work", description="Evento A", source="user")
    ct.add_canon_event(work_id="vault_work", description="Evento B", source="user")
    story_engine.create_snapshot("vault_work", message="checkpoint 1", author="tester")
    story_engine.create_snapshot("vault_work", message="checkpoint 2", author="tester")
    return story_engine


# -- estado de configuración -----------------------------------------------------


def test_status_disabled_when_not_configured(story_engine):
    vault = DiscordVaultBackup(engine=story_engine, webhook_url=None, passphrase=None)
    status = vault.status()
    assert status["configured"] is False
    assert status["level"] == "disabled"
    assert status["webhook_set"] is False
    assert status["passphrase_set"] is False


def test_status_ready_when_configured(story_engine):
    vault = DiscordVaultBackup(engine=story_engine, webhook_url="https://hook", passphrase="s3cret")
    status = vault.status()
    assert status["configured"] is True
    assert status["level"] == "ready"
    # No se filtran secretos en el reporte.
    assert "webhook_url" not in status and "passphrase" not in status


# -- cifrado round-trip ------------------------------------------------------------


def test_encrypt_decrypt_roundtrip(story_engine):
    vault = DiscordVaultBackup(
        engine=story_engine, webhook_url="https://hook", passphrase="frase-de-paso"
    )
    secret = b"contenido literario secreto"
    blob = vault.encrypt(secret)
    # Formato con prefijo de autenticación.
    assert blob.startswith(vault.FORMAT_PREFIX)
    # El texto plano no debe aparecer en el cifrado.
    assert secret not in blob
    assert vault.decrypt(blob) == secret


def test_decrypt_wrong_passphrase_fails(story_engine):
    vault_a = DiscordVaultBackup(
        engine=story_engine, webhook_url="https://hook", passphrase="clave-a"
    )
    blob = vault_a.encrypt(b"datos")
    vault_b = DiscordVaultBackup(
        engine=story_engine, webhook_url="https://hook", passphrase="clave-b"
    )
    with pytest.raises(Exception):
        vault_b.decrypt(blob)


# -- empaquetado --------------------------------------------------------------------


def test_package_bundles_recent_snapshots(work_with_snapshot):
    vault = DiscordVaultBackup(
        engine=work_with_snapshot, webhook_url="https://hook", passphrase="p4ss"
    )
    blob = vault.package("vault_work", recent_n=5)
    assert blob.startswith(vault.FORMAT_PREFIX)
    bundle = json.loads(vault.decrypt(blob))
    assert bundle["format"] == vault.FORMAT_ID
    assert bundle["work_id"] == "vault_work"
    assert bundle["count"] == 2
    assert [s["manifest"]["message"] for s in bundle["snapshots"]] == [
        "checkpoint 1",
        "checkpoint 2",
    ]


# -- subida --------------------------------------------------------------------------


class _FakeResponse:
    def __init__(self, code):
        self.status_code = code


def test_push_disabled_when_not_configured(work_with_snapshot):
    vault = DiscordVaultBackup(engine=work_with_snapshot, webhook_url=None, passphrase=None)
    res = vault.push("vault_work")
    assert res["status"] == "disabled"


def test_push_async_returns_accepted(work_with_snapshot, monkeypatch):
    import httpx as _httpx

    registry = {}

    def fake_post(url, **kwargs):
        files = kwargs.get("files", [])
        registry["url"] = url
        registry["filename"] = files[0][1][0]
        registry["payload"] = files[0][1][1]
        return _FakeResponse(200)

    monkeypatch.setattr(_httpx, "post", fake_post)

    vault = DiscordVaultBackup(
        engine=work_with_snapshot,
        webhook_url="https://discord.example/webhook",
        passphrase="p4ss-secret",
    )
    res = vault.push_async("vault_work")
    assert res["status"] == "accepted"

    # Esperar a que el hilo daemon complete el POST mockeado.
    for _ in range(100):
        if registry.get("payload"):
            break
        time.sleep(0.01)
    assert registry["url"] == "https://discord.example/webhook"
    assert registry["filename"] == "literary-main.bin"
    assert registry["payload"].startswith(vault.FORMAT_PREFIX)


def test_push_sync_uploads_encrypted_payload(work_with_snapshot, monkeypatch):
    import httpx as _httpx

    captured = {}

    def fake_post(url, **kwargs):
        captured["payload"] = kwargs["files"][0][1][1]
        return _FakeResponse(204)

    monkeypatch.setattr(_httpx, "post", fake_post)

    vault = DiscordVaultBackup(
        engine=work_with_snapshot,
        webhook_url="https://discord.example/webhook",
        passphrase="p4ss-secret",
    )
    res = vault.push("vault_work")
    assert res["status"] == "ok"
    assert res["uploaded"] is True
    assert res["encrypted"] is True
    assert res["count"] == 2
    assert captured["payload"].startswith(vault.FORMAT_PREFIX)
    # El bundle viaja cifrado: el texto de los snapshots no debe aparecer en claro.
    assert b"checkpoint" not in captured["payload"]


# -- REST ----------------------------------------------------------------------------------


@pytest.fixture
def rest_client(monkeypatch, tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from backend.story_memory.canon_tracker import CanonTracker
    from backend.story_memory.story_storage import StoryStorage
    from backend.story_memory.versioning import get_snapshot_engine
    from backend.story_routes import router as story_router

    story_dir = str(tmp_path / "story")
    monkeypatch.setenv("AURA_STORY_DIR", story_dir)
    set_engine_store_path(story_dir)
    store = StoryStorage(store_dir=story_dir)
    store.create_work(
        work_id="vault_rest", title="REST Vault", universe="test", description="d", author="tester"
    )
    ct = CanonTracker()
    ct.add_canon_event(work_id="vault_rest", description="Evento REST", source="user")
    get_snapshot_engine().create_snapshot("vault_rest", message="rest snap")

    api = FastAPI()
    api.include_router(story_router)
    yield TestClient(api)
    set_engine_store_path(None)
    reset_vault_backup()


def test_rest_vault_status(rest_client):
    r = rest_client.get("/api/story/vault/status")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "configured" in body
    # No se filtran secretos.
    assert "webhook_url" not in body and "passphrase" not in body


def test_rest_backup_disabled_when_not_configured(rest_client):
    r = rest_client.post("/api/story/vault_rest/snapshots/backup", json={"branch": "main"})
    assert r.json()["status"] == "disabled"


def test_rest_backup_async_disabled(rest_client):
    r = rest_client.post(
        "/api/story/vault_rest/snapshots/backup", json={"sync": True, "recent_n": 3}
    )
    assert r.status_code == 200
    assert r.json()["status"] == "disabled"
