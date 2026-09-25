import json
import os
from typing import Any, Dict, Optional


class Config:
    _config: Dict[str, Any] = {}

    @classmethod
    def load(cls, path: Optional[str] = None) -> None:
        config_path = path or os.path.join(os.path.dirname(__file__), "..", "..", "config.json")
        defaults = {
            "server": {"host": "127.0.0.1", "port": 8000},
            "ai": {"provider": "local", "model": "dolphin-2_6-phi-2", "timeout": 30},
            "memory": {"short_term_size": 10, "long_term_db": "aria_long.db"},
            "connectors": {
                "notion": {"enabled": False},
                "slack": {"enabled": False},
                "google": {"enabled": False},
                "discord": {"enabled": False},
                "twitter": {"enabled": False},
                "supabase": {"enabled": False},
                "stripe": {"enabled": False},
                "stable_diffusion": {"enabled": False},
                "github": {"enabled": False},
                "huggingface": {"enabled": False},
            },
            "resilience": {"circuit_breaker_threshold": 5, "circuit_timeout": 30, "max_retries": 5},
            "observability": {"metrics_enabled": True, "logging_level": "INFO"},
        }
        if os.path.exists(config_path):
            try:
                with open(config_path, "r") as f:
                    loaded = json.load(f)
                    cls._config = {**defaults, **loaded}
                    return
            except Exception:
                pass
        cls._config = defaults

    @classmethod
    def get(cls, key: str, default: Any = None) -> Any:
        if not cls._config:
            cls.load()
        keys = key.split(".")
        val = cls._config
        for k in keys:
            if isinstance(val, dict) and k in val:
                val = val[k]
            else:
                return default
        return val

    @classmethod
    def set(cls, key: str, value: Any) -> None:
        if not cls._config:
            cls.load()
        keys = key.split(".")
        d = cls._config
        for k in keys[:-1]:
            d = d.setdefault(k, {})
        d[keys[-1]] = value

    @classmethod
    def require(cls, key: str) -> Any:
        val = cls.get(key)
        if val is None:
            raise ValueError(f"Required config missing: {key}")
        return val
