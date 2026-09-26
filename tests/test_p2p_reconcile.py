"""Tests Bloque 50 — AURA Offline Sync & P2P Conflict Resolution Engine.

Valida (sin red real ni cloud):
- doc_hash: hash SHA-256 estable y sensible al contenido.
- _decide: matriz three-way (in_sync / push_to_sd / pull_from_sd / conflict).
- _merge_metadata: fusión de metadatos (unión + conflictos por clave).
- P2PReconciler.reconcile: pipeline completo con respaldos automáticos.
- Endpoints REST: POST /api/sync/reconcile, GET /status, GET /backups.
- Notificación WebSocket best-effort (mockeada, sin bloquear la respuesta).
- Sin pérdida de datos: toda edición concurrente queda respaldada.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import backend.p2p_reconcile as p2p
from backend.p2p_reconcile import (
    P2PReconciler,
    doc_hash,
    get_p2p_reconciler,
)

H_A, H_B = "sha256:aaa", "sha256:bbb"


def _doc(doc_id="w1/character/hero", base=H_A, sd=None, pc=None, type_="character", work_id="w1"):
    d = {"doc_id": doc_id, "type": type_, "work_id": work_id, "base_hash": base}
    if sd is not None:
        d["sd"] = sd
    if pc is not None:
        d["pc"] = pc
    return d


@pytest.fixture(autouse=True)
def _isolated_sync_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_SYNC_DIR", str(tmp_path / "sync"))
    yield


@pytest.fixture()
def client():
    app = FastAPI()
    app.include_router(p2p.router)
    return TestClient(app)


# ------------------------------------------------------------------ doc_hash


def test_doc_hash_is_stable_and_content_sensitive():
    payload_a = {"name": "Ariadna", "role": "protagonista"}
    payload_b = {"name": "Ariadna", "role": "antagonista"}
    h1 = doc_hash(payload_a)
    assert h1 == doc_hash({"role": "protagonista", "name": "Ariadna"})  # orden irrelevante
    assert h1 != doc_hash(payload_b)
    assert h1.startswith("sha256:")


def test_doc_hash_tolerates_unserializable_payload():
    assert doc_hash({"x": object()}).startswith("sha256:")


# -------------------------------------------------------------------- _decide


def test_decide_in_sync_when_hashes_equal():
    d = _doc(sd={"hash": H_A, "updated_at": 100}, pc={"hash": H_A, "updated_at": 100})
    assert p2p._decide(d, "lww") == ("in_sync", "")


def test_decide_pull_from_sd_when_pc_unchanged():
    d = _doc(sd={"hash": H_B, "updated_at": 300}, pc={"hash": H_A, "updated_at": 100})
    assert p2p._decide(d, "lww") == ("pull_from_sd", "sd")


def test_decide_push_to_sd_when_sd_unchanged():
    d = _doc(sd={"hash": H_A, "updated_at": 100}, pc={"hash": H_B, "updated_at": 200})
    assert p2p._decide(d, "lww") == ("push_to_sd", "pc")


def test_decide_conflict_when_both_diverge():
    d = _doc(sd={"hash": H_B, "updated_at": 500}, pc={"hash": "sha256:ccc", "updated_at": 200})
    decision, winner = p2p._decide(d, "lww")
    assert decision == "conflict"
    assert winner == "sd"  # 500 > 200 (LWW)


def test_decide_conflict_pc_wins_when_pc_newer():
    d = _doc(sd={"hash": H_B, "updated_at": 100}, pc={"hash": "sha256:ccc", "updated_at": 900})
    assert p2p._decide(d, "lww")[1] == "pc"


def test_decide_doc_only_in_sd_or_only_in_pc():
    only_sd = _doc(sd={"hash": H_B, "updated_at": 10})
    only_pc = _doc(pc={"hash": H_A, "updated_at": 10})
    assert p2p._decide(only_sd, "lww") == ("pull_from_sd", "sd")
    assert p2p._decide(only_pc, "lww") == ("push_to_sd", "pc")


def test_decide_explicit_strategies_override_lww():
    d = _doc(sd={"hash": H_B, "updated_at": 500}, pc={"hash": "sha256:ccc", "updated_at": 200})
    assert p2p._decide(d, "pc_wins")[1] == "pc"
    assert p2p._decide(d, "sd_wins")[1] == "sd"


# ------------------------------------------------------------ _merge_metadata


def test_merge_metadata_unions_non_conflicting_keys():
    merged, conflicts = p2p._merge_metadata(
        {"age": 30, "role": "hero"},
        {"alias": "Ari"},
        100,
        100,
    )
    assert merged == {"age": 30, "role": "hero", "alias": "Ari"}
    assert conflicts == []


def test_merge_metadata_resolves_conflicts_by_recency():
    merged, conflicts = p2p._merge_metadata(
        {"mood": "calm"},
        {"mood": "furious"},
        100,
        500,
    )
    assert merged["mood"] == "furious"  # SD más reciente gana
    assert conflicts == ["mood"]

    merged2, conflicts2 = p2p._merge_metadata(
        {"mood": "calm"},
        {"mood": "furious"},
        900,
        100,
    )
    assert merged2["mood"] == "calm"  # PC más reciente gana
    assert conflicts2 == ["mood"]


def test_merge_metadata_tolerates_none():
    merged, conflicts = p2p._merge_metadata(None, None, 0, 0)
    assert merged == {} and conflicts == []


# ------------------------------------------------- P2PReconciler.reconcile


def test_reconcile_in_sync_document():
    rec = P2PReconciler()
    doc = _doc(
        sd={"hash": H_A, "updated_at": 100, "version": 1},
        pc={"hash": H_A, "updated_at": 100, "version": 1},
    )
    report = rec.reconcile([doc], device_id="ame_1")
    assert report["status"] == "ok"
    assert report["in_sync"] == 1
    assert report["conflicts"] == 0
    assert report["backups_created"] == 0
    assert report["documents"][0]["decision"] == "in_sync"


def test_reconcile_pull_from_sd_adopts_sd_version():
    rec = P2PReconciler()
    doc = _doc(
        sd={"hash": H_B, "updated_at": 300, "version": 2, "payload": {"text": "SD"}},
        pc={"hash": H_A, "updated_at": 100, "version": 1},
    )
    report = rec.reconcile([doc], device_id="ame_1")
    assert report["pulled_to_pc"] == 1
    assert report["adopted_from_sd"] == ["w1/character/hero"]
    assert report["documents"][0]["winner"] == "sd"


def test_reconcile_push_to_sd_when_sd_stale():
    rec = P2PReconciler()
    doc = _doc(
        sd={"hash": H_A, "updated_at": 100, "version": 1},
        pc={"hash": H_B, "updated_at": 400, "version": 2, "payload": {"text": "PC"}},
    )
    report = rec.reconcile([doc], device_id="ame_1")
    assert report["pushed_to_sd"] == 1
    assert report["documents"][0]["winner"] == "pc"
    assert report["backups_created"] == 0  # no hubo edición concurrente


def test_reconcile_conflict_lww_creates_backup_without_data_loss():
    rec = P2PReconciler()
    sd = {
        "hash": H_B,
        "updated_at": 500,
        "version": 3,
        "payload": {"text": "version SD"},
        "metadata": {"mood": "furious"},
    }
    pc = {
        "hash": "sha256:ccc",
        "updated_at": 200,
        "version": 2,
        "payload": {"text": "version PC"},
        "metadata": {"mood": "calm"},
    }
    doc = _doc(sd=sd, pc=pc)
    report = rec.reconcile([doc], device_id="ame_1", strategy="lww")
    assert report["conflicts"] == 1
    assert report["backups_created"] == 1
    res = report["documents"][0]
    assert res["decision"] == "conflict"
    assert res["winner"] == "sd"  # LWW: 500 > 200
    assert res["backup_path"] and Path(res["backup_path"]).exists()

    # El respaldo conserva AMBAS versiones (sin pérdida de datos).
    backup = json.loads(Path(res["backup_path"]).read_text(encoding="utf-8"))
    assert backup["pc"]["payload"]["text"] == "version PC"
    assert backup["sd"]["payload"]["text"] == "version SD"
    assert backup["winner"] == "sd"
    assert backup["reason"] == "concurrent_edit"


def test_reconcile_conflict_merge_unions_metadata():
    rec = P2PReconciler()
    sd = {
        "hash": H_B,
        "updated_at": 500,
        "version": 3,
        "metadata": {"mood": "furious", "alias": "Ari"},
    }
    pc = {
        "hash": "sha256:ccc",
        "updated_at": 200,
        "version": 2,
        "metadata": {"mood": "calm", "age": 30},
    }
    doc = _doc(sd=sd, pc=pc)
    report = rec.reconcile([doc], device_id="ame_1", strategy="merge")
    res = report["documents"][0]
    assert res["decision"] == "conflict"
    assert res["resolution"] == "merged"
    assert res["merged_metadata"] == {"mood": "furious", "alias": "Ari", "age": 30}
    assert res["metadata_conflicts"] == ["mood"]
    assert res["backup_path"]  # el perdedor queda respaldado


def test_reconcile_explicit_pc_wins_strategy():
    rec = P2PReconciler()
    doc = _doc(sd={"hash": H_B, "updated_at": 999}, pc={"hash": "sha256:ccc", "updated_at": 1})
    report = rec.reconcile([doc], device_id="ame_1", strategy="pc_wins")
    assert report["documents"][0]["winner"] == "pc"
    assert report["conflicts"] == 1
    assert report["backups_created"] == 1


def test_reconcile_rejects_malformed_documents():
    rec = P2PReconciler()
    report = rec.reconcile(
        [
            {"type": "character"},  # sin doc_id
            {"doc_id": "x"},  # sin sd/pc
            {"doc_id": "y", "sd": {"updated_at": 1}},
        ],  # sd sin hash
        device_id="ame_1",
    )
    assert len(report["rejected"]) == 3
    assert report["reconciled"] == 0
    assert report["status"] == "ok"


def test_reconcile_persists_state_and_updates_registry():
    rec = P2PReconciler()
    doc = _doc(
        sd={"hash": H_B, "updated_at": 300, "version": 2},
        pc={"hash": H_A, "updated_at": 100, "version": 1},
    )
    rec.reconcile([doc], device_id="ame_9")
    state = json.loads((Path(p2p._sync_dir()) / p2p.STATE_FILENAME).read_text(encoding="utf-8"))
    assert state["last_device"] == "ame_9"
    assert state["reconcile_count"] == 1
    assert state["docs"]["w1/character/hero"]["hash"] == H_B
    assert state["last_summary"]["conflicts"] == 0


def test_reconcile_mixed_batch_counters():
    rec = P2PReconciler()
    docs = [
        _doc("d1", sd={"hash": H_A, "updated_at": 1}, pc={"hash": H_A, "updated_at": 1}),
        _doc("d2", sd={"hash": H_A, "updated_at": 1}, pc={"hash": H_B, "updated_at": 2}),
        _doc("d3", sd={"hash": H_B, "updated_at": 3}, pc={"hash": H_A, "updated_at": 1}),
        _doc("d4", sd={"hash": H_B, "updated_at": 9}, pc={"hash": "sha256:z", "updated_at": 8}),
    ]
    report = rec.reconcile(docs, device_id="ame_1")
    assert report["in_sync"] == 1
    assert report["pushed_to_sd"] == 1
    assert report["pulled_to_pc"] == 1
    assert report["conflicts"] == 1
    assert report["backups_created"] == 1
    assert report["reconciled"] == 4


def test_reconcile_broadcasts_ws_event_best_effort():
    rec = P2PReconciler()
    fake_gateway = MagicMock()
    doc = _doc(sd={"hash": H_A, "updated_at": 1}, pc={"hash": H_A, "updated_at": 1})
    with patch.object(p2p, "ws_gateway", fake_gateway, create=True):
        report = rec.reconcile([doc], device_id="ame_1")
    assert report["status"] == "ok"  # nunca lanza aunque el broadcast falle


def test_reconcile_does_not_crash_without_event_loop():
    rec = P2PReconciler()
    doc = _doc(sd={"hash": H_A, "updated_at": 1}, pc={"hash": H_A, "updated_at": 1})
    report = rec.reconcile([doc], device_id="ame_1")  # fuera de asyncio
    assert report["status"] == "ok"


def test_get_p2p_reconciler_singleton():
    assert get_p2p_reconciler() is get_p2p_reconciler()
