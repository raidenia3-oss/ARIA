"""Discord diagnostics endpoint for AURA — checks Discord bot connectivity without exposing secrets."""

from __future__ import annotations

import os
import socket
import subprocess
import time
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List
from urllib.parse import urlparse

import logging

logger = logging.getLogger("AURADiscordDiag")


VALIDATION_CONFIGURED = "configured"
VALIDATION_ABSENT = "absent"
VALIDATION_INVALID = "invalid"
VALIDATION_UNCHECKED = "unchecked"


@dataclass
class DiscordDiagResult:
    token_validation: str
    token_masked: str
    client_id_validation: str
    backend_available: bool
    backend_url: str
    redis_available: bool
    redis_url: str
    bot_process_running: bool
    last_connection: str
    last_error: str = ""
    configuration_source: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "token_validation": self.token_validation,
            "token_masked": self.token_masked,
            "client_id_validation": self.client_id_validation,
            "backend_available": self.backend_available,
            "backend_url": self.backend_url,
            "redis_available": self.redis_available,
            "redis_url": self.redis_url,
            "bot_process_running": self.bot_process_running,
            "last_connection": self.last_connection,
            "last_error": self.last_error,
            "configuration_source": self.configuration_source,
        }


def _mask_token(token: str) -> str:
    if not token or not token.strip():
        return "[ausente]"
    t = token.strip()
    if len(t) <= 8:
        return "****"
    return f"{t[:4]}****{t[-4:]}"


def _validate_token(token: str) -> str:
    """Validate Discord token presence and basic format without exposing the value."""
    if not token or not token.strip():
        return VALIDATION_ABSENT
    t = token.strip()
    if len(t) < 10:
        return VALIDATION_INVALID
    parts = t.split(".")
    if len(parts) != 3 or not parts[0] or not parts[1] or not parts[2]:
        return VALIDATION_INVALID
    return VALIDATION_CONFIGURED


def _check_tcp(host: str, port: int, timeout: float = 3.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


def _check_backend(url: str) -> bool:
    """Check backend availability via TCP.

    NOTE: deliberately avoids an HTTP self-request. When diagnostics run
    inside the backend itself, a blocking HTTP call to our own endpoint
    would deadlock the event loop and always report the backend down.
    A TCP connect is completed by the OS backlog and is safe.
    """
    try:
        parsed = urlparse(url)
        host = parsed.hostname or "localhost"
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        return _check_tcp(host, port)
    except Exception:
        return False


def _check_discord_process() -> bool:
    """Detect the Discord bot ruby process by its command line (bot.rb)."""
    found = False
    try:
        result = subprocess.run(
            ["wmic", "process", "where", "name='ruby.exe'", "get", "commandline"],
            capture_output=True, text=True, timeout=10
        )
        found = "bot.rb" in (result.stdout or "").lower()
    except Exception:
        found = False
    if found:
        return True
    # Fallback: any ruby.exe running (cannot inspect command line or wmic absent).
    try:
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq ruby.exe"],
            capture_output=True, text=True, timeout=5
        )
        return "ruby.exe" in result.stdout
    except Exception:
        return False


def _get_config_source() -> str:
    """Determine which env file provided the Discord configuration."""
    import dotenv
    sources = [
        os.path.join(os.path.dirname(__file__), "..", "services", "discord-bot", ".env"),
    ]
    for src in sources:
        src = os.path.normpath(src)
        if os.path.isfile(src):
            vals = dotenv.dotenv_values(src)
            if vals.get("DISCORD_BOT_TOKEN"):
                return src
    return "unknown"


def _get_last_connection() -> str:
    """Reads last connection timestamp from data file if available."""
    last_conn_file = os.path.join(os.path.dirname(__file__), "..", "data", "discord_last_connection.txt")
    last_conn_file = os.path.normpath(last_conn_file)
    try:
        with open(last_conn_file, "r") as f:
            return f.read().strip()
    except Exception:
        return "never"


def _sanitize_url(url: str) -> str:
    """Strip credentials (user:password) from a URL before exposing it."""
    try:
        parsed = urlparse(url)
        if parsed.password is None and parsed.username is None:
            return url
        netloc = parsed.hostname or ""
        if parsed.port:
            netloc = f"{netloc}:{parsed.port}"
        return parsed._replace(netloc=netloc).geturl()
    except Exception:
        return "[url]"


