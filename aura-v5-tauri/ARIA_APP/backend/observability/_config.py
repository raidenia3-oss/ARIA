import os

_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config.json")

try:
    with open(_CONFIG_PATH, "r") as f:
        _raw = json.load(f)
except Exception:
    _raw = {}

SERVER_HOST = _raw.get("server", {}).get("host", "127.0.0.1")
SERVER_PORT = _raw.get("server", {}).get("port", 8000)
AI_PROVIDER = _raw.get("ai", {}).get("provider", "local")
AI_MODEL = _raw.get("ai", {}).get("model", "dolphin-2_6-phi-2")
AI_TIMEOUT = _raw.get("ai", {}).get("timeout", 30)
DATABASE_PATH = _raw.get("database", {}).get("path", "aria.db")
MEMORY_PATH = _raw.get("memory", {}).get("path", "memory/")
LOG_LEVEL = _raw.get("observability", {}).get("logging_level", "INFO")
METRICS_ENABLED = _raw.get("observability", {}).get("metrics_enabled", True)
CIRCUIT_BREAKER_THRESHOLD = _raw.get("resilience", {}).get("circuit_breaker_threshold", 5)
CIRCUIT_TIMEOUT = _raw.get("resilience", {}).get("circuit_timeout", 30)
MAX_RETRIES = _raw.get("resilience", {}).get("max_retries", 5)
CONNECTORS = _raw.get("connectors", {})

try:
    import json
except ImportError:
    pass
