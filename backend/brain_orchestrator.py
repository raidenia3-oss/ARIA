"""
AURA Unified Brain - Orquestador central del sistema de IA distribuido.

Roles:
- PC: modelo potente + modelo ligero/equilibrado
- Servidor externo: modelo chico
- Celular: APIs externas como apoyo/entrenamiento

El cerebro unificado coordina:
- Inferencia distribuida por dispositivo
- Recolección de muestras para fine-tuning continuo
- Mejora incremental de modelos
- Sincronización entre nodos
"""

from __future__ import annotations

import os
import time
import threading
import logging
import json
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

logger = logging.getLogger("AURA.Brain")

BRAIN_STATE_FILE = os.getenv("AURA_BRAIN_STATE_FILE", "./brain_state.json")
TRAINING_DATA_DIR = os.getenv("AURA_TRAINING_DATA_DIR", "./training_data")
MODEL_REGISTRY_FILE = os.getenv("AURA_MODEL_REGISTRY_FILE", "./model_registry.json")

DEVICE_PC = "pc"
DEVICE_SERVER = "server"
DEVICE_MOBILE = "mobile"
DEVICE_UNKNOWN = "unknown"

ROLE_POWERFUL = "powerful"
ROLE_LIGHT = "light"
ROLE_SMALL = "small"
ROLE_EXTERNAL = "external_api"


def _now() -> float:
    return time.time()


