# -*- coding: utf-8 -*-
"""
AURA OS — Chunk 1: Context Analyzer.

Analiza el contexto de una entrada combinando tres fuentes:
  1. Memoria (short/medium/long term vía MemoryManager)
  2. Grafo cognitivo (CognitiveGraphEngine)
  3. Estado del sistema (platform / recursos básicos)

Salida normalizada:
  {
    "urgencia": 0.0-1.0,
    "urgencia_nivel": "low" | "medium" | "high" | "critical",
    "tipo": "consulta" | "comando" | "creacion" | "analisis" | "conversacion",
    "dominio": "system" | "files" | "web" | "memory" | "code" | "security" | "general",
    "contexto": {...},          # payload completo (memoria, grafo, sistema, keywords)
    "enriched_prompt": "...",   # prompt listo para el DecisionEngine
  }
"""
from __future__ import annotations

import logging
import platform
import re
import time
from typing import Any, Dict, List, Optional

from backend.core.event_bus import CoreEvent, EventType, get_event_bus

logger = logging.getLogger("AURA.ContextAnalyzer")

# ------------------------------------------------------------------
# Diccionarios de clasificación
# ------------------------------------------------------------------

URGENCY_HIGH = (
    "urgente", "urgencia", "ahora", "ya mismo", "inmediato", "emergencia",
    "critico", "crítico", "error", "fallo", "crash", "caido", "caído",
    "ayuda", "socorro", "peligro", "alerta", "fire", "urgent", "critical",
)
URGENCY_MED = (
    "rapido", "rápido", "pronto", "cuanto antes", "importante", "prioridad",
    "necesito", "requiero", "deadline", "prisa",
)

DOMAIN_KEYWORDS: Dict[str, tuple] = {
    "files": ("archivo", "fichero", "carpeta", "directorio", "file", "path", "leer", "escribir", "guardar", "pdf", "csv"),
    "web": ("web", "internet", "buscar", "search", "google", "url", "http", "clima", "weather", "noticias", "scraping"),
    "system": ("sistema", "servidor", "server", "cpu", "ram", "memoria ram", "disco", "proceso", "status",
               "estado", "hora", "volumen", "pantalla", "screenshot", "apagar", "caido", "caído",
               "caida", "caída", "uptime", "latencia", "rendimiento", "log", "logs", "crash"),
    "memory": ("recuerda", "recordar", "memoria", "antes", "historial", "contexto", "conversacion", "conversación", "dijiste"),
    "code": ("codigo", "código", "code", "funcion", "función", "clase", "bug", "test", "refactor", "python", "javascript", "api", "endpoint"),
    "security": ("seguridad", "password", "contraseña", "token", "clave", "cifrado", "vulnerabilidad", "hack", "permiso", "auth"),
}

TYPE_KEYWORDS: Dict[str, tuple] = {
    "comando": ("abre", "abrir", "cierra", "cerrar", "ejecuta", "lanza", "muestra", "lista", "borra", "crea", "apaga", "enciende", "open", "run", "exec"),
    "creacion": ("crea", "genera", "escribe", "construye", "haz", "implementa", "diseña", "create", "build", "generate"),
    "analisis": ("analiza", "explica", "resume", "compara", "evalua", "por que", "por qué", "analyze", "explain", "compare"),
    "consulta": ("que", "qué", "cual", "cuál", "como", "cómo", "donde", "dónde", "cuando", "cuándo", "quien", "quién", "?", "¿", "what", "how", "why"),
    "conversacion": ("hola", "buenas", "hey", "gracias", "saludos", "hello", "hi", "tal"),
}

STOPWORDS = frozenset({
    "de", "la", "el", "los", "las", "un", "una", "y", "o", "que", "en", "por",
    "para", "con", "sin", "del", "al", "es", "son", "mi", "tu", "me", "te",
})


def _keywords(text: str, limit: int = 8) -> List[str]:
    """Extrae palabras significativas (sin stopwords) preservando orden."""
    tokens = re.findall(r"[0-9a-zA-Z_áéíóúñüÁÉÍÓÚÑÜ]+", (text or "").lower())
    out: List[str] = []
    for tok in tokens:
        if len(tok) < 3 or tok in STOPWORDS:
            continue
        if tok not in out:
            out.append(tok)
        if len(out) >= limit:
            break
    return out
# ------------------------------------------------------------------
# Analizador principal
# ------------------------------------------------------------------

