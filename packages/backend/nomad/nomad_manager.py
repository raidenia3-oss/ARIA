"""N.O.M.A.D. manager - Offline-first service orchestrator."""

from __future__ import annotations

import asyncio
import json
import os
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from backend.database import SessionLocal
from backend.models import LogEntry


class ServiceStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DOWN = "down"
    UNKNOWN = "unknown"


class NomadService(str, Enum):
    OLLAMA = "ollama"
    QDRANT = "qdrant"
    KIWIX = "kiwix"
    KOLIBRI = "kolibri"
    PROTOMAPS = "protomaps"
    CYBERCHEF = "cyberchef"
    COMMAND_CENTER = "command_center"


SERVICE_DEFAULT_PORTS: Dict[NomadService, int] = {
    NomadService.OLLAMA: 11434,
    NomadService.QDRANT: 6333,
    NomadService.KIWIX: 8080,
    NomadService.KOLIBRI: 8008,
    NomadService.PROTOMAPS: 8100,
    NomadService.CYBERCHEF: 8010,
    NomadService.COMMAND_CENTER: 8000,
}


@dataclass
class ServiceHealth:
    service: NomadService
    status: ServiceStatus
    port: int
    last_check: str
    error: Optional[str] = None
    latency_ms: Optional[float] = None