def run_diagnostics() -> Dict[str, Any]:
    token = os.getenv("DISCORD_BOT_TOKEN", "")
    client_id = os.getenv("DISCORD_CLIENT_ID", "")
    backend_url = os.getenv("AURA_BACKEND_URL", "http://localhost:8000")
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    token_validation = _validate_token(token)
    client_id_validation = VALIDATION_CONFIGURED if client_id and client_id.strip() else VALIDATION_ABSENT

    backend_ok = _check_backend(backend_url)
    redis_parsed: str = ""
    redis_ok = False
    try:
        parsed = urlparse(redis_url)
        redis_parsed = f"{parsed.hostname}:{parsed.port or 6379}"
        redis_ok = _check_tcp(parsed.hostname or "localhost", parsed.port or 6379)
    except Exception:
        redis_parsed = redis_url
        redis_ok = False

    process_running = _check_discord_process()
    config_source = _get_config_source()
    last_connection = _get_last_connection()

    errors: List[str] = []
    if token_validation == VALIDATION_ABSENT:
        errors.append("DISCORD_BOT_TOKEN no está configurado")
    elif token_validation == VALIDATION_INVALID:
        errors.append("DISCORD_BOT_TOKEN presente pero con formato inválido")
    if client_id_validation == VALIDATION_ABSENT:
        errors.append("DISCORD_CLIENT_ID no está configurado")
    if not backend_ok:
        errors.append(f"Backend no disponible en {backend_url}")
    if not redis_ok:
        errors.append(f"Redis no disponible en {redis_parsed}")
    if not process_running:
        errors.append("Proceso de bot de Discord no detectado (ruby.exe)")

    if token_validation == VALIDATION_ABSENT and client_id_validation == VALIDATION_ABSENT:
        status = "not_configured"
    elif token_validation == VALIDATION_INVALID:
        status = "error"
    elif errors:
        status = "degraded"
    elif process_running and backend_ok and redis_ok and token_validation == VALIDATION_CONFIGURED:
        status = "healthy"
    elif not process_running and backend_ok and token_validation == VALIDATION_CONFIGURED:
        status = "offline"
    else:
        status = "degraded"

    result = DiscordDiagResult(
        token_validation=token_validation,
        token_masked=_mask_token(token) if token else "[ausente]",
        client_id_validation=client_id_validation,
        backend_available=backend_ok,
        backend_url=backend_url,
        redis_available=redis_ok,
        redis_url=_sanitize_url(redis_url),
        bot_process_running=process_running,
        last_connection=last_connection,
        last_error="; ".join(errors) if errors else "",
        configuration_source=config_source,
    )

    payload = result.to_dict()
    payload["token_configured"] = token_validation == VALIDATION_CONFIGURED
    payload["status"] = status
    # Bot wrapper retries every 5s while running; no retry scheduled when stopped.
    payload["next_retry"] = "5s" if process_running else "n/a"

    return {
        "status": status,
        "checks": payload,
    }


discord_diag_cache: Dict[str, Any] = {}
_discord_diag_interval = 30


def get_cached_diagnostics() -> Dict[str, Any]:
    now = time.time()
    if discord_diag_cache.get("expires", 0) > now:
        return discord_diag_cache.get("data", {})
    result = run_diagnostics()
    discord_diag_cache["data"] = result
    discord_diag_cache["expires"] = now + _discord_diag_interval
    discord_diag_cache["checked_at"] = now
    return result


def record_successful_connection() -> None:
    """Record that the Discord bot successfully connected."""
    conn_file = os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "data", "discord_last_connection.txt")
    )
    os.makedirs(os.path.dirname(conn_file), exist_ok=True)
    with open(conn_file, "w") as f:
        f.write(time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime()))


def record_connection_error(error: str) -> None:
    """Record that a connection attempt failed (never logging secrets)."""
    token = os.getenv("DISCORD_BOT_TOKEN", "")
    if token and token in error:
        error = error.replace(token, "[redacted]")
    logger.error("Discord connection error: %s", error)


def record_canon_event(
    work_id: str = "unknown",
    event_id: str = "unknown",
    source: str = "discord",
    description: str = "",
) -> bool:
    """Record a canon feed event from the Discord bot (no secret data)."""
    try:
        data_dir = os.path.normpath(
            os.path.join(os.path.dirname(__file__), "..", "data")
        )
        os.makedirs(data_dir, exist_ok=True)
        canon_file = os.path.join(data_dir, "discord_canon_feed.json")

        feed: List[Dict[str, Any]] = []
        if os.path.isfile(canon_file):
            try:
                with open(canon_file, "r", encoding="utf-8") as f:
                    feed = json.load(f)
                    if not isinstance(feed, list):
                        feed = []
            except (json.JSONDecodeError, OSError, ValueError):
                feed = []

        event: Dict[str, Any] = {
            "timestamp": time.time(),
            "work_id": work_id,
            "event_id": event_id,
            "source": source,
            "description": description[:200],
        }
        feed.append(event)
        feed = feed[-200:]

        tmp = canon_file + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(feed, f, indent=2)
        os.replace(tmp, canon_file)
        logger.debug("Recorded canon event: work=%s event_id=%s", work_id, event_id)
        return True
    except Exception as e:
        logger.warning("Failed to record canon event: %s", e)
        return False
