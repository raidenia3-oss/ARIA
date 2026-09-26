"""
Smart Query Router - Adaptive Routing Module.
Decides where to process each query based on availability and query characteristics.
"""

from __future__ import annotations

import time
import logging
import requests
from enum import Enum
from typing import Any, Dict, List, Optional

from backend.orchestrator import orchestrator, NODE_PC, NODE_SERVER, NODE_MOBILE, ROLE_EXTERNAL

logger = logging.getLogger("AURA.Router")

CACHE_TTL = 60 * 60  # 1 hour
_response_cache: Dict[str, Dict[str, Any]] = {}
_route_history: List[Dict[str, Any]] = []
_query_queue: List[Dict[str, Any]] = []


def _is_local_backend_alive(url: str = "http://localhost:8000", timeout: int = 2) -> bool:
    try:
        resp = requests.get(f"{url}/health", timeout=timeout)
        return resp.status_code == 200
    except Exception:
        return False


class RouteTarget(str, Enum):
    SERVER = "server"
    PC = "pc"
    API = "api"
    CACHE = "cache"
    QUEUE = "queue"


class QueryRouter:
    """Enruta queries inteligentemente según disponibilidad y características."""

    def __init__(self) -> None:
        self.orchestrator = orchestrator

    def analyze_query(self, query: str) -> Dict[str, Any]:
        q = (query or "").lower()
        words = q.split()
        urgent_keywords = ["ahora", "rápido", "urgente", "inmediato", "ayuda", "emergencia"]
        quality_keywords = ["explica", "analiza", "profundo", "detalle", "completo", "comparar", "razona"]
        fresh_keywords = ["hoy", "ahora", "nuevo", "último", "actual", "news", "clima", "precio", "stock"]
        return {
            "is_urgent": any(k in q for k in urgent_keywords),
            "needs_quality": any(k in q for k in quality_keywords) or len(query) > 100,
            "needs_fresh_data": any(k in q for k in fresh_keywords),
            "estimated_tokens": len(words),
        }

    def route_query(self, query: str, context: Optional[Dict[str, Any]] = None) -> RouteTarget:
        analysis = self.analyze_query(query)
        status = self.orchestrator.get_status()
        available = status.get("available_backends", [])
        primary = status.get("primary_backend")

        server_online = (NODE_SERVER in available or primary == NODE_SERVER or _is_local_backend_alive())
        pc_online = NODE_PC in available
        mobile_connected = NODE_MOBILE in available

        if analysis["is_urgent"]:
            if server_online:
                return RouteTarget.SERVER
            if self._has_cache(query):
                return RouteTarget.CACHE
            return RouteTarget.QUEUE

        if analysis["needs_quality"]:
            if pc_online:
                return RouteTarget.PC
            if server_online:
                return RouteTarget.SERVER
            if self._has_cache(query):
                return RouteTarget.CACHE
            return RouteTarget.QUEUE

        if analysis["needs_fresh_data"]:
            if mobile_connected:
                return RouteTarget.API
            if pc_online:
                return RouteTarget.PC
            return RouteTarget.QUEUE

        if server_online:
            return RouteTarget.SERVER
        if self._has_cache(query):
            return RouteTarget.CACHE
        return RouteTarget.QUEUE

    def get_response(self, query: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        route = self.route_query(query, context)
        self._log_route(query, route)

        if route == RouteTarget.SERVER:
            return self._route_to_server(query)
        if route == RouteTarget.PC:
            return self._route_to_pc(query)
        if route == RouteTarget.API:
            return self._route_to_api(query)
        if route == RouteTarget.CACHE:
            return self._route_to_cache(query)
        return self._queue_for_later(query)

    def async_improvement(self, query: str, initial_response: Dict[str, Any]) -> None:
        try:
            better_route = self.route_query(query)
            if better_route != RouteTarget.CACHE:
                better_response = self.get_response(query)
                if better_response.get("route") != "cache":
                    initial_response.update(better_response)
                    initial_response["improved"] = True
        except Exception as exc:
            logger.error("Async improvement failed: %s", exc)

    def _route_to_server(self, query: str) -> Dict[str, Any]:
        return {
            "response": f"[SERVER] {query}",
            "route": "server",
            "latency_ms": 0,
            "model": "qwen-0.5b",
        }

    def _route_to_pc(self, query: str) -> Dict[str, Any]:
        return {
            "response": f"[PC] {query}",
            "route": "pc",
            "latency_ms": 0,
            "model": "qwen-7b",
        }

    def _route_to_api(self, query: str) -> Dict[str, Any]:
        return {
            "response": f"[API] {query}",
            "route": "api",
            "latency_ms": 0,
            "model": "groq/gemini/openrouter",
        }

    def _route_to_cache(self, query: str) -> Dict[str, Any]:
        cached = self._get_cache(query)
        return {
            "response": cached or "No cache available",
            "route": "cache",
            "latency_ms": 0,
            "model": "cached",
            "is_cached": cached is not None,
        }

    def _queue_for_later(self, query: str) -> Dict[str, Any]:
        queue_id = f"{int(time.time())}-{len(_query_queue)}"
        _query_queue.append({"queue_id": queue_id, "query": query, "ts": time.time()})
        return {
            "queued": True,
            "queue_id": queue_id,
            "message": "En cola, esperando disponibilidad",
            "route": "queue",
        }

    def get_status(self) -> Dict[str, Any]:
        status = self.orchestrator.get_status()
        nodes = status.get("nodes", {})
        server_online = nodes.get(NODE_SERVER, {}).get("status") == "online" or _is_local_backend_alive()
        pc_online = nodes.get(NODE_PC, {}).get("status") == "online"
        mobile_connected = nodes.get(NODE_MOBILE, {}).get("status") == "online"
        return {
            "server": server_online,
            "pc": pc_online,
            "mobile": mobile_connected,
            "cache": len(_response_cache) > 0,
            "queue": len(_query_queue),
            "primary_backend": status.get("primary_backend"),
            "available_backends": status.get("available_backends", []),
        }

    def get_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        return _route_history[-limit:]

    def _has_cache(self, query: str) -> bool:
        return self._get_cache(query) is not None

    def _get_cache(self, query: str) -> Optional[str]:
        entry = _response_cache.get(query)
        if not entry:
            return None
        if time.time() - entry.get("ts", 0) > CACHE_TTL:
            _response_cache.pop(query, None)
            return None
        return entry.get("response")

    def _set_cache(self, query: str, response: str) -> None:
        _response_cache[query] = {"ts": time.time(), "response": response}

    def _log_route(self, query: str, route: RouteTarget) -> None:
        _route_history.append({
            "timestamp": time.time(),
            "query": query,
            "route": route.value,
            "status": self.orchestrator.get_status(),
        })


query_router = QueryRouter()
