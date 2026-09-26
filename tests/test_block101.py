"""BLOQUE 101 - unit tests for local LoRA fine-tuning & on-device neural optimization."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.ai.fine_tuning import (
    DEFAULT_MAX_RAM_MB,
    DEFAULT_MAX_VRAM_MB,
    HardwareBudget,
    LoraAdapterManager,
    LoraDatasetSynthesizer,
    get_engine,
    reset_engine,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_engine()
    yield
    reset_engine()


def _entries(n: int = 20) -> list:
    return [
        {
            "text": f"pregunta cognitiva numero {i} sobre AURA",
            "output": f"respuesta validada numero {i}",
            "source": "cognitive_graph",
        }
        for i in range(n)
    ]


# ------------------------------------------------------ dataset synthesizer ---


def test_synthesizer_dedupes_and_formats():
    s = LoraDatasetSynthesizer()
    samples = s.build_samples(_entries(10) + _entries(10))
    assert len(samples) == 10
    assert all(s_.prompt and s_.completion for s_ in samples)


def test_synthesizer_rejects_invalid_entries():
    s = LoraDatasetSynthesizer()
    samples = s.build_samples(
        [
            {"text": "", "output": "x"},
            {"text": "ok-prompt", "output": "ok-completion"},
            {"text": "ab", "output": "tiny"},
        ]
    )
    assert len(samples) == 1


def test_export_persists_jsonl_with_sha256():
    s = LoraDatasetSynthesizer()
    res = s.export("test_ds", _entries(15))
    assert res["dataset_id"].startswith("ds_")
    assert res["samples"] == 15
    assert len(res["sha256"]) == 64
    loaded = s.load(res["dataset_id"])
    assert len(loaded) == 15 and "prompt" in loaded[0]
    assert s.export("empty", [])["error"] == "no_valid_samples"


def test_list_datasets():
    LoraDatasetSynthesizer().export("a", _entries(5))
    assert len(LoraDatasetSynthesizer().list_datasets()) >= 1


# ---------------------------------------------------- adapter manager LoRA ----


def test_create_and_train_adapter_loss_converges():
    m = LoraAdapterManager()
    ad = m.create_adapter(rank=8)
    tr = m.train_adapter(ad["adapter_id"], steps=60)
    assert tr["trained"] is True
    assert tr["final_loss"] <= 0.6
    assert len(tr["weights_sha256"]) == 64


def test_training_deterministic_same_integrity():
    m = LoraAdapterManager()
    t1 = m.train_adapter(m.create_adapter(rank=8)["adapter_id"], steps=30)
    t2 = m.train_adapter(m.create_adapter(rank=8)["adapter_id"], steps=30)
    assert t1["weights_sha256"] != t2["weights_sha256"]  # ids distintos
    assert t1["final_loss"] == pytest.approx(t2["final_loss"], abs=1e-9)


def test_resource_guard_blocks_oversized_training():
    m = LoraAdapterManager(budget=HardwareBudget(max_ram_mb=100, max_vram_mb=100))
    ad = m.create_adapter(rank=64)
    res = m.train_adapter(ad["adapter_id"], steps=500)
    assert res["trained"] is False and res.get("resource_guard") is True
    assert m.get_adapter(ad["adapter_id"])["status"] == "failed"


def test_defaults_budget_reasonable():
    b = HardwareBudget()
    assert b.max_ram_mb == DEFAULT_MAX_RAM_MB == 4096
    assert b.max_vram_mb == DEFAULT_MAX_VRAM_MB == 6144
    assert b.validate(1000, 2000) == (True, "")


def test_hot_swap_activate_and_rollback():
    m = LoraAdapterManager()
    a1, a2 = m.create_adapter(rank=8), m.create_adapter(rank=8)
    m.train_adapter(a1["adapter_id"], steps=30)
    m.train_adapter(a2["adapter_id"], steps=30)
    r1 = m.activate(a1["adapter_id"])
    assert r1["activated"] is True and r1["previous_adapter"] is None
    assert m.train_adapter(a1["adapter_id"], steps=10)["trained"] is False
    assert m.activate(a2["adapter_id"])["previous_adapter"] == a1["adapter_id"]
    assert m.get_adapter(a1["adapter_id"])["status"] == "trained"
    assert m.rollback(a2["adapter_id"])["rolled_back"] is True
    assert m.status()["active_adapter"] is None


def test_activate_untrained_rejected():
    m = LoraAdapterManager()
    res = m.activate(m.create_adapter(rank=8)["adapter_id"])
    assert res["activated"] is False and "not_trained" in res["error"]


def test_optimize_weights_quantization():
    m = LoraAdapterManager()
    ad = m.create_adapter(rank=8)
    m.train_adapter(ad["adapter_id"], steps=30)
    res = m.optimize_weights(ad["adapter_id"], bits=4)
    assert res["optimized"] is True and res["compression_ratio"] == 0.125
    assert len(res["optimized_sha256"]) == 64
    ad2 = m.create_adapter(rank=8)
    assert m.optimize_weights(ad2["adapter_id"])["optimized"] is False


def test_adapter_rank_clamped():
    assert LoraAdapterManager().create_adapter(rank=9999)["rank"] == 256


def test_engine_full_cycle_and_singleton():
    assert get_engine() is get_engine()
    res = get_engine().run_cycle(_entries(12), name="cycle_test", rank=8, steps=40)
    assert res["cycle"] is True and res["dataset"]["samples"] == 12


# ------------------------------------------------------------ REST / WS ------


def _client() -> TestClient:
    app = FastAPI()
    from backend.ai.routes import router

    app.include_router(router)
    return TestClient(app)


def test_rest_full_flow():
    c = _client()
    ds = c.post(
        "/api/ai/finetune-lora/dataset/synthesize", json={"name": "e2e", "entries": _entries(10)}
    ).json()
    assert ds["samples"] == 10
    ad = c.post(
        "/api/ai/finetune-lora/adapter/create", json={"rank": 8, "dataset_id": ds["dataset_id"]}
    ).json()
    tr = c.post(
        f"/api/ai/finetune-lora/adapter/{ad['adapter_id']}/train", json={"steps": 40}
    ).json()
    assert tr["trained"] is True
    act = c.post(f"/api/ai/finetune-lora/adapter/{ad['adapter_id']}/activate").json()
    assert act["activated"] is True
    st = c.get("/api/ai/finetune-lora/status").json()
    assert st["adapters"]["active_adapter"] == ad["adapter_id"]
    assert c.post("/api/ai/finetune-lora/reset").json()["reset"] is True


def test_rest_validation_errors():
    c = _client()
    assert (
        c.post("/api/ai/finetune-lora/dataset/synthesize", json={"entries": []}).status_code == 422
    )
    assert (
        c.post("/api/ai/finetune-lora/adapter/unknown/train", json={"steps": 10}).status_code == 400
    )
    assert c.get("/api/ai/finetune-lora/adapter/unknown").status_code == 404
    assert c.post("/api/ai/finetune-lora/adapter/create", json={"rank": 0}).status_code == 422


def test_rest_cycle_endpoint():
    c = _client()
    res = c.post(
        "/api/ai/finetune-lora/cycle", json={"name": "rest_cycle", "entries": _entries(8)}
    ).json()
    assert res["cycle"] is True


def test_ws_finetune_heartbeat():
    c = _client()
    with c.websocket_connect("/api/ai/finetune-lora/ws") as ws:
        msg = ws.receive_json()
    assert msg["event"] == "finetune_heartbeat"
    assert msg["offline_only"] is True
    assert "adapters" in msg["status"]