class ContextAnalyzer:
    """Analiza memoria + grafo cognitivo + estado del sistema."""

    def __init__(self) -> None:
        self._bus = get_event_bus()
        self._memory: Any = None
        self._graph: Any = None
        self._last: Dict[str, Dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # dependencias (lazy: no rompen el arranque si fallan)
    # ------------------------------------------------------------------
    @property
    def memory(self) -> Any:
        if self._memory is None:
            try:
                from backend.memory.manager import get_memory_manager
                self._memory = get_memory_manager()
            except Exception as exc:  # noqa: BLE001
                logger.debug("MemoryManager no disponible: %s", exc)
                self._memory = False
        return self._memory or None

    @property
    def graph(self) -> Any:
        if self._graph is None:
            try:
                from backend.memory.cognitive_graph import get_cognitive_graph
                self._graph = get_cognitive_graph()
            except Exception as exc:  # noqa: BLE001
                logger.debug("CognitiveGraph no disponible: %s", exc)
                self._graph = False
        return self._graph or None

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------
    def analyze(
        self,
        prompt: str,
        session_id: str = "",
        input_type: str = "chat",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Analiza el prompt y devuelve urgencia, tipo, dominio y contexto
        enriquecido listo para el DecisionEngine.
        """
        prompt = prompt or ""
        meta = metadata or {}

        urgencia, nivel = self._detect_urgency(prompt, meta)
        tipo = self._detect_type(prompt, input_type)
        dominio = self._detect_domain(prompt)
        keywords = _keywords(prompt)

        memoria = self._memory_context(prompt, session_id)
        grafo = self._graph_context(prompt)
        sistema = self._system_state()

        ctx: Dict[str, Any] = {
            "session_id": session_id,
            "input_type": input_type,
            "timestamp": time.time(),
            "platform": sistema.get("platform", platform.system()),
            "keywords": keywords,
            "metadata": meta,
            "prompt": prompt,  # prompt crudo (para heurísticas del fallback local)
            "memory": memoria,
            "graph": grafo,
            "system": sistema,
            # --- claves legacy (compat con consumidores previos)
            "memory_stats": memoria.get("stats", {}),
            "relevant_memories": memoria.get("hits", []),
            "system_state": sistema,
        }

        enriched = self._enrich_prompt(prompt, urgencia, tipo, dominio, ctx)
        ctx["enriched_prompt"] = enriched
        ctx["context_size"] = len(enriched)

        result: Dict[str, Any] = {
            "urgencia": round(urgencia, 3),
            "urgencia_nivel": nivel,
            "tipo": tipo,
            "dominio": dominio,
            "contexto": ctx,
            "enriched_prompt": enriched,
            "context_size": len(enriched),
            "session_id": session_id,
        }
        self._last[session_id or "default"] = result

        self._bus.emit(CoreEvent(
            type=EventType.THOUGHT,
            data={
                "stage": "context_analyzer",
                "urgencia": result["urgencia"],
                "tipo": tipo,
                "dominio": dominio,
                "session_id": session_id,
            },
            agent="context_analyzer",
            status="analyzed",
        ))
        logger.info("analyzer: tipo=%s dominio=%s urgencia=%.2f (%s)",
                    tipo, dominio, urgencia, nivel)
        return result

    def last_analysis(self, session_id: str = "") -> Optional[Dict[str, Any]]:
        return self._last.get(session_id or "default")

    def clear(self) -> None:
        self._last.clear()

    # ------------------------------------------------------------------
    # clasificadores
    # ------------------------------------------------------------------
    def _detect_urgency(self, prompt: str, meta: Dict[str, Any]) -> tuple:
        low = (prompt or "").lower()
        score = 0.2
        if any(k in low for k in URGENCY_HIGH):
            score += 0.6
        if any(k in low for k in URGENCY_MED):
            score += 0.25
        if "!" in (prompt or ""):
            score += 0.1
        if (prompt or "").isupper() and len(prompt or "") > 6:
            score += 0.1
        try:
            score += float(meta.get("urgency_boost", 0.0))
        except (TypeError, ValueError):
            pass
        score = min(1.0, max(0.0, score))

        if score >= 0.8:
            nivel = "critical"
        elif score >= 0.55:
            nivel = "high"
        elif score >= 0.35:
            nivel = "medium"
        else:
            nivel = "low"
        return score, nivel

    def _detect_type(self, prompt: str, input_type: str) -> str:
        if input_type in ("voice", "gesture"):
            return "comando"
        low = (prompt or "").lower()
        for tipo in ("comando", "creacion", "analisis", "consulta", "conversacion"):
            if any(k in low for k in TYPE_KEYWORDS[tipo]):
                return tipo
        return "conversacion" if len(low) < 25 else "consulta"

    def _detect_domain(self, prompt: str) -> str:
        low = (prompt or "").lower()
        best, best_hits = "general", 0
        for dominio, keys in DOMAIN_KEYWORDS.items():
            hits = sum(1 for k in keys if k in low)
            if hits > best_hits:
                best, best_hits = dominio, hits
        return best

    # ------------------------------------------------------------------
    # fuentes de contexto
    # ------------------------------------------------------------------
    def _memory_context(self, prompt: str, session_id: str) -> Dict[str, Any]:
        out: Dict[str, Any] = {"available": False, "hits": [], "stats": {},
                               "session_context": {}}
        mem = self.memory
        if mem is None:
            return out
        out["available"] = True
        try:
            matches = mem.search(prompt, limit=5) or []
            out["hits"] = [
                {
                    "key": getattr(m, "key", ""),
                    "value": (getattr(m, "value", "") or "")[:200],
                    "level": getattr(m, "level", "short"),
                }
                for m in matches
            ]
        except Exception as exc:  # noqa: BLE001
            logger.debug("memory.search falló: %s", exc)
        try:
            out["stats"] = mem.stats() or {}
        except Exception as exc:  # noqa: BLE001
            logger.debug("memory.stats falló: %s", exc)
        try:
            if session_id:
                out["session_context"] = mem.get_session_context(session_id) or {}
        except Exception as exc:  # noqa: BLE001
            logger.debug("memory.get_session_context falló: %s", exc)
        return out

    def _graph_context(self, prompt: str) -> Dict[str, Any]:
        out: Dict[str, Any] = {"available": False, "nodes": [], "related": []}
        graph = self.graph
        if graph is None:
            return out
        out["available"] = True
        try:
            nodes = graph.search(prompt, limit=5) or []
            for n in nodes:
                entry = {
                    "id": getattr(n, "node_id", getattr(n, "id", "")),
                    "label": getattr(n, "label", ""),
                    "summary": (getattr(n, "summary", "") or "")[:180],
                    "tags": list(getattr(n, "tags", []) or [])[:6],
                    "weight": getattr(n, "weight", 0.0),
                }
                out["nodes"].append(entry)
                try:
                    neigh = graph.neighbors(entry["id"], limit=3) or []
                    for _edge, node in neigh:
                        out["related"].append({
                            "label": getattr(node, "label", ""),
                            "to": entry["label"],
                        })
                except Exception:  # noqa: BLE001
                    pass
            out["total_nodes"] = len(getattr(graph, "_nodes", {}) or {})
        except Exception as exc:  # noqa: BLE001
            logger.debug("graph.search falló: %s", exc)
        return out

    def _system_state(self) -> Dict[str, Any]:
        state: Dict[str, Any] = {
            "platform": platform.system(),
            "release": platform.release(),
            "python": platform.python_version(),
            "machine": platform.machine(),
            "timestamp": time.time(),
        }
        try:
            import os
            state["cwd"] = os.getcwd()
            state["cpu_count"] = os.cpu_count()
        except Exception:  # noqa: BLE001
            pass
        return state
# ------------------------------------------------------------------
    # enriquecimiento del prompt
    # ------------------------------------------------------------------
    def _enrich_prompt(
        self,
        prompt: str,
        urgencia: float,
        tipo: str,
        dominio: str,
        ctx: Dict[str, Any],
    ) -> str:
        parts: List[str] = []
        parts.append(f"[URGENCIA] {urgencia:.2f}")
        parts.append(f"[TIPO] {tipo}")
        parts.append(f"[DOMINIO] {dominio}")

        sistema = ctx.get("system", {})
        parts.append(f"[SISTEMA] {sistema.get('platform', 'unknown')} "
                     f"py{sistema.get('python', '?')} cwd={sistema.get('cwd', '?')}")

        sesion = ctx.get("session_id") or "nueva"
        partes_sesion = [f"[SESION] {sesion}"]
        keywords = ctx.get("keywords") or []
        if keywords:
            partes_sesion.append(f"[KEYWORDS] {', '.join(keywords)}")
        parts.append(" ".join(partes_sesion))

        hits = (ctx.get("memory") or {}).get("hits") or []
        if hits:
            mem_txt = " | ".join(
                f"{h.get('key', '')}={h.get('value', '')[:80]}" for h in hits[:3]
            )
            parts.append(f"[MEMORIA] {mem_txt}")

        nodos = (ctx.get("graph") or {}).get("nodes") or []
        if nodos:
            graf_txt = " | ".join(
                f"{n.get('label', '')} ({n.get('summary', '')[:50]})" for n in nodos[:3]
            )
            parts.append(f"[GRAFO] {graf_txt}")

        parts.append(f"[CONSULTA] {prompt}")
        return "\n\n".join(parts)

    def handle_event(self, event: CoreEvent) -> None:
        """Maneja un evento de entrada y emite el análisis al EventBus."""
        if event.type == EventType.INPUT:
            input_data = event.data
            prompt = input_data.get("content", "")
            session_id = input_data.get("session_id", "")
            input_type = input_data.get("type", "chat")
            metadata = input_data.get("metadata", {})

            analysis = self.analyze(prompt, session_id, input_type, metadata)
            analysis_event = CoreEvent(
                type=EventType.THOUGHT,
                data={
                    "context_analysis": analysis,
                    "original_event": event.data
                },
                agent="context_analyzer"
            )
            self._bus.emit(analysis_event)


# ------------------------------------------------------------------
# Singleton
# ------------------------------------------------------------------

_analyzer: Optional[ContextAnalyzer] = None


def get_context_analyzer() -> ContextAnalyzer:
    global _analyzer
    if _analyzer is None:
        _analyzer = ContextAnalyzer()
    return _analyzer


def reset_context_analyzer() -> None:
    global _analyzer
    if _analyzer is not None:
        _analyzer.clear()
    _analyzer = None
