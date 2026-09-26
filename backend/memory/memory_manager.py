"""
AURA OS - Chunk 3: Memory Manager

Sistema de memoria segmentado en tres niveles:
- Corto plazo: últimas 20 conversaciones
- Mediano plazo: últimas 24 horas
- Largo plazo: patrones permanentes

Método get_context() retorna contexto relevante por similaridad semántica.
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger("AURA.MemoryManager")

# -------------------------------------------------------------------------
# Configuración
# -------------------------------------------------------------------------

DATA_DIR = Path(os.environ.get("AURA_DATA_DIR", "data/memory"))
CACHE_TTL_SECONDS = int(os.environ.get("AURA_CACHE_TTL", "3600"))  # 1 hora


@dataclass
class ConversationEntry:
    """Entrada individual en memoria a corto plazo."""
    role: str
    content: str
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ConversationEntry":
        return cls(
            role=d.get("role", "user"),
            content=d.get("content", ""),
            timestamp=d.get("timestamp", time.time()),
            metadata=d.get("metadata", {}),
        )


@dataclass
class LongTermPattern:
    """Patrón almacenado en memoria a largo plazo."""
    pattern_id: str
    trigger: str
    response: str
    frequency: int = 1
    last_used: float = field(default_factory=time.time)
    confidence: float = 0.5
    created_at: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "pattern_id": self.pattern_id,
            "trigger": self.trigger,
            "response": self.response,
            "frequency": self.frequency,
            "last_used": self.last_used,
            "confidence": self.confidence,
            "created_at": self.created_at,
        }
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "LongTermPattern":
        return cls(
            pattern_id=d["pattern_id"],
            trigger=d["trigger"],
            response=d["response"],
            frequency=d.get("frequency", 1),
            last_used=d.get("last_used", time.time()),
            confidence=d.get("confidence", 0.5),
            created_at=d.get("created_at", time.time()),
        )


class MemoryManager:
    """
    Gestión de memoria segmentada en tres capas:
    
    1. Corto plazo (short_term): últimas 20 conversaciones, viven en RAM.
       Se vacían al cerrar sesión o al superar el límite.
    
    2. Mediano plazo (medium_term): persistencia en disco de las últimas 
       24 horas de conversaciones. Se accede por rango temporal.
    
    3. Largo plazo (long_term): patrones permanentes que se actualizan 
       dinámicamente. Se accede por similaridad semántica (keyword match).
    
    La persistencia a medio y largo plazo se guarda en JSON para 
    compatibilidad con sistemas sin base de datos externa.
    """
    
    def __init__(
        self,
        short_term_limit: int = 20,
        data_dir: Optional[Path] = None,
    ) -> None:
        """
        Inicializa el MemoryManager.
        
        Args:
            short_term_limit: Número máximo de entradas en corto plazo.
            data_dir: Directorio base para persistencia. Si es None, usa DATA_DIR.
        """
        self._short_term_limit = max(1, short_term_limit)
        self._data_dir = data_dir or DATA_DIR
        self._short_term: List[ConversationEntry] = []
        self._long_term_patterns: List[LongTermPattern] = []
        self._session_id: Optional[str] = None
        self._ensure_dirs()
        self._load_long_term()
    
    def _ensure_dirs(self) -> None:
        """Crea los directorios necesarios si no existen."""
        self._data_dir.mkdir(parents=True, exist_ok=True)
        (self._data_dir / "sessions").mkdir(exist_ok=True)
        (self._data_dir / "patterns").mkdir(exist_ok=True)
    
    def set_session(self, session_id: str) -> None:
        """
        Cambia la sesión activa. Vaciar el corto plazo al cambiar de sesión.
        """
        if self._session_id != session_id:
            self._short_term.clear()
            self._session_id = session_id
            logger.debug(f"MemoryManager: Sesión cambiada a {session_id}")
    
    # -------------------------------------------------------------------------
    # Inserción
    # -------------------------------------------------------------------------
    
    def add_short_term(self, role: str, content: str,
                       metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Agrega una entrada a memoria a corto plazo.
        Si excede el límite, se descarta la más antigua.
        """
        entry = ConversationEntry(
            role=role,
            content=content,
            metadata=metadata or {},
        )
        self._short_term.append(entry)
        if len(self._short_term) > self._short_term_limit:
            removed = self._short_term.pop(0)
            logger.debug(f"MemoryManager: Eliminado entry antiguo: {removed.content[:50]}...")
        logger.debug(f"MemoryManager: Added short-term: {role} -> {content[:30]}...")
    
    def add_long_term_pattern(self, trigger: str, response: str,
                              pattern_id: Optional[str] = None) -> LongTermPattern:
        """
        Agrega o actualiza un patrón a largo plazo.
        Si el patrón ya existe (misma trigger), incrementa frecuencia.
        """
        pid = pattern_id or f"pattern_{int(time.time())}_{len(self._long_term_patterns)}"
        
        existing = next((p for p in self._long_term_patterns if p.trigger == trigger), None)
        if existing:
            existing.frequency += 1
            existing.last_used = time.time()
            existing.confidence = min(1.0, existing.confidence + 0.05)
            logger.debug(f"MemoryManager: Patrón actualizado: {trigger}")
            return existing
        
        pattern = LongTermPattern(
            pattern_id=pid,
            trigger=trigger,
            response=response,
            frequency=1,
            confidence=0.5,
        )
        self._long_term_patterns.append(pattern)
        self._save_long_term()
        logger.info(f"MemoryManager: Nuevo patrón guardado: {trigger} -> {response[:50]}...")
        return pattern
    
    def add_medium_term(self, entry: ConversationEntry) -> None:
        """
        Persiste una entrada a medio plazo en disco.
        Se guarda en session/<session_id>.json.
        """
        if not self._session_id:
            logger.warning("MemoryManager: No hay sesión activa, no se puede persistir a medio plazo")
            return
        
        session_file = self._data_dir / "sessions" / f"{self._session_id}.json"
        sessions: Dict[str, List[Dict]] = {}
        
        if session_file.exists():
            try:
                with open(session_file, "r", encoding="utf-8") as f:
                    sessions = json.load(f)
            except (json.JSONDecodeError, IOError):
                sessions = {}
        
        timestamp_key = datetime.fromtimestamp(entry.timestamp).strftime("%Y%m%d_%H")
        if timestamp_key not in sessions:
            sessions[timestamp_key] = []
        
        sessions[timestamp_key].append(entry.to_dict())
        
        with open(session_file, "w", encoding="utf-8") as f:
            json.dump(sessions, f, ensure_ascii=False, indent=2)
        
        logger.debug(f"MemoryManager: Persistido a medio plazo: {entry.content[:30]}...")
    
    # -------------------------------------------------------------------------
    # Recuperación
    # -------------------------------------------------------------------------
    
    def get_short_term(self, limit: Optional[int] = None) -> List[ConversationEntry]:
        """Retorna las últimas N entradas de corto plazo."""
        if limit is None:
            return list(self._short_term)
        return list(self._short_term)[-max(1, limit):]
    
    def get_long_term_patterns(self, top_k: int = 20) -> List[LongTermPattern]:
        """Retorna los patrones a largo plazo ordenados por frecuencia."""
        return sorted(self._long_term_patterns, key=lambda p: p.frequency, reverse=True)[:max(1, top_k)]
    
    def get_medium_term(self, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retorna conversaciones persistidas (últimas 24h) de una sesión."""
        sid = session_id or self._session_id
        if not sid:
            return []
        session_file = self._data_dir / "sessions" / f"{sid}.json"
        if not session_file.exists():
            return []
        try:
            with open(session_file, "r", encoding="utf-8") as f:
                sessions = json.load(f)
        except (json.JSONDecodeError, IOError):
            return []
        cutoff = time.time() - 24 * 3600
        out: List[Dict[str, Any]] = []
        for bucket in sorted(sessions.keys()):
            for d in sessions[bucket]:
                if d.get("timestamp", 0) >= cutoff:
                    out.append(d)
        return out
    
    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Búsqueda semántica simple (keyword overlap) sobre corto plazo
        y patrones a largo plazo. Retorna hits rankeados por similitud.
        """
        q_tokens = set(query.lower().split())
        hits: List[Tuple[float, Dict[str, Any]]] = []
        for e in self._short_term:
            t_tokens = set(e.content.lower().split())
            if not q_tokens or not t_tokens:
                continue
            sim = len(q_tokens & t_tokens) / max(1, len(q_tokens | t_tokens))
            if sim > 0.0:
                hits.append((sim, {"source": "short_term", "role": e.role,
                                   "content": e.content, "timestamp": e.timestamp}))
        for p in self._long_term_patterns:
            t_tokens = set((p.trigger + " " + p.response).lower().split())
            sim = len(q_tokens & t_tokens) / max(1, len(q_tokens | t_tokens))
            if sim > 0.0:
                hits.append((sim, {"source": "long_term", "role": "pattern",
                                   "content": f"{p.trigger} -> {p.response}",
                                   "timestamp": p.last_used}))
        hits.sort(key=lambda h: h[0], reverse=True)
        return [dict(h, similarity=round(s, 4)) for s, h in hits[:max(1, top_k)]]
    
    def get_context(self, query: str, top_k: int = 5) -> Dict[str, Any]:
        """
        Contexto consolidado para el ContextAnalyzer:
        hits de búsqueda + contadores por capa.
        """
        hits = self.search(query, top_k=top_k)
        return {
            "hits": hits,
            "short_term_size": len(self._short_term),
            "long_term_patterns": len(self._long_term_patterns),
            "session_id": self._session_id or "",
        }
    
    def stats(self) -> Dict[str, Any]:
        """Estadísticas de memoria para /api/core/status."""
        return {
            "short_term": len(self._short_term),
            "short_term_limit": self._short_term_limit,
            "long_term_patterns": len(self._long_term_patterns),
            "session_id": self._session_id or "",
            "data_dir": str(self._data_dir),
        }
    
    # -------------------------------------------------------------------------
    # Persistencia largo plazo
    # -------------------------------------------------------------------------
    
    def _patterns_file(self) -> Path:
        return self._data_dir / "patterns" / "patterns.json"
    
    def _load_long_term(self) -> None:
        pf = self._patterns_file()
        if not pf.exists():
            return
        try:
            with open(pf, "r", encoding="utf-8") as f:
                raw = json.load(f)
            self._long_term_patterns = [LongTermPattern.from_dict(d) for d in raw]
            logger.info(f"MemoryManager: {len(self._long_term_patterns)} patrones cargados")
        except Exception as exc:
            logger.warning(f"MemoryManager: error cargando patrones: {exc}")
    
    def _save_long_term(self) -> None:
        pf = self._patterns_file()
        try:
            with open(pf, "w", encoding="utf-8") as f:
                json.dump([p.to_dict() for p in self._long_term_patterns], f,
                          ensure_ascii=False, indent=2)
        except Exception as exc:
            logger.warning(f"MemoryManager: error guardando patrones: {exc}")


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_manager: Optional[MemoryManager] = None


def get_memory_manager() -> MemoryManager:
    global _manager
    if _manager is None:
        _manager = MemoryManager()
    return _manager


def reset_memory_manager() -> None:
    global _manager
    _manager = None
