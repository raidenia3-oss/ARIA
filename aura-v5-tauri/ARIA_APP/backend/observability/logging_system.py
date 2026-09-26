import asyncio
import json
import logging
import os
from logging.handlers import RotatingFileHandler
from typing import Any, Dict, Optional


class LoggingSystem:
    def __init__(self, log_dir: str = "", level: str = "INFO") -> None:
        self.log_dir = log_dir or os.path.join(os.path.dirname(__file__), "..", "logs")
        os.makedirs(self.log_dir, exist_ok=True)
        self.level = getattr(logging, level.upper(), logging.INFO)
        self._logger = logging.getLogger("aria")
        self._logger.setLevel(self.level)
        self._setup_handlers()
        self._sensitive_fields = {"password", "token", "secret", "api_key", "key", "credential"}

    def _setup_handlers(self) -> None:
        handler = RotatingFileHandler(
            os.path.join(self.log_dir, "aria.log"), maxBytes=10 * 1024 * 1024, backupCount=5
        )
        handler.setLevel(self.level)
        formatter = logging.Formatter(
            '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "message": %(message)s}'
        )
        handler.setFormatter(formatter)
        self._logger.addHandler(handler)

    def log(self, level: str, message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        extra = extra or {}
        sanitized = self._sanitize(extra)
        msg = json.dumps({"message": message, **sanitized})
        getattr(self._logger, level.lower())(msg)

    def _sanitize(self, data: Dict[str, Any]) -> Dict[str, Any]:
        sanitized = {}
        for k, v in data.items():
            if k.lower() in self._sensitive_fields:
                sanitized[k] = "***REDACTED***"
            elif isinstance(v, dict):
                sanitized[k] = self._sanitize(v)
            else:
                sanitized[k] = v
        return sanitized

    def info(self, message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        self.log("INFO", message, extra)

    def warning(self, message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        self.log("WARNING", message, extra)

    def error(self, message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        self.log("ERROR", message, extra)

    def critical(self, message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        self.log("CRITICAL", message, extra)

    def debug(self, message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        self.log("DEBUG", message, extra)
