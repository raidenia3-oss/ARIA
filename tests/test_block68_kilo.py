"""BLOQUE 68 - Kilo integration tests: /api/security/vault REST."""

import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.security.crypto import EncryptedStore
from backend.security.vault import (
    CredentialVaultEngine,
    reset_engine,
    router,
    set_engine,
)


@pytest.fixture
def client(tmp_path):
    reset_engine()
    store_dir = tmp_path / "vault"
    store_dir.mkdir()
    os.environ["AURA_VAULT_DIR"] = str(store_dir)
    store = EncryptedStore(vault_dir=store_dir)
    set_engine(CredentialVaultEngine(store=store))
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as c:
        yield c
    reset_engine()
    os.environ.pop("AURA_VAULT_DIR", None)


def test_router_paths():
    paths = [rt.path for rt in router.routes]
    assert router.prefix == "/api/security/vault"
    for p in (
        "/api/security/vault/status",
        "/api/security/vault/unlock",
        "/api/security/vault/lock",
        "/api/security/vault/audit",
        "/api/security/vault/profiles",
        "/api/security/vault/profiles/{profile_id}",
        "/api/security/vault/profiles/{profile_id}/credentials/{key}",
        "/api/security/vault/profiles/{profile_id}/sessions",
    ):
        assert p in paths, p


def test_status_locked(client):
    r = client.get("/api/security/vault/status")
    assert r.status_code == 200
    assert r.json()["is_locked"] is True


def test_unlock_bad_secret(client):
    # Fresh vault: first unlock creates the verifier (any secret accepted).
    r = client.post("/api/security/vault/unlock", json={"master_secret": "right"})
    assert r.status_code == 200
    client.post("/api/security/vault/lock")
    # Now a wrong secret must be rejected.
    r = client.post("/api/security/vault/unlock", json={"master_secret": "wrong"})
    assert r.status_code == 403


def test_full_flow(client):
    # unlock
    r = client.post("/api/security/vault/unlock", json={"master_secret": "master-secret"})
    assert r.status_code == 200
    assert r.json()["status"] == "unlocked"

    # create profile
    r = client.post(
        "/api/security/vault/profiles",
        json={
            "profile_id": "p1",
            "name": "n",
            "service": "s",
        },
    )
    assert r.status_code == 200
    assert r.json()["profile"]["profile_id"] == "p1"

    # duplicate
    r = client.post(
        "/api/security/vault/profiles",
        json={
            "profile_id": "p1",
            "name": "n2",
            "service": "s2",
        },
    )
    assert r.status_code == 409

    # list
    r = client.get("/api/security/vault/profiles")
    assert r.status_code == 200
    assert r.json()["total"] == 1

    # get
    r = client.get("/api/security/vault/profiles/p1")
    assert r.status_code == 200

    # credential
    r = client.post(
        "/api/security/vault/profiles/p1/credentials",
        json={
            "key": "api_key",
            "value": "secret123",
            "kind": "token",
        },
    )
    assert r.status_code == 200
    r = client.get("/api/security/vault/profiles/p1/credentials/api_key")
    assert r.status_code == 200
    assert r.json()["credential"]["value"] == "secret123"

    # session
    r = client.post(
        "/api/security/vault/profiles/p1/sessions",
        json={
            "cookies": [{"cookie_name": "sess", "cookie_value": "abc"}],
        },
    )
    assert r.status_code == 200
    r = client.get("/api/security/vault/profiles/p1/sessions")
    assert r.status_code == 200
    assert r.json()["total"] == 1

    # audit
    r = client.get("/api/security/vault/audit")
    assert r.status_code == 200
    assert len(r.json()["events"]) >= 1

    # lock
    r = client.post("/api/security/vault/lock")
    assert r.status_code == 200
    assert r.json()["status"] == "locked"

    # locked now
    r = client.get("/api/security/vault/profiles")
    assert r.status_code == 403


def test_delete_profile(client):
    client.post("/api/security/vault/unlock", json={"master_secret": "m"})
    client.post(
        "/api/security/vault/profiles",
        json={
            "profile_id": "p1",
            "name": "n",
            "service": "s",
        },
    )
    r = client.delete("/api/security/vault/profiles/p1")
    assert r.status_code == 200
    r = client.delete("/api/security/vault/profiles/p1")
    assert r.status_code == 404


def test_update_profile(client):
    client.post("/api/security/vault/unlock", json={"master_secret": "m"})
    client.post(
        "/api/security/vault/profiles",
        json={
            "profile_id": "p1",
            "name": "n",
            "service": "s",
        },
    )
    r = client.put("/api/security/vault/profiles/p1", json={"name": "n2"})
    assert r.status_code == 200
    assert r.json()["profile"]["name"] == "n2"
    r = client.put("/api/security/vault/profiles/nope", json={"name": "x"})
    assert r.status_code == 404


def test_remove_credential(client):
    client.post("/api/security/vault/unlock", json={"master_secret": "m"})
    client.post(
        "/api/security/vault/profiles",
        json={
            "profile_id": "p1",
            "name": "n",
            "service": "s",
        },
    )
    client.post(
        "/api/security/vault/profiles/p1/credentials",
        json={
            "key": "k",
            "value": "v",
        },
    )
    r = client.delete("/api/security/vault/profiles/p1/credentials/k")
    assert r.status_code == 200
    r = client.delete("/api/security/vault/profiles/p1/credentials/k")
    assert r.status_code == 404
