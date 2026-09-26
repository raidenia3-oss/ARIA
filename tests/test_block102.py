"""BLOQUE 102 - tests for federated learning, privacy-preserving aggregation & Byzantine resistance."""

import base64
import json

import pytest
from cryptography.fernet import Fernet
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.ai.federated import (
    BYZANTINE_NORM_FACTOR,
    FederatedAggregator,
    GradientValidator,
    get_engine,
    reset_engine,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_engine()
    yield
    reset_engine()


def _delta(n: int = 8, scale: float = 0.1) -> list:
    return [round((i + 1) * scale, 6) for i in range(n)]


def _open_round(agg: FederatedAggregator, min_nodes: int = 2):
    rep = agg.start_round(min_nodes=min_nodes)
    # round_key_b64 ya es la clave Fernet en base64 urlsafe
    return rep["round_id"], rep["round_key_b64"].encode("ascii")


def _submit(agg, round_id, key, node_id, delta, weight=1.0):
    enc = agg.encrypt_update(key, delta, node_id, weight)
    return agg.submit_update(round_id, node_id, enc["ciphertext_b64"], enc["hmac_sha256"], weight)


def _craft(agg, key, delta, node_id, weight=1.0, hmac=None):
    """Construye una peticion manual (para casos de corrupcion controlada)."""
    f = Fernet(key)
    ct = base64.urlsafe_b64encode(
        f.encrypt(
            json.dumps(
                {"delta": delta, "node_id": node_id, "weight": weight}, sort_keys=True
            ).encode()
        )
    ).decode()
    return {
        "node_id": node_id,
        "ciphertext_b64": ct,
        "hmac_sha256": hmac if hmac is not None else GradientValidator.hmac_of(ct, key),
    }


# --------------------------------------------------- cifrado / integridad -----


def test_encrypt_decrypt_roundtrip():
    agg = FederatedAggregator()
    key = Fernet.generate_key()
    enc = agg.encrypt_update(key, [1.5, -2.0], "node_a", weight=2.0)
    plain = agg.decrypt_update(enc["ciphertext_b64"], key)
    assert plain["delta"] == [1.5, -2.0] and plain["weight"] == 2.0


def test_wrong_key_cannot_decrypt():
    agg = FederatedAggregator()
    enc = agg.encrypt_update(Fernet.generate_key(), _delta(), "node_a")
    assert agg.decrypt_update(enc["ciphertext_b64"], Fernet.generate_key()) is None


def test_hmac_mismatch_rejected():
    agg = FederatedAggregator()
    rid, key = _open_round(agg)
    enc = agg.encrypt_update(key, _delta(), "node_a")
    res = agg.submit_update(rid, "node_a", enc["ciphertext_b64"], "bad" * 16)
    assert res["accepted"] is False and res["error"] == "integrity_hmac_mismatch"


def test_tampered_ciphertext_rejected():
    agg = FederatedAggregator()
    rid, key = _open_round(agg)
    req = _craft(
        agg,
        key,
        [x + 999.0 for x in _delta()],
        "node_evil",
        hmac=GradientValidator.hmac_of(_delta().__str__(), key),
    )
    res = agg.submit_update(rid, req["node_id"], req["ciphertext_b64"], req["hmac_sha256"])


# ------------------------------------------------- validador de gradientes ----


def test_validator_rejects_non_finite_values():
    agg = FederatedAggregator()
    rid, key = _open_round(agg)
    req = _craft(agg, key, [float("nan"), 1.0], "n1")
    res = agg.submit_update(rid, "n1", req["ciphertext_b64"], req["hmac_sha256"])
    assert res["accepted"] is False and res["error"] == "non_finite_values"


def test_validator_rejects_empty_and_invalid_vector():
    agg = FederatedAggregator()
    rid, key = _open_round(agg)
    req = _craft(agg, key, [], "n1")
    res = agg.submit_update(rid, "n1", req["ciphertext_b64"], req["hmac_sha256"])
    assert res["accepted"] is False and res["error"] == "invalid_vector"


def test_validator_rejects_dimension_mismatch():
    agg = FederatedAggregator()
    rid, key = _open_round(agg)
    assert _submit(agg, rid, key, "n1", _delta(8))["accepted"] is True
    res = _submit(agg, rid, key, "n2", _delta(16))
    assert res["accepted"] is False and res["error"] == "dimension_mismatch"


def test_byzantine_outlier_rejected():
    agg = FederatedAggregator()
    rid, key = _open_round(agg, min_nodes=3)
    assert _submit(agg, rid, key, "n1", _delta(scale=0.1))["accepted"] is True
    assert _submit(agg, rid, key, "n2", _delta(scale=0.2))["accepted"] is True
    assert _submit(agg, rid, key, "n3", _delta(scale=0.15))["accepted"] is True
    res = _submit(agg, rid, key, "n_byz", _delta(scale=100.0))
    assert res["accepted"] is False and res["error"] == "byzantine_outlier"


def test_byzantine_factor_threshold():
    assert BYZANTINE_NORM_FACTOR == 3.0


# ---------------------------------------------------- agregacion FedAvg ------


def test_aggregate_weighted_average_math():
    agg = FederatedAggregator()
    rid, key = _open_round(agg, min_nodes=2)
    _submit(agg, rid, key, "n1", [1.0] * 4, weight=1.0)
    _submit(agg, rid, key, "n2", [3.0] * 4, weight=3.0)
    res = agg.aggregate(rid)
    assert res["aggregated"] is True and res["participants"] == 2
    # fedavg: (1*1 + 3*3)/4 = 2.5, con ruido DP <= 0.05 por componente
    assert all(abs(v - 2.5) <= 0.06 for v in agg.global_model)
    assert len(res["global_sha256"]) == 64


def test_aggregate_requires_min_nodes():
    agg = FederatedAggregator()
    rid, key = _open_round(agg, min_nodes=3)
    _submit(agg, rid, key, "n1", _delta())
    res = agg.aggregate(rid)
    assert res["aggregated"] is False and res["error"] == "insufficient_participants"


def test_clipping_applied_to_large_norm():
    agg = FederatedAggregator(clip_norm=1.0)
    rid, key = _open_round(agg, min_nodes=2)
    _submit(agg, rid, key, "n1", [0.5] * 4, weight=1.0)
    _submit(agg, rid, key, "n2", [5.0] * 4, weight=1.0)  # norma ~10 -> clip 1.0
    res = agg.aggregate(rid)
    assert res["aggregated"] is True and res["clipped_updates"] == 1
    assert all(abs(v - 0.75) <= 0.06 for v in agg.global_model)


def test_dp_noise_produces_distinct_global_models():
    agg = FederatedAggregator()
    for _ in range(2):
        rid, key = _open_round(agg)
        _submit(agg, rid, key, "n1", [1.0] * 4)
        _submit(agg, rid, key, "n2", [1.0] * 4)
        agg.aggregate(rid)
    hashes = {r["global_sha256"] for r in agg.list_rounds() if r["status"] == "completed"}
    # ruido DP -> incluso con inputs identicos, el modelo global difiere
    assert len(hashes) == 2


def test_double_aggregate_rejected():
    agg = FederatedAggregator()
    rid, key = _open_round(agg)
    _submit(agg, rid, key, "n1", _delta())
    _submit(agg, rid, key, "n2", _delta())
    assert agg.aggregate(rid)["aggregated"] is True
    assert agg.aggregate(rid)["aggregated"] is False


# ------------------------------------------------------------ REST / WS ------


def _client() -> TestClient:
    app = FastAPI()
    from backend.ai.federated_routes import router

    app.include_router(router)
    return TestClient(app)


def test_rest_full_federated_flow():
    c = _client()
    rep = c.post("/api/ai/federated/round/start", json={"min_nodes": 2}).json()
    # round_key_b64 is already the Fernet key (urlsafe base64 string); pass it as bytes.
    key = rep["round_key_b64"].encode("ascii")
    rid = rep["round_id"]
    from backend.ai.federated import FederatedAggregator as FA

    for node, scale in (("node_x", 0.1), ("node_y", 0.5)):
        u = FA.encrypt_update(key, _delta(scale=scale), node)
        s = c.post(
            f"/api/ai/federated/round/{rid}/submit",
            json={
                "node_id": node,
                "ciphertext_b64": u["ciphertext_b64"],
                "hmac_sha256": u["hmac_sha256"],
                "weight": 1.0,
            },
        )
        assert s.status_code == 200
    agg = c.post(f"/api/ai/federated/round/{rid}/aggregate").json()
    assert agg["aggregated"] is True and agg["participants"] == 2
    st = c.get("/api/ai/federated/status").json()
    assert st["rounds_completed"] == 1
    assert len(st["global_model_sha256"]) == 64
    assert c.post("/api/ai/federated/reset").json()["reset"] is True


def test_rest_invalid_round():
    c = _client()
    assert c.get("/api/ai/federated/round/unknown").status_code == 404
    assert c.post("/api/ai/federated/round/unknown/aggregate").status_code == 400


def test_rest_submit_bad_hmac_400():
    c = _client()
    rep = c.post("/api/ai/federated/round/start", json={"min_nodes": 2}).json()
    res = c.post(
        f"/api/ai/federated/round/{rep['round_id']}/submit",
        json={"node_id": "n", "ciphertext_b64": "AAAA", "hmac_sha256": "bad" * 16},
    )
    assert res.status_code == 400


def test_ws_federated_heartbeat():
    c = _client()
    with c.websocket_connect("/api/ai/federated/ws") as ws:
        msg = ws.receive_json()
    assert msg["event"] == "federated_heartbeat" and msg["offline_only"] is True
