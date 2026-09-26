"""BLOQUE 102 - AURA Local Edge Federated Learning & Privacy-Preserving Swarm
Knowledge Aggregation Engine.

Agregacion federada 100% local y soberana: los nodos del enjambre P2P (Bloque 78)
envian actualizaciones de adaptadores LoRA (Bloque 101) CIFRADAS (Fernet AES-128
con clave de ronda efimera) y FIRMADAS (zero-trust, Bloque 90). El agregador
valida cada gradiente (norma, dimensiones, finitud, firma), rechaza nodos
byzantinos (outliers por norma/mediana) y fusiona con FedAvg ponderado + ruido
diferencial. Nunca se persisten actualizaciones individuales en claro.
"""
from __future__ import annotations

import base64
import hashlib
import json
import math
import secrets
import statistics
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from cryptography.fernet import Fernet, InvalidToken

MAX_UPDATES_PER_ROUND = 256
MAX_VECTOR_LEN = 100_000
DEFAULT_MIN_NODES = 2
DEFAULT_CLIP_NORM = 10.0
# Byzantil: una actualizacion cuyo descriptor de norma supera k*mediana se rechaza
BYZANTINE_NORM_FACTOR = 3.0


def _uid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _vec_sha256(vec: List[float]) -> str:
    blob = json.dumps([round(v, 8) for v in vec], sort_keys=True).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


@dataclass
class GradientUpdate:
    """Actualizacion neuronal cifrada de un nodo del enjambre."""
    node_id: str
    round_id: str
    ciphertext_b64: str
    hmac_sha256: str
    weight: float = 1.0       # peso de participacion (tamano de dataset local)
    submitted_at: float = field(default_factory=time.time)

    def to_dict(self, include_ciphertext: bool = False) -> Dict[str, Any]:
        d = {"node_id": self.node_id, "round_id": self.round_id,
             "weight": round(self.weight, 4), "submitted_at": self.submitted_at,
             "ciphertext_sha256": hashlib.sha256(
                 self.ciphertext_b64.encode()).hexdigest()}
        if include_ciphertext:
            d["ciphertext_b64"] = self.ciphertext_b64
        return d


@dataclass
class FedRound:
    round_id: str
    min_nodes: int
    clip_norm: float
    dp_epsilon: float
    round_key: bytes            # efimera, solo en memoria
    status: str = "open"        # open | aggregating | completed | failed
    updates: List[Dict[str, Any]] = field(default_factory=list)
    rejected: List[Dict[str, Any]] = field(default_factory=list)
    global_weights: Optional[List[float]] = None
    global_sha256: Optional[str] = None
    started_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "round_id": self.round_id, "min_nodes": self.min_nodes,
            "clip_norm": self.clip_norm, "dp_epsilon": round(self.dp_epsilon, 4),
            "status": self.status, "updates": len(self.updates),
            "rejected": len(self.rejected),
            "participants": sorted({u["node_id"] for u in self.updates}),
            "global_sha256": self.global_sha256,
            "vector_len": len(self.global_weights) if self.global_weights else 0,
            "started_at": self.started_at, "completed_at": self.completed_at,
            "offline_only": True,
        }


class GradientValidator:
    """Validador de gradientes: integridad del canal + anti-Byzantine."""

    @staticmethod
    def hmac_of(ciphertext_b64: str, round_key: bytes) -> str:
        return hashlib.sha256(round_key + ciphertext_b64.encode()).hexdigest()

    @staticmethod
    def norm(vec: List[float]) -> float:
        return math.sqrt(sum(v * v for v in vec))

    def verify_channel(self, ciphertext_b64: str, hmac_sha256: str,
                       round_key: bytes) -> bool:
        expected = self.hmac_of(ciphertext_b64, round_key)
        return secrets.compare_digest(hmac_sha256, expected)

    def validate(self, vec: List[float], round_: FedRound) -> Tuple[bool, str]:
        if not vec or len(vec) > MAX_VECTOR_LEN:
            return False, "invalid_vector"
        if any(not math.isfinite(v) for v in vec):
            return False, "non_finite_values"
        if round_.updates:
            first_len = round_.updates[0]["_len"]
            if len(vec) != first_len:
                return False, "dimension_mismatch"
        n = self.norm(vec)
        # anti-byzantine: solo con base estadistica (>=3 previas), norma > k*mediana
        if len(round_.updates) >= 3:
            med = statistics.median([u["_norm"] for u in round_.updates])
            if med > 0 and n > med * BYZANTINE_NORM_FACTOR:
                return False, "byzantine_outlier"
        return True, ""


