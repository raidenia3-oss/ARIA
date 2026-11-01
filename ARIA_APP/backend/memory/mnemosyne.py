# -*- coding: utf-8 -*-
"""ARIA OS - Mnemosyne Memory Layer.

Capa ligera, zero-dependency, memoria local rápida para sesiones cortas.
Inspirada en Mnemosyne del video de Wanderloots: memoria operativa que
retiene lo que el usuario dijo en la sesión actual sin depender de LLM.
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("ARIA.Memory.Mnemosyne")


@dataclass
class MnemosyneEntry:
    """Entrada individual de Mnemosyne."""
    entry_id: str
    role: str
    content: str
    timestamp: float = field(default_factory=time.time)
    importance: float = 0.5
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    consolidated: bool = False


class MnemosyneMemory:
    """Memoria local rápida, cero dependencias, persiste en JSON.

    Retiene conversaciones de la sesión actual. Sirve como buffer de
    acceso inmediato para el contexto operativo de ARIA.
    """

    def __init__(self, data_dir: str = "data/memory/mnemosyne", max_entries: int = 200) -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.max_entries = max(1, max_entries)
        self._entries: Dict[str, MnemosyneEntry] = {}
        self._order: List[str] = []
        self._session_id: Optional[str] = None
        self._load()

    # ------------------------------------------------------------------ #
    # Sesión
    # ------------------------------------------------------------------ #
    def set_session(self, session_id: str) -> None:
        """Cambia de sesión. No limpia las entradas, solo marca la sesión activa."""
        self._session_id = session_id
        self._save()
        logger.debug(f"Mnemosyne: Sesión activa -> {session_id}")

    # ------------------------------------------------------------------ #
    # CRUD
    # ------------------------------------------------------------------ #
    def add(
        self,
        role: str,
        content: str,
        importance: float = 0.5,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Agrega una entrada a Mnemosyne. Retorna el entry_id."""
        # El sufijo aleatorio evita colisiones: con el timestamp y el tamaño
        # del dict nada más, dos entradas del mismo milisegundo se pisaban.
        entry_id = f"m_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"
        entry = MnemosyneEntry(
            entry_id=entry_id,
            role=role,
            content=content,
            importance=max(0.0, min(1.0, importance)),
            tags=tags or [],
            metadata=metadata or {},
        )
        self._entries[entry_id] = entry
        self._order.append(entry_id)

        # Mantener límite de entradas
        while len(self._order) > self.max_entries:
            old_id = self._order.pop(0)
            self._entries.pop(old_id, None)
            logger.debug(f"Mnemosyne: Entrada evictada {old_id}")

        self._save()
        return entry_id

    def get(self, entry_id: str) -> Optional[MnemosyneEntry]:
        return self._entries.get(entry_id)

    def get_recent(self, limit: Optional[int] = None) -> List[MnemosyneEntry]:
        """Retorna las últimas N entradas por orden de inserción."""
        ids = self._order[-max(1, limit or len(self._order)):] if limit else list(self._order)
        return [self._entries[i] for i in ids if i in self._entries]

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Búsqueda por solapamiento de palabras clave (zero-dependency)."""
        q_tokens = set(query.lower().split())
        hits: List[Dict[str, Any]] = []
        for e in self._entries.values():
            t_tokens = set((e.content + " " + " ".join(e.tags)).lower().split())
            if not q_tokens or not t_tokens:
                continue
            sim = len(q_tokens & t_tokens) / max(1, len(q_tokens | t_tokens))
            if sim > 0:
                hits.append({
                    "entry_id": e.entry_id,
                    "role": e.role,
                    "content": e.content,
                    "timestamp": e.timestamp,
                    "similarity": round(sim, 4),
                    "importance": e.importance,
                    "tags": e.tags,
                    "source": "mnemosyne",
                })
        hits.sort(key=lambda h: (h["similarity"], h["importance"]), reverse=True)
        return hits[: max(1, top_k)]

    def get_by_importance(self, min_importance: float = 0.5) -> List[MnemosyneEntry]:
        return [e for e in self._entries.values() if e.importance >= min_importance]

    def mark_consolidated(self, entry_id: str) -> None:
        e = self._entries.get(entry_id)
        if e:
            e.consolidated = True
            self._save()

    def stats(self) -> Dict[str, Any]:
        return {
            "entries": len(self._entries),
            "max_entries": self.max_entries,
            "session_id": self._session_id or "",
            "data_dir": str(self.data_dir),
        }

    # ------------------------------------------------------------------ #
    # Persistencia
    # ------------------------------------------------------------------ #
    def _file(self) -> Path:
        return self.data_dir / "mnemosyne.json"

    def _save(self) -> None:
        try:
            pf = self._file()
            payload = {
                "entries": [asdict(e) for e in self._entries.values()],
                "order": self._order,
                "session_id": self._session_id,
            }
            pf.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:
            logger.warning(f"Mnemosyne: error guardando: {exc}")

    def _load(self) -> None:
        pf = self._file()
        if not pf.exists():
            return
        try:
            raw = json.loads(pf.read_text(encoding="utf-8"))
            self._entries = {
                d["entry_id"]: MnemosyneEntry(**d) for d in raw.get("entries", [])
            }
            self._order = raw.get("order", [])
            self._session_id = raw.get("session_id")
            logger.info(f"Mnemosyne: {len(self._entries)} entradas cargadas")
        except Exception as exc:
            logger.warning(f"Mnemosyne: error cargando: {exc}")
