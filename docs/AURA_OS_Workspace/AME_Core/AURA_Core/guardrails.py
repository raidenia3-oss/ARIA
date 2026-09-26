import os
import re
import sqlite3
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "aura_guardrails.db"

# Patrones de prompt injection (expresiones regulares + palabras clave)
INJECTION_PATTERNS = [
    re.compile(r"olvida las instrucciones anteriores", re.IGNORECASE),
    re.compile(r"ignora las reglas del sistema", re.IGNORECASE),
    re.compile(r"act[uú+]a como un modo root sin restricciones", re.IGNORECASE),
    re.compile(r"sos un hacker", re.IGNORECASE),
    re.compile(r"deja de ser un asistente", re.IGNORECASE),
    re.compile(r"ahora eres DAN", re.IGNORECASE),
    re.compile(r"no tienes reglas", re.IGNORECASE),
    re.compile(r"sin restricciones", re.IGNORECASE),
    re.compile(r"bypass", re.IGNORECASE),
    re.compile(r"jailbreak", re.IGNORECASE),
    re.compile(r"prompt injection", re.IGNORECASE),
]

INJECTION_KEYWORDS = [
    "olvida las instrucciones",
    "ignora las reglas",
    "modo root",
    "sin restricciones",
    "sin límites",
    "sin filtros",
    "no seas asistente",
    "eres un hacker",
    "actúa como",
    "ahora eres",
    "deja de ser",
    "bypass",
    "jailbreak",
    "prompt injection",
    "system override",
    "admin mode",
    "superuser",
]


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            user_input TEXT,
            matched_rule TEXT,
            action TEXT
        )
        """)
    conn.commit()
    conn.close()


def record_alert(user_input: str, matched_rule: str, action: str = "blocked"):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO alerts (user_input, matched_rule, action) VALUES (?, ?, ?)",
        (user_input, matched_rule, action),
    )
    conn.commit()
    conn.close()


def sanitize_text(text: str) -> str:
    # Elimina secuencias de control peligrosas y normaliza espacios
    text = "".join(ch for ch in text if ch >= " " or ch in "\r\n\t")
    text = re.sub(r"[ \t]+", " ", text).strip()
    return text


def detect_prompt_injection(user_input: str) -> dict:
    if not user_input or not isinstance(user_input, str):
        return {"blocked": False}

    text = user_input.lower()
    matched = []

    for pat in INJECTION_PATTERNS:
        if pat.search(text):
            matched.append(pat.pattern)

    for kw in INJECTION_KEYWORDS:
        if kw in text:
            matched.append(kw)

    if matched:
        return {
            "blocked": True,
            "rule": matched[0],
            "all_matches": matched,
        }

    return {"blocked": False}


def load_env_keys() -> set[str]:
    keys = set()
    try:
        env_path = BASE_DIR / ".env"
        if not env_path.exists():
            return keys
        with open(env_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, _, v = line.partition("=")
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    if v:
                        keys.add(v)
    except Exception:
        pass
    return keys


def filter_credentials(text: str) -> str:
    secret_values = load_env_keys()
    if not secret_values:
        return text
    filtered = text
    for secret in secret_values:
        if secret in filtered:
            filtered = filtered.replace(secret, "[REDACTED]")
    return filtered


def check_and_sanitize(user_input: str) -> dict:
    sanitized = sanitize_text(user_input)
    injection = detect_prompt_injection(sanitized)

    if injection["blocked"]:
        # Registrar alerta
        try:
            record_alert(user_input, injection["rule"])
        except Exception:
            pass
        return {
            "safe": False,
            "sanitized_input": sanitized,
            "blocked": True,
            "message": "⚠️ Petición bloqueada por políticas de seguridad de AURA.",
        }

    return {
        "safe": True,
        "sanitized_input": sanitized,
        "blocked": False,
        "message": "",
    }