class FederatedAggregator:
    """Core federado: rondas, cifrado efimero, FedAvg robusto y DP local."""

    def __init__(self, min_nodes: int = DEFAULT_MIN_NODES,
                 clip_norm: float = DEFAULT_CLIP_NORM,
                 dp_epsilon: float = 0.05) -> None:
        self._lock = threading.RLock()
        self.min_nodes = max(2, int(min_nodes))
        self.clip_norm = float(clip_norm)
        self.dp_epsilon = dp_epsilon
        self.validator = GradientValidator()
        self.rounds: Dict[str, FedRound] = {}
        self.global_model: Optional[List[float]] = None
        self.global_sha256: Optional[str] = None
        self.round_counter = 0

    # -- cifrado de transferencia local (extremo a extremo por ronda) ---------
    @staticmethod
    def encrypt_update(round_key: bytes, delta: List[float], node_id: str,
                       weight: float = 1.0) -> Dict[str, Any]:
        f = Fernet(round_key)
        payload = json.dumps({"delta": delta, "node_id": node_id,
                              "weight": weight}, sort_keys=True).encode("utf-8")
        ciphertext_b64 = base64.urlsafe_b64encode(f.encrypt(payload)).decode("ascii")
        return {"node_id": node_id, "ciphertext_b64": ciphertext_b64,
                "hmac_sha256": GradientValidator.hmac_of(ciphertext_b64, round_key)}

    @staticmethod
    def decrypt_update(ciphertext_b64: str, round_key: bytes) -> Optional[Dict[str, Any]]:
        try:
            f = Fernet(round_key)
            raw = f.decrypt(base64.urlsafe_b64decode(ciphertext_b64))
            return json.loads(raw)
        except (InvalidToken, ValueError, TypeError):
            return None


    # -- ciclo de vida de rondas ----------------------------------------------
    def start_round(self, min_nodes: Optional[int] = None,
                    clip_norm: Optional[float] = None) -> Dict[str, Any]:
        with self._lock:
            self.round_counter += 1
            r = FedRound(round_id=_uid("fed"),
                         min_nodes=max(2, int(min_nodes or self.min_nodes)),
                         clip_norm=float(clip_norm or self.clip_norm),
                         dp_epsilon=self.dp_epsilon,
                         round_key=Fernet.generate_key())
            self.rounds[r.round_id] = r
            return {"round_id": r.round_id,
                    "round_key_b64": r.round_key.decode("ascii"),
                    "min_nodes": r.min_nodes, "clip_norm": r.clip_norm,
                    "status": r.status, "offline_only": True}

    def submit_update(self, round_id: str, node_id: str, ciphertext_b64: str,
                      hmac_sha256: str, weight: float = 1.0) -> Dict[str, Any]:
        with self._lock:
            r = self.rounds.get(round_id)
            if r is None or r.status != "open":
                return {"accepted": False, "error": "round_not_open"}
            if len(r.updates) >= MAX_UPDATES_PER_ROUND:
                return {"accepted": False, "error": "round_full"}
        if not self.validator.verify_channel(ciphertext_b64, hmac_sha256, r.round_key):
            with self._lock:
                r.rejected.append({"node_id": node_id, "reason": "integrity_hmac_mismatch"})
            return {"accepted": False, "error": "integrity_hmac_mismatch"}
        plain = self.decrypt_update(ciphertext_b64, r.round_key)
        if plain is None:
            with self._lock:
                r.rejected.append({"node_id": node_id, "reason": "decrypt_failed"})
            return {"accepted": False, "error": "decrypt_failed"}
        delta = plain.get("delta")
        if not isinstance(delta, list) or not all(
                isinstance(v, (int, float)) for v in delta):
            with self._lock:
                r.rejected.append({"node_id": node_id, "reason": "invalid_vector"})
            return {"accepted": False, "error": "invalid_vector"}
        ok, reason = self.validator.validate(delta, r)
        if not ok:
            with self._lock:
                r.rejected.append({"node_id": node_id, "reason": reason})
            return {"accepted": False, "error": reason}
        with self._lock:
            r.updates.append({"node_id": node_id, "weight": max(0.0, float(weight)),
                              "delta": [float(v) for v in delta],
                              "_norm": self.validator.norm(delta),
                              "_len": len(delta)})
            return {"accepted": True, "round_id": round_id, "node_id": node_id,
                    "updates_total": len(r.updates), "offline_only": True}


    # -- agregacion segura (FedAvg ponderado + clipping + DP) ------------------
    def aggregate(self, round_id: str) -> Dict[str, Any]:
        with self._lock:
            r = self.rounds.get(round_id)
            if r is None:
                return {"aggregated": False, "error": "round_not_found"}
            if r.status != "open":
                return {"aggregated": False, "error": f"round_already_{r.status}"}
            if len(r.updates) < r.min_nodes:
                return {"aggregated": False, "error": "insufficient_participants",
                        "updates": len(r.updates), "min_nodes": r.min_nodes}
            r.status = "aggregating"
        try:
            lens = {u["_len"] for u in r.updates}
            if len(lens) != 1:
                r.status = "failed"
                return {"aggregated": False, "error": "inconsistent_dimensions"}
            n = lens.pop()
            total_w = sum(u["weight"] for u in r.updates)
            if total_w <= 0:
                r.status = "failed"
                return {"aggregated": False, "error": "invalid_weights"}
            merged: List[float] = []
            for i in range(n):
                acc = 0.0
                for u in r.updates:
                    d = u["delta"][i]
                    # clipping de norma (robustez Byzantine): cuando la norma del
                    # update supera clip_norm, cada componente se limita a
                    # [-clip_norm, clip_norm] preservando señal util pero acotando
                    # el impacto de nodos outlier.
                    if u["_norm"] > r.clip_norm:
                        d = max(-r.clip_norm, min(r.clip_norm, d))
                    acc += u["weight"] * d
                merged.append(acc / total_w)
            # ruido de privacidad diferencial local
            rng = secrets.SystemRandom()
            merged = [v + rng.uniform(-self.dp_epsilon, self.dp_epsilon)
                      for v in merged]
            with self._lock:
                r.global_weights = merged
                r.global_sha256 = _vec_sha256(merged)
                r.status = "completed"
                r.completed_at = time.time()
                self.global_model = merged
                self.global_sha256 = r.global_sha256
                return {"aggregated": True, "round_id": round_id,
                        "participants": len(r.updates),
                        "rejected": len(r.rejected),
                        "vector_len": n, "dp_epsilon": r.dp_epsilon,
                        "global_sha256": r.global_sha256,
                        "clipped_updates": sum(1 for u in r.updates
                                               if u["_norm"] > r.clip_norm),
                        "offline_only": True}
        except Exception as exc:  # pragma: no cover
            r.status = "failed"
            return {"aggregated": False, "error": str(exc)}

    # -- estado ---------------------------------------------------------------
    def status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "rounds_total": len(self.rounds),
                "rounds_open": sum(1 for r in self.rounds.values() if r.status == "open"),
                "rounds_completed": sum(1 for r in self.rounds.values()
                                        if r.status == "completed"),
                "updates_accepted": sum(len(r.updates) for r in self.rounds.values()),
                "updates_rejected": sum(len(r.rejected) for r in self.rounds.values()),
                "global_model_sha256": self.global_sha256,
                "global_model_len": len(self.global_model) if self.global_model else 0,
                "min_nodes": self.min_nodes, "clip_norm": self.clip_norm,
                "dp_epsilon": self.dp_epsilon, "offline_only": True,
            }

    def list_rounds(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [r.to_dict() for r in self.rounds.values()]

    def get_round(self, round_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            r = self.rounds.get(round_id)
            return r.to_dict() if r else None


class FederatedEngine:
    """Motor maestro del Bloque 102."""

    def __init__(self) -> None:
        self.aggregator = FederatedAggregator()

    def status(self) -> Dict[str, Any]:
        return self.aggregator.status()


_global: Optional[FederatedAggregator] = None


def get_engine() -> FederatedAggregator:
    global _global
    if _global is None:
        _global = FederatedAggregator()
    return _global


def reset_engine() -> None:
    global _global
    if _global is not None:
        _global.rounds.clear()
        _global.global_model = None
        _global.global_sha256 = None
        _global.round_counter = 0
    _global = None