def _load_json(path: str, default: Any = None) -> Any:
    if not os.path.exists(path):
        return default if default is not None else {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default if default is not None else {}


def _save_json(path: str, data: Any) -> None:
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as exc:
        logger.error("No se pudo guardar %s: %s", path, exc)


def detect_device_role(user_agent: str = "", source: str = "") -> Dict[str, str]:
    ua = (user_agent or "").lower()
    src = (source or "").lower()

    if "android" in ua or "iphone" in ua or "mobile" in src:
        return {"device": DEVICE_MOBILE, "role": ROLE_EXTERNAL}
    if "godot" in ua or "desktop" in src:
        return {"device": DEVICE_PC, "role": ROLE_LIGHT}
    return {"device": DEVICE_SERVER, "role": ROLE_SMALL}


class UnifiedBrain:
    def __init__(self) -> None:
        self.state = _load_json(BRAIN_STATE_FILE, {
            "version": "1.0.0",
            "total_conversations": 0,
            "total_training_samples": 0,
            "last_training": None,
            "model_versions": {},
            "device_stats": {},
        })
        self.registry = _load_json(MODEL_REGISTRY_FILE, {
            "models": {
                "local-qwen": {"path": os.getenv("AURA_LOCAL_MODEL_PATH", "./models/qwen-0.5b"), "role": ROLE_LIGHT, "device": DEVICE_PC, "version": "1.0.0", "last_updated": _now()},
                "cloud-small": {"path": "/app/models/qwen-0.5b", "role": ROLE_SMALL, "device": DEVICE_SERVER, "version": "1.0.0", "last_updated": _now()},
            }
        })
        os.makedirs(TRAINING_DATA_DIR, exist_ok=True)

    def record_conversation(self, device: str, role: str, prompt: str, response: str, provider: str, feedback: Optional[str] = None) -> None:
        sample = {
            "device": device,
            "role": role,
            "prompt": prompt,
            "response": response,
            "provider": provider,
            "feedback": feedback,
            "timestamp": _now(),
            "date": datetime.utcnow().isoformat() + "Z",
        }
        self.state["total_conversations"] = self.state.get("total_conversations", 0) + 1
        key = f"{device}:{role}"
        self.state.setdefault("device_stats", {})
        self.state["device_stats"][key] = self.state["device_stats"].get(key, 0) + 1

        today = datetime.utcnow().strftime("%Y-%m-%d")
        sample_path = os.path.join(TRAINING_DATA_DIR, f"samples_{today}.jsonl")
        try:
            with open(sample_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(sample, ensure_ascii=False) + "\n")
        except Exception as exc:
            logger.error("No se pudo guardar muestra de entrenamiento: %s", exc)

        _save_json(BRAIN_STATE_FILE, self.state)

    def get_training_dataset(self, days: int = 7, limit: int = 5000) -> List[Dict[str, Any]]:
        samples: List[Dict[str, Any]] = []
        cutoff = _now() - (days * 86400)
        try:
            for filename in sorted(os.listdir(TRAINING_DATA_DIR)):
                if not filename.startswith("samples_") or not filename.endswith(".jsonl"):
                    continue
                filepath = os.path.join(TRAINING_DATA_DIR, filename)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        for line in f:
                            try:
                                sample = json.loads(line)
                                if sample.get("timestamp", 0) >= cutoff:
                                    samples.append(sample)
                            except Exception:
                                continue
                except Exception:
                    continue
        except Exception as exc:
            logger.error("Error leyendo dataset: %s", exc)
        return samples[-limit:]

    def should_retrain(self, min_samples: int = 200, min_days: int = 1) -> bool:
        samples = self.get_training_dataset(days=min_days)
        if len(samples) < min_samples:
            return False
        last_training = self.state.get("last_training")
        if not last_training:
            return True
        try:
            last_dt = datetime.fromisoformat(last_training.replace("Z", "+00:00"))
            return datetime.utcnow().replace(tzinfo=last_dt.tzinfo) - last_dt >= timedelta(days=min_days)
        except Exception:
            return True

    def register_model_update(self, model_id: str, version: str, path: str, role: str, device: str) -> None:
        self.registry.setdefault("models", {})[model_id] = {
            "path": path,
            "role": role,
            "device": device,
            "version": version,
            "last_updated": _now(),
        }
        self.state.setdefault("model_versions", {})[model_id] = version
        _save_json(MODEL_REGISTRY_FILE, self.registry)
        _save_json(BRAIN_STATE_FILE, self.state)

    def get_brain_status(self) -> Dict[str, Any]:
        samples = self.get_training_dataset(days=7)
        stats: Dict[str, Any] = {
            "state": self.state,
            "registry": self.registry,
            "samples_last_7_days": len(samples),
            "should_retrain": self.should_retrain(),
            "devices": list({k.split(":")[0] for k in (self.state.get("device_stats") or {}).keys()}),
            "roles": list({k.split(":")[1] for k in (self.state.get("device_stats") or {}).keys()}),
        }
        return stats

    def learn(self, device: str, role: str, prompt: str, response: str, provider: str, feedback: Optional[str] = None, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        sample = {
            "device": device,
            "role": role,
            "prompt": prompt,
            "response": response,
            "provider": provider,
            "feedback": feedback,
            "extra": extra or {},
            "timestamp": _now(),
            "date": datetime.utcnow().isoformat() + "Z",
        }
        self.state["total_conversations"] = self.state.get("total_conversations", 0) + 1
        key = f"{device}:{role}"
        self.state.setdefault("device_stats", {})
        self.state["device_stats"][key] = self.state["device_stats"].get(key, 0) + 1

        today = datetime.utcnow().strftime("%Y-%m-%d")
        sample_path = os.path.join(TRAINING_DATA_DIR, f"samples_{today}.jsonl")
        try:
            with open(sample_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(sample, ensure_ascii=False) + "\n")
        except Exception as exc:
            logger.error("No se pudo guardar muestra de entrenamiento: %s", exc)

        _save_json(BRAIN_STATE_FILE, self.state)
        return {"status": "learned", "sample": sample}

    def sync_remote_state(self, remote_state: Dict[str, Any]) -> Dict[str, Any]:
        if not remote_state:
            return {"status": "noop"}
        merged_device_stats = dict(self.state.get("device_stats") or {})
        for key, value in (remote_state.get("device_stats") or {}).items():
            merged_device_stats[key] = int(merged_device_stats.get(key, 0)) + int(value)
        self.state["total_conversations"] = int(self.state.get("total_conversations", 0)) + int(remote_state.get("total_conversations", 0))
        self.state["device_stats"] = merged_device_stats
        self.state.setdefault("model_versions", {}).update(remote_state.get("model_versions") or {})
        _save_json(BRAIN_STATE_FILE, self.state)
        return {"status": "synced", "state": self.state}


brain = UnifiedBrain()