class NomadManager:
    """Orquesta servicios offline N.O.M.A.D."""

    def __init__(self) -> None:
        self.services: Dict[NomadService, ServiceHealth] = {}
        self.compose_path = os.path.join(os.path.dirname(__file__), "..", "..", "docker", "docker-compose.nomad.yml")

    async def check_ollama(self) -> ServiceHealth:
        port = SERVICE_DEFAULT_PORTS[NomadService.OLLAMA]
        return await self._probe_http(NomadService.OLLAMA, port, "/api/tags")

    async def check_qdrant(self) -> ServiceHealth:
        port = SERVICE_DEFAULT_PORTS[NomadService.QDRANT]
        return await self._probe_http(NomadService.QDRANT, port, "/healthz")

    async def check_kiwix(self) -> ServiceHealth:
        port = SERVICE_DEFAULT_PORTS[NomadService.KIWIX]
        return await self._probe_http(NomadService.KIWIX, port, "/")

    async def check_kolibri(self) -> ServiceHealth:
        port = SERVICE_DEFAULT_PORTS[NomadService.KOLIBRI]
        return await self._probe_http(NomadService.KOLIBRI, port, "/")

    async def check_protomaps(self) -> ServiceHealth:
        port = SERVICE_DEFAULT_PORTS[NomadService.PROTOMAPS]
        return await self._probe_http(NomadService.PROTOMAPS, port, "/")

    async def check_cyberchef(self) -> ServiceHealth:
        port = SERVICE_DEFAULT_PORTS[NomadService.CYBERCHEF]
        return await self._probe_http(NomadService.CYBERCHEF, port, "/")

    async def check_command_center(self) -> ServiceHealth:
        port = SERVICE_DEFAULT_PORTS[NomadService.COMMAND_CENTER]
        return await self._probe_http(NomadService.COMMAND_CENTER, port, "/health")

    async def health_check_all(self) -> Dict[str, Any]:
        checks = {
            "ollama": self.check_ollama(),
            "qdrant": self.check_qdrant(),
            "kiwix": self.check_kiwix(),
            "kolibri": self.check_kolibri(),
            "protomaps": self.check_protomaps(),
            "cyberchef": self.check_cyberchef(),
            "command_center": self.check_command_center(),
        }
        results = await asyncio.gather(*checks.values(), return_exceptions=True)
        summary = {}
        for service, result in zip(checks.keys(), results):
            if isinstance(result, Exception):
                summary[service] = ServiceHealth(
                    service=NomadService[service.upper()],
                    status=ServiceStatus.DOWN,
                    port=SERVICE_DEFAULT_PORTS[NomadService[service.upper()]],
                    last_check=datetime.now().isoformat(),
                    error=str(result),
                ).__dict__
            else:
                summary[service] = result.__dict__
        await self._persist_status(summary)
        return summary

    async def _probe_http(self, service: NomadService, port: int, path: str) -> ServiceHealth:
        import urllib.request
        url = f"http://127.0.0.1:{port}{path}"
        started = datetime.now()
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                latency = (datetime.now() - started).total_seconds() * 1000
                status = ServiceStatus.HEALTHY if resp.status < 400 else ServiceStatus.DEGRADED
                return ServiceHealth(
                    service=service,
                    status=status,
                    port=port,
                    last_check=datetime.now().isoformat(),
                    latency_ms=round(latency, 2),
                )
        except Exception as e:
            return ServiceHealth(
                service=service,
                status=ServiceStatus.DOWN,
                port=port,
                last_check=datetime.now().isoformat(),
                error=str(e),
            )

    async def _persist_status(self, summary: Dict[str, Any]) -> None:
        db = SessionLocal()
        try:
            entry = LogEntry(
                service="nomad_health",
                level="INFO",
                message=json.dumps(summary, ensure_ascii=False),
                timestamp=datetime.now().timestamp(),
            )
            db.add(entry)
            db.commit()
        finally:
            db.close()

    async def ingest_document(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """Ingesta un documento en el stack offline N.O.M.A.D.

        Flujo offline-first:
        1. Generar embedding local con Ollama.
        2. Persistir en Qdrant.
        3. Guardar trazabilidad en logs locales.
        """
        doc_id = document.get("id") or str(int(datetime.now().timestamp() * 1000))
        text = document.get("text") or document.get("content") or ""
        metadata = document.get("metadata") or {}

        ollama_embedding = await self._ollama_embed(text)
        qdrant_payload = await self._qdrant_upsert(doc_id, ollama_embedding, metadata)

        return {
            "document_id": doc_id,
            "status": "ingested",
            "ollama": ollama_embedding,
            "qdrant": qdrant_payload,
        }

    async def rag_query(self, query: str, limit: int = 5) -> Dict[str, Any]:
        """Ejecuta una consulta RAG offline.

        1. Embedding de la query con Ollama.
        2. Búsqueda semántica en Qdrant.
        3. Retorna contexto y fuentes.
        """
        query_embedding = await self._ollama_embed(query)
        search_results = await self._qdrant_search(query_embedding, limit=limit)

        context_parts = []
        sources = []
        for item in search_results:
            text = item.get("payload", {}).get("text") or item.get("text") or ""
            score = item.get("score") or 0.0
            context_parts.append(text)
            sources.append({"id": item.get("id"), "score": score, "text": text[:200]})

        context = "\n---\n".join(context_parts)
        return {
            "query": query,
            "context": context,
            "sources": sources,
            "total_sources": len(sources),
        }

    async def get_status(self) -> Dict[str, Any]:
        health = await self.health_check_all()
        active = [k for k, v in health.items() if v.get("status") == "healthy"]
        degraded = [k for k, v in health.items() if v.get("status") == "degraded"]
        down = [k for k, v in health.items() if v.get("status") == "down"]
        return {
            "status": "healthy" if not degraded and not down else "degraded" if degraded else "down",
            "healthy": active,
            "degraded": degraded,
            "down": down,
            "total_services": len(health),
            "services": health,
        }

    async def _ollama_embed(self, text: str) -> List[float]:
        """Genera embedding local usando Ollama."""
        payload = json.dumps({"prompt": text}).encode()
        req = urllib.request.Request(
            "http://127.0.0.1:11434/api/embed",
            data=payload,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                embedding = data.get("embedding") or []
                if not embedding:
                    return [0.0] * 768
                return embedding
        except Exception:
            return [0.0] * 768

    async def _qdrant_upsert(self, doc_id: str, embedding: List[float], metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Persiste vector en Qdrant."""
        payload = json.dumps({
            "points": [
                {
                    "id": doc_id,
                    "vector": embedding,
                    "payload": metadata,
                }
            ]
        }).encode()
        req = urllib.request.Request(
            "http://127.0.0.1:6333/collections/nomad/points",
            data=payload,
            method="PUT",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            return {"error": str(e), "doc_id": doc_id}

    async def _qdrant_search(self, embedding: List[float], limit: int = 5) -> List[Dict[str, Any]]:
        """Busca vectores similares en Qdrant."""
        payload = json.dumps({
            "vector": embedding,
            "limit": limit,
            "score_threshold": 0.0,
        }).encode()
        req = urllib.request.Request(
            "http://127.0.0.1:6333/collections/nomad/points/search",
            data=payload,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("result", [])
        except Exception:
            return []

    def compose_template(self) -> str:
        return self._render_compose()

    def _render_compose(self) -> str:
        return """version: '3.8'

services:
  ollama:
    image: ollama/ollama:latest
    ports:
      - '11434:11434'
    volumes:
      - ollama_data:/root/.ollama
    healthcheck:
      test: ['CMD', 'curl', '-f', 'http://localhost:11434/api/tags']
      interval: 30s
    networks:
      - nomad-net

  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - '6333:6333'
      - '6334:6334'
    volumes:
      - qdrant_data:/qdrant/storage
    healthcheck:
      test: ['CMD', 'curl', '-f', 'http://localhost:6333/healthz']
      interval: 30s
    networks:
      - nomad-net

  kiwix:
    image: kiwix/kiwix-serve:latest
    ports:
      - '8080:8080'
    volumes:
      - kiwix_data:/data
    healthcheck:
      test: ['CMD', 'curl', '-f', 'http://localhost:8080/']
      interval: 30s
    networks:
      - nomad-net

  kolibri:
    image: learningequality/kolibri:latest
    ports:
      - '8008:8008'
    volumes:
      - kolibri_data:/kolibri
    healthcheck:
      test: ['CMD', 'curl', '-f', 'http://localhost:8008/']
      interval: 30s
    networks:
      - nomad-net

  protomaps:
    image: protomaps/protomaps:latest
    ports:
      - '8100:8080'
    volumes:
      - protomaps_data:/data
    healthcheck:
      test: ['CMD', 'curl', '-f', 'http://localhost:8080/']
      interval: 30s
    networks:
      - nomad-net

  cyberchef:
    image: gchq/cyberchef:latest
    ports:
      - '8010:8080'
    healthcheck:
      test: ['CMD', 'curl', '-f', 'http://localhost:8080/']
      interval: 30s
    networks:
      - nomad-net

networks:
  nomad-net:
    driver: bridge

volumes:
  ollama_data:
  qdrant_data:
  kiwix_data:
  kolibri_data:
  protomaps_data:
"""
