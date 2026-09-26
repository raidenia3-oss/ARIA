"""BLOQUE 70 - Kilo integration tests: /api/evolution/patch REST."""

import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.evolution.patcher import (
    EvolutionPatchEngine,
    PatchType,
    reset_engine,
    router,
    set_engine,
)

_TARGET = os.path.join("backend", "_b70_kilo_mod.py")


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_EVOLUTION70_DIR", str(tmp_path / "ev70"))
    reset_engine()
    set_engine(EvolutionPatchEngine())
    with open(_TARGET, "w", encoding="utf-8") as fh:
        fh.write("def f():\n    return 1\n")
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as c:
        yield c
    reset_engine()
    if os.path.exists(_TARGET):
        os.remove(_TARGET)


def test_router_paths():
    paths = [rt.path for rt in router.routes]
    assert router.prefix == "/api/evolution/patch"
    for p in (
        "/api/evolution/patch/status",
        "/api/evolution/patch/audit",
        "/api/evolution/patch/propose",
        "/api/evolution/patch/propose/autonomous",
        "/api/evolution/patch/patches",
        "/api/evolution/patch/{patch_id}",
        "/api/evolution/patch/{patch_id}/test",
        "/api/evolution/patch/{patch_id}/apply",
        "/api/evolution/patch/{patch_id}/rollback",
        "/api/evolution/patch/{patch_id}/snapshot",
    ):
        assert p in paths, p


def test_status(client):
    r = client.get("/api/evolution/patch/status")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_audit(client, tmp_path):
    bad = tmp_path / "bad.py"
    bad.write_text("eval('1')\n", encoding="utf-8")
    r = client.get("/api/evolution/patch/audit", params={"root": str(tmp_path), "max_files": 10})
    assert r.status_code == 200
    assert r.json()["count"] >= 1


def test_propose_and_apply(client):
    r = client.post(
        "/api/evolution/patch/propose",
        json={
            "target_file": _TARGET,
            "old_snippet": "def f():\n    return 1\n",
            "new_snippet": "def f():\n    return 2\n",
            "description": "fix",
            "patch_type": "bugfix",
        },
    )
    assert r.status_code == 200
    patch_id = r.json()["patch_id"]
    r = client.post(f"/api/evolution/patch/{patch_id}/test")
    assert r.status_code == 200
    assert r.json()["outcome"] == "passed"
    r = client.post(f"/api/evolution/patch/{patch_id}/apply", params={"run_sandbox": False})
    assert r.status_code == 200
    assert r.json()["status"] == "applied"
    assert open(_TARGET, encoding="utf-8").read() == "def f():\n    return 2\n"
    r = client.post(f"/api/evolution/patch/{patch_id}/rollback")
    assert r.status_code == 200
    assert r.json()["status"] == "rolled_back"
    assert open(_TARGET, encoding="utf-8").read() == "def f():\n    return 1\n"


def test_propose_unauthorized(client, tmp_path):
    target = tmp_path / "main.py"
    target.write_text("print('hi')\n", encoding="utf-8")
    r = client.post(
        "/api/evolution/patch/propose",
        json={
            "target_file": str(target),
            "old_snippet": "print('hi')\n",
            "new_snippet": "print('bye')\n",
            "description": "x",
        },
    )
    assert r.status_code == 400


def test_propose_autonomous(client):
    r = client.post(
        "/api/evolution/patch/propose/autonomous",
        json={
            "traces": [
                {"file": "backend/x.py", "line": 1, "message": "boom"},
                {"file": "backend/x.py", "line": 2, "message": "ok"},
            ]
        },
    )
    assert r.status_code == 200
    assert r.json()["count"] == 2


def test_patch_not_found(client):
    r = client.get("/api/evolution/patch/nope")
    assert r.status_code == 404
    r = client.post("/api/evolution/patch/nope/test")
    assert r.status_code == 404


def test_no_cloud_deps():
    import backend.evolution.patcher as mod

    src = open(mod.__file__, encoding="utf-8").read().lower()
    for bad in (
        "openai",
        "anthropic",
        "cohere",
        "huggingface_hub",
        "github copilot",
        "copilot",
        "aws",
        "gcp",
        "azure",
        "access_token=",
        "api_key=",
        "secret=",
    ):
        assert bad not in src, f"cloud dep found: {bad}"
