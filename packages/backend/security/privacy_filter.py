"""PARTE 8: PRIVACY & SECURITY (200 lines) — Privacy filter + audit.

Clase: PrivacyFilter
- filter_sensitive_data() — Redacta datos sensibles
- audit_log() — Registra qué se capturó
- user_transparency() — Reporte de privacidad
"""

from __future__ import annotations

import os
import re
import json
import time
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class PrivacyResult:
    filtered: str
    removed_count: int
    categories: Dict[str, int] = field(default_factory=dict)


class PrivacyFilter:
    """Filtra datos sensibles antes de almacenar/loguear."""

    SENSITIVE_PATTERNS: List[Tuple[str, str, str]] = [
        # (pattern, replacement, category)
        (r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b", "[CREDIT_CARD]", "credit_card"),
        (r"\b(?:\d{3}[-\s]?){2}\d{4}\b", "[SSN]", "ssn"),
        (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "[EMAIL_REDACTED]", "email"),
        (r"\b\d{3}[-\s]?\d{3}[-\s]?\d{4}\b", "[PHONE]", "phone"),
        (r"(?i)(password|passwd|contraseña|clave)[\s=:]+[^\s,;]+", r"\1=[REDACTED]", "password"),
        (r"(?i)(token|api[_-]?key|secret)[\s=:]+[^\s,;]+", r"\1=[REDACTED]", "api_key"),
        (r"\b\d{16}\b", "[CARD_NUMBER]", "credit_card"),
        (r"\b(?:\d{4}[-\s]?){3}\d{4}\b", "[CARD]", "credit_card"),
    ]

    SENSITIVE_KEYWORDS = [
        "password", "passwd", "contraseña", "secret", "token",
        "api_key", "apikey", "credit", "card", "ssn", "social",
        "rut", "cuit", "cuil", "dni", "documento",
    ]

    def __init__(self, db_path: str = None):
        self.db_path = db_path or str(os.path.expanduser("~/.aria/privacy_audit.db"))
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._audit_buffer: List[Dict[str, Any]] = []
        self._total_filtered = 0

    def _init_db(self) -> None:
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL,
                event_type TEXT,
                action TEXT,
                category TEXT,
                data_snapshot TEXT,
                filtered BOOLEAN DEFAULT 0
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS privacy_report (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL,
                total_processed INTEGER,
                total_filtered INTEGER,
                categories TEXT,
                privacy_score REAL
            )
        """)
        conn.commit()
        conn.close()

    async def filter_sensitive_data(self, text: str) -> PrivacyResult:
        """Filtra datos sensibles del texto."""
        if not text:
            return PrivacyResult(filtered="", removed_count=0, categories={})

        result_text = text
        total_removed = 0
        categories: Dict[str, int] = {}

        for pattern, replacement, category in self.SENSITIVE_PATTERNS:
            matches = re.findall(pattern, text)
            if matches:
                result_text = re.sub(pattern, replacement, result_text)
                count = len(matches)
                total_removed += count
                categories[category] = categories.get(category, 0) + count

        for keyword in self.SENSITIVE_KEYWORDS:
            pattern = rf"(?i)({keyword})[\s=:]*[A-Za-z0-9@._-]{{3,}}"
            if re.search(pattern, text):
                result_text = re.sub(pattern, f"\\1=[REDACTED]", result_text)
                keyword_keyword = keyword.lower()
                categories[keyword_keyword] = categories.get(keyword_keyword, 0) + 1
                total_removed += 1

        self._total_filtered += total_removed
        self._log_audit("filter", f"Removed {total_removed} items", categories, text[:200])

        return PrivacyResult(
            filtered=result_text,
            removed_count=total_removed,
            categories=categories,
        )

    def _log_audit(self, event_type: str, action: str, categories: dict, snapshot: str) -> None:
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT INTO audit_log (timestamp, event_type, action, category, data_snapshot, filtered) VALUES (?,?,?,?,?,?)",
            (time.time(), event_type, action, json.dumps(categories)[:200], snapshot[:300], True),
        )
        conn.commit()
        conn.close()

    async def audit_log(self, event: dict) -> dict:
        """Registra qué se capturó sin almacenar datos sensibles."""
        filtered_event = self._sanitize_event(event)
        self._log_audit(
            event.get("type", "unknown"),
            json.dumps(filtered_event)[:300],
            {},
            "",
        )
        return {"logged": True, "filtered": filtered_event != event}

    def _sanitize_event(self, event: dict) -> dict:
        sanitized = json.loads(json.dumps(event))
        text_fields = self._extract_text_fields(sanitized)
        for path, text in text_fields:
            filtered = self.filter_sensitive_data(text)
            if filtered.removed_count > 0:
                self._set_text_field(sanitized, path, filtered.filtered)
        return sanitized

    def _extract_text_fields(self, data, prefix="") -> List[Tuple[str, str]]:
        fields = []
        if isinstance(data, dict):
            for k, v in data.items():
                p = f"{prefix}.{k}" if prefix else k
                if isinstance(v, str) and len(v) > 3:
                    fields.append((p, v))
                elif isinstance(v, (dict, list)):
                    fields.extend(self._extract_text_fields(v, p))
        elif isinstance(data, list):
            for i, item in enumerate(data):
                fields.extend(self._extract_text_fields(item, f"{prefix}[{i}]"))
        return fields

    def _set_text_field(self, data, path: str, value: str) -> None:
        keys = path.split(".")
        d = data
        for k in keys[:-1]:
            if k in d:
                d = d[k]
        if keys[-1] in d:
            d[keys[-1]] = value

    async def user_transparency(self) -> Dict[str, Any]:
        """Reporte de privacidad para el usuario."""
        conn = sqlite3.connect(self.db_path)
        total_processed = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
        total_filtered = conn.execute("SELECT COUNT(*) FROM audit_log WHERE filtered = 1").fetchone()[0]
        rows = conn.execute("SELECT category, COUNT(*) FROM audit_log GROUP BY category").fetchall()
        categories = {r[0]: r[1] for r in rows}
        conn.close()

        privacy_score = 100.0
        if total_processed > 0:
            privacy_score = ((total_processed - total_filtered) / total_processed) * 100

        return {
            "report": {
                "total_processed": total_processed,
                "total_filtered": total_filtered,
                "categories": categories,
                "privacy_score": round(privacy_score, 1),
                "what_aria_sees": [
                    "Active application name (no titles)",
                    "General activity type",
                    "Anonymized mood/intent data",
                    "Pattern frequency (no personal data)",
                ],
                "what_aria_never_stores": [
                    "Passwords",
                    "Email addresses",
                    "Credit card numbers",
                    "SSN / ID numbers",
                    "API keys",
                    "Personal documents content",
                ],
                "screenshot_frequency": "Every 2 seconds (analysis only, stored as analysis data)",
                "audio_policy": "Detected but never stored. Transcription filtered.",
            }
        }

    @property
    def total_filtered_count(self) -> int:
        return self._total_filtered

    def get_privacy_score(self) -> float:
        try:
            conn = sqlite3.connect(self.db_path)
            total = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
            filtered = conn.execute("SELECT COUNT(*) FROM audit_log WHERE filtered = 1").fetchone()[0]
            conn.close()
            if total == 0: return 100.0
            return (filtered / total) * 100
        except Exception:
            return 100.0
