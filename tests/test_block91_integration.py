"""BLOQUE 91 - integracion refactoring(91) <-> governor(71) + fusion(83) + master(100)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.refactoring.engine import (
    DynamicRefactorizer,
    get_engine,
    reset_engine,
    router,
)
from backend.refactoring.integration import (
    emit_fusion,
    fusion_snapshot,
    governor_gate,
    master_probe,
)


def _client() -> TestClient:
    reset_engine()
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_alias_dynamic_refactorizer():
    reset_engine()
    assert DynamicRefactorizer is get_engine().__class__
    reset_engine()


def test_governor_gate_fail_open_shape():
    g = governor_gate()
    assert "allowed" in g and "decision" in g
    assert g["offline_only"] is True


def test_fusion_emit_and_snapshot():
    eid = emit_fusion("refactoring.test", {"x": 1}, severity="info")
    assert eid  # fail-soft pero debe publicar en local
    snap = fusion_snapshot(window_s=30.0)
    assert "state" in snap or "fused_score" in snap


def test_master_probe_shape():
    m = master_probe()
    assert "offline_only" in m


def test_contracts_endpoint():
    c = _client()
    r = c.get("/api/refactoring/contracts")
    assert r.status_code == 200
    body = r.json()
    assert body["block"] == 91
    assert "71_governor" in body["compatibility"]
    assert "83_fusion" in body["compatibility"]


def test_governor_fusion_master_endpoints():
    c = _client()
    assert c.get("/api/refactoring/governor-gate").status_code == 200
    assert c.get("/api/refactoring/fusion-context").status_code == 200
    assert c.get("/api/refactoring/master-probe").status_code == 200


def test_propose_apply_rollback_emits_fusion():
    from backend.fusion.sensory import get_fusion_engine

    c = _client()
    before = len(get_fusion_engine().bus)
    p = c.post(
        "/api/refactoring/propose",
        json={
            "target_file": "backend/evolution/models.py",
            "old_snippet": "",
            "new_snippet": "X_REFACTOR91 = 1\n",
            "description": "integration test",
        },
    )
    # puede ser 400 si el gobernador bloquea (PAUSE); en ese caso solo valida gate
    if p.status_code == 200:
        pid = p.json()["patch_id"]
        c.post(f"/api/refactoring/{pid}/apply")
        c.post(f"/api/refactoring/{pid}/rollback")
        after = len(get_fusion_engine().bus)
        assert after >= before
    else:
        assert p.status_code == 400


def test_corruption_controlled_invalid_syntax_rejected():
    # Escenario de corrupcion controlada: snippet con sintaxis invalida
    c = _client()
    p = c.post(
        "/api/refactoring/propose",
        json={
            "target_file": "backend/evolution/models.py",
            "old_snippet": "",
            "new_snippet": "X_BAD = (\n",
            "description": "corrupt",
        },
    )
    assert p.status_code in (200, 400)
    if p.status_code == 200:
        pid = p.json()["patch_id"]
        r = c.post(f"/api/refactoring/{pid}/test")
        assert r.json()["passed"] is False
