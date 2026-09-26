#!/usr/bin/env python3
"""
memory_brain.py - Memoria Global y Skills
Base de datos de contexto persistente para todos los modelos de IA.
"""

import os
import json
import time
import logging
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class MemoryBrain:
    """Cerebro de memoria persistente para AURA/AME."""

    def __init__(self):
        self.memory_path = os.getenv("AURA_MEMORY_PATH", "memory_brain.json")
        self._data: Dict = {
            "user": {
                "name": "",
                "preferences": {
                    "format": "structured",
                    "response_style": "precise",
                    "language": "es",
                },
                "system_injections": [],
            },
            "context": [],
            "skills": [],
            "stats": {
                "total_queries": 0,
                "providers_used": {},
                "last_updated": datetime.now().isoformat(),
            },
        }
        self._load()

    def _load(self):
        try:
            if os.path.exists(self.memory_path):
                with open(self.memory_path, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    self._data.update(saved)
                logger.info(f"[Memory] Cargada desde {self.memory_path}")
        except Exception as e:
            logger.error(f"[Memory] Error cargando: {e}")

    def _save(self):
        try:
            self._data["stats"]["last_updated"] = datetime.now().isoformat()
            with open(self.memory_path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
            logger.debug(f"[Memory] Guardada en {self.memory_path}")
        except Exception as e:
            logger.error(f"[Memory] Error guardando: {e}")

    def get_user_name(self) -> str:
        return self._data.get("user", {}).get("name", "")

    def set_user_name(self, name: str):
        self._data["user"]["name"] = name
        self._save()

    def get_preferences(self) -> Dict:
        return self._data.get("user", {}).get("preferences", {})

    def update_preferences(self, prefs: Dict):
        self._data["user"]["preferences"].update(prefs)
        self._save()

    def add_system_injection(self, text: str):
        self._data["user"]["system_injections"].append(text)
        self._save()

    def add_context(self, role: str, content: str):
        entry = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
        }
        self._data["context"].append(entry)
        if len(self._data["context"]) > 200:
            self._data["context"] = self._data["context"][-200:]
        self._save()

    def get_context(self, limit: int = 50) -> List[Dict]:
        return self._data.get("context", [])[-limit:]

    def clear_context(self):
        self._data["context"] = []
        self._save()

    def record_query(self, provider: str):
        self._data["stats"]["total_queries"] += 1
        providers = self._data["stats"]["providers_used"]
        providers[provider] = providers.get(provider, 0) + 1
        self._save()

    def get_stats(self) -> Dict:
        return self._data.get("stats", {})

    def export_context_for_prompt(self) -> str:
        lines = [
            "=== MEMORIA GLOBAL AURA ===",
            f"Usuario: {self.get_user_name()}",
            f"Preferencias: {json.dumps(self.get_preferences(), ensure_ascii=False)}",
            "Inyecciones de sistema:",
        ]
        for inj in self._data["user"]["system_injections"]:
            lines.append(f"- {inj}")
        lines.append("Contexto reciente:")
        for c in self.get_context(10):
            lines.append(f"[{c['role']}] {c['content'][:120]}")
        return "\n".join(lines)


# Instancia global
_memory = MemoryBrain()


def get_memory_brain() -> MemoryBrain:
    return _memory
