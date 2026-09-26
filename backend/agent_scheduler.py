"""AURA Agent Scheduler — Background Daemon, Jan Reflection Engine & Async Event Dispatcher.

Proporciona:
1. **BackgroundDaemon** — scheduler asyncio con tareas programadas (cron-style)
   integrado en el ciclo de vida de FastAPI (startup/shutdown).
2. **JanReflectionEngine** — subrutina que consulta el modelo local de Jan (vía
   AIRouter o directamente localhost:1337/v1) para detectar baches argumentales
   y sugerir giros de trama basados en las últimas entradas de canon.
3. **AsyncEventDispatcher** — canaliza resultados de tareas en segundo plano hacia
   el WebSocket Gateway (Bloque 33) y la Bóveda de Discord (canon-feed).

No introduce dependencias pesadas: solo asyncio, httpx (ya usado por ai_router)
y módulos locales de AURA.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Callable

logger = logging.getLogger("AURA.AgentScheduler")

DEFAULT_COHERENCE_INTERVAL = int(os.getenv("AURA_COHERENCE_INTERVAL", "600"))  # 10 min
DEFAULT_REFLECTION_INTERVAL = int(os.getenv("AURA_REFLECTION_INTERVAL", "3600"))  # 1h
DEFAULT_SUMMARY_INTERVAL = int(os.getenv("AURA_SUMMARY_INTERVAL", "86400"))  # 24h
DEFAULT_CACHE_CLEANUP_INTERVAL = int(os.getenv("AURA_CACHE_CLEANUP_INTERVAL", "300"))  # 5m
DEFAULT_VAULT_BACKUP_INTERVAL = int(os.getenv("AURA_VAULT_BACKUP_INTERVAL", "1800"))  # 30m


@dataclass
class ScheduledTask:
    """Representa una tarea programada en el BackgroundDaemon."""
    task_id: str
    name: str
    interval: int
    func: Callable[[], "Any"]
    last_run: float = 0.0
    enabled: bool = True
    last_error: str = ""
    run_count: int = 0


@dataclass
class ReflectionResult:
    """Resultado de una reflexión del Jan Reflection Engine."""
    work_id: str
    analysis: str
    gaps: List[str] = field(default_factory=list)
    plot_twists: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)


class AsyncEventDispatcher:
    """Canaliza resultados de tareas en segundo plano hacia WebSocket y Discord."""

    @staticmethod
    async def dispatch_to_websocket(
        event_type: str,
        payload: Dict[str, Any],
        work_id: Optional[str] = None,
    ) -> int:
        """Envía un evento al WebSocket Gateway (/api/ws/stream)."""
        try:
            from backend.websocket_manager import ws_gateway
            return await ws_gateway.broadcast(event_type, payload, work_id=work_id)
        except Exception as exc:
            logger.warning("WebSocket dispatch failed: %s", exc)
            return 0

    @staticmethod
    async def archive_to_discord_vault(
        work_id: str,
        event_type: str,
        payload: Dict[str, Any],
    ) -> bool:
        """Archiva un evento en la bóveda de Discord vía record_canon_event (canon-feed)."""
        try:
            from backend.discord_diagnostics import record_canon_event
            description = payload.get("description") or payload.get("analysis", "")[:200]
            return record_canon_event(
                work_id=work_id,
                event_id=str(uuid.uuid4()),
                source=f"bg-{event_type}",
                description=description,
            )
        except Exception as exc:
            logger.warning("Discord vault archive failed: %s", exc)
            return False

    @staticmethod
    async def dispatch_reflection(
        work_id: str,
        result: Dict[str, Any],
    ) -> None:
        """Dispacha resultados de reflexión a WebSocket + Discord Vault."""
        await asyncio.gather(
            AsyncEventDispatcher.dispatch_to_websocket(
                "reflection",
                {"work_id": work_id, "analysis": result.get("analysis", ""),
                 "gaps": result.get("gaps", []), "plot_twists": result.get("plot_twists", [])},
                work_id=work_id,
            ),
            AsyncEventDispatcher.archive_to_discord_vault(
                work_id=work_id,
                event_type="reflection",
                payload={"analysis": result.get("analysis", ""), "gaps": result.get("gaps", [])},
            ),
            return_exceptions=True,
        )


class JanReflectionEngine:
    """Subrutina que usa Jan (o AIRouter) para análisis narrativo autónomo."""

    JAN_BASE_URL_DEFAULT = "http://localhost:1337/v1"

    def __init__(self, ai_router: Any = None) -> None:
        self._ai_router = ai_router

    async def _query_jan(self, prompt: str, system_prompt: str = "") -> Optional[str]:
        """Consulta Jan directamente (OpenAI-compatible en localhost:1337/v1)."""
        import httpx

        base_url = os.getenv("JAN_API_BASE_URL", self.JAN_BASE_URL_DEFAULT).rstrip("/")
        model = os.getenv("JAN_MODEL", "gemma-3-1b-it")
        body = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt or "Eres AURA, un asistente narrativo experto."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.7,
            "max_tokens": 1024,
            "stream": False,
        }
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(
                    f"{base_url}/chat/completions",
                    json=body,
                    headers={"Content-Type": "application/json"},
                )
                resp.raise_for_status()
                data = resp.json()
                text = ((data.get("choices") or [{}])[0].get("message") or {}).get("content", "").strip()
                if text:
                    return text
        except Exception:
            return None
        return None

    async def _query_router(self, prompt: str, system_prompt: str = "") -> Optional[str]:
        """Consulta el AIRouter (multi-proveedor con fallback a Jan)."""
        if self._ai_router is not None:
            try:
                result = await self._ai_router.generate_response(
                    prompt=prompt,
                    system_prompt=system_prompt or "Eres AURA, un asistente narrativo experto.",
                    max_tokens=1024,
                    temperature=0.7,
                )
                if result and result.get("message"):
                    return str(result["message"])
            except Exception:
                return None
        return None

    def _get_recent_canon(self, work_id: str, max_events: int = 20) -> List[Dict[str, Any]]:
        """Obtiene los eventos canónicos recientes de una obra."""
        try:
            from backend.story_memory.story_storage import StoryStorage
            storage = StoryStorage()
            events = storage.get_canon_events(work_id)
            return events[-max_events:]
        except Exception:
            return []

    def _get_works(self) -> List[Dict[str, Any]]:
        """Lista las obras literarias existentes."""
        try:
            from backend.story_memory.story_storage import StoryStorage
            return StoryStorage().list_works()
        except Exception:
            return []

    async def reflect_on_work(self, work_id: str) -> Optional[Dict[str, Any]]:
        """Analiza coherencia y sugiere giros de trama para una obra usando Jan/AIRouter."""
        recent = self._get_recent_canon(work_id, max_events=20)
        if not recent:
            logger.debug("No canon events for work_id=%s, skipping reflection", work_id)
            return None

        descriptions = "\n".join(
            f"- [{e.get('event_id', 'e'+str(i))}] {e.get('description', '')}"
            for i, e in enumerate(recent)
        )
        prompt = (
            f"Obra: {work_id}\n"
            f"Eventos canónicos recientes:\n{descriptions}\n\n"
            "Identifica posibles baches argumentales, contradicciones de continuidad "
            "y sugiere giros de trama creativos. Responde en formato JSON:\n"
            '{"analysis": "...", "gaps": ["..."], "plot_twists": ["..."]}'
        )
        system_prompt = (
            "Eres un crítico literario experto en narrativa de ficción. "
            "Tu análisis es conciso, en español, y siempre devuelves JSON válido."
        )

        text = await self._query_jan(prompt, system_prompt)
        if not text:
            logger.info("Jan unavailable for reflection on %s, trying AIRouter", work_id)
            text = await self._query_router(prompt, system_prompt)

        if not text:
            return None

        try:
            result = json.loads(text)
            if not isinstance(result, dict):
                result = {"analysis": text, "gaps": [], "plot_twists": []}
        except (json.JSONDecodeError, TypeError):
            result = {"analysis": text, "gaps": [], "plot_twists": []}

        result.setdefault("work_id", work_id)
        result.setdefault("gaps", [])
        result.setdefault("plot_twists", [])
        return result

    async def summarize_work(self, work_id: str) -> Optional[str]:
        """Genera un resumen de trama para una obra usando Jan/AIRouter."""
        recent = self._get_recent_canon(work_id, max_events=50)
        if not recent:
            return None

        descriptions = "\n".join(
            f"- {e.get('description', '')}" for e in recent
        )
        prompt = (
            f"Obra: {work_id}\nEventos canónicos:\n{descriptions}\n\n"
            "Genera un resumen conciso (máximo 200 palabras) de la trama principal en español."
        )
        system_prompt = "Eres un asistente narrativo experto en resúmenes literarios."

        text = await self._query_jan(prompt, system_prompt)
        if not text:
            text = await self._query_router(prompt, system_prompt)
        return text


class BackgroundDaemon:
    """Scheduler asyncio con tareas programadas (cron-style).

    Integrado en el ciclo de vida de FastAPI: se inicia con `start()` en startup
    y se detiene con `stop()` en shutdown.
    """

    def __init__(self, ai_router: Any = None) -> None:
        self._tasks: Dict[str, ScheduledTask] = {}
        self._running: bool = False
        self._main_loop_task: Optional[asyncio.Task] = None
        self._reflection_engine = JanReflectionEngine(ai_router=ai_router)
        self._dispatcher = AsyncEventDispatcher()

    def register_task(
        self,
        name: str,
        interval: int,
        func: Callable[[], "Any"],
    ) -> str:
        """Registra una tarea programada."""
        task_id = str(uuid.uuid4())
        self._tasks[task_id] = ScheduledTask(
            task_id=task_id,
            name=name,
            interval=interval,
            func=func,
        )
        logger.info("Scheduled task registered: %s (interval=%ss)", name, interval)
        return task_id

    def unregister_task(self, task_id: str) -> bool:
        """Desregistra una tarea programada."""
        return self._tasks.pop(task_id, None) is not None

    def enable_task(self, task_id: str, enabled: bool = True) -> bool:
        task = self._tasks.get(task_id)
        if task:
            task.enabled = enabled
            return True
        return False

    async def _run_task(self, task: ScheduledTask) -> None:
        """Ejecuta una tarea individual y captura errores."""
        try:
            result = task.func()
            if asyncio.iscoroutine(result):
                await result
            task.run_count += 1
            task.last_error = ""
            logger.debug("Task %s completed (run #%d)", task.name, task.run_count)
        except Exception as exc:
            task.last_error = str(exc)[:200]
            logger.warning("Background task %s failed: %s", task.name, exc)

    async def _main_loop(self) -> None:
        """Loop principal: ejecuta tareas programadas según intervalo."""
        logger.info("BackgroundDaemon main loop started")
        while self._running:
            now = time.time()
            for task in self._tasks.values():
                if not task.enabled:
                    continue
                if now - task.last_run >= task.interval:
                    task.last_run = now
                    await self._run_task(task)
            await asyncio.sleep(5)
        logger.info("BackgroundDaemon main loop stopped")

    def start(self, ai_router: Any = None) -> "BackgroundDaemon":
        """Inicia el daemon y programa las tareas literarias por defecto."""
        if ai_router is not None:
            self._reflection_engine._ai_router = ai_router

        if not self._tasks:
            self._schedule_default_tasks()

        self._running = True
        self._main_loop_task = asyncio.create_task(self._main_loop())
        logger.info("BackgroundDaemon started with %d tasks", len(self._tasks))
        return self

    def _schedule_default_tasks(self) -> None:
        """Programa las tareas literarias de mantenimiento periódico."""
        self.register_task(
            name="coherence_audit",
            interval=DEFAULT_COHERENCE_INTERVAL,
            func=self._run_coherence_audit,
        )
        self.register_task(
            name="jan_reflection",
            interval=DEFAULT_REFLECTION_INTERVAL,
            func=self._run_reflection,
        )
        self.register_task(
            name="plot_summary",
            interval=DEFAULT_SUMMARY_INTERVAL,
            func=self._run_plot_summary,
        )
        self.register_task(
            name="cache_cleanup",
            interval=DEFAULT_CACHE_CLEANUP_INTERVAL,
            func=self._run_cache_cleanup,
        )
        self.register_task(
            name="vault_backup",
            interval=DEFAULT_VAULT_BACKUP_INTERVAL,
            func=self._run_vault_backup,
        )

    async def _run_coherence_audit(self) -> Dict[str, Any]:
        """Audita la coherencia narrativa de todas las obras activas."""
        from backend.story_memory.story_storage import StoryStorage
        works = StoryStorage().list_works()
        results: List[Dict[str, Any]] = []
        for work in works:
            work_id = work.get("work_id") or work.get("id", "")
            if not work_id:
                continue
            events = StoryStorage().get_canon_events(work_id)
            audit = {
                "work_id": work_id,
                "total_events": len(events),
                "gaps_detected": len([e for e in events if not e.get("description")]),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            results.append(audit)
            await self._dispatcher.dispatch_to_websocket(
                "coherence_audit",
                audit,
                work_id=work_id,
            )
        logger.info("Coherence audit completed for %d works", len(results))
        return {"audited_works": len(results), "results": results}

    async def _run_reflection(self) -> None:
        """Ejecuta reflexión narrativa con Jan para cada obra activa."""
        from backend.story_memory.story_storage import StoryStorage
        works = StoryStorage().list_works()
        for work in works:
            work_id = work.get("work_id") or work.get("id", "")
            if not work_id:
                continue
            try:
                result = await self._reflection_engine.reflect_on_work(work_id)
                if result:
                    await self._dispatcher.dispatch_reflection(work_id, result)
                    logger.info("Reflection completed for work_id=%s", work_id)
            except Exception as exc:
                logger.warning("Reflection failed for work_id=%s: %s", work_id, exc)

    async def _run_plot_summary(self) -> None:
        """Genera resúmenes de trama para obras activas."""
        from backend.story_memory.story_storage import StoryStorage
        works = StoryStorage().list_works()
        for work in works:
            work_id = work.get("work_id") or work.get("id", "")
            if not work_id:
                continue
            try:
                summary = await self._reflection_engine.summarize_work(work_id)
                if summary:
                    await self._dispatcher.dispatch_to_websocket(
                        "plot_summary",
                        {"work_id": work_id, "summary": summary},
                        work_id=work_id,
                    )
                    await self._dispatcher.archive_to_discord_vault(
                        work_id=work_id,
                        event_type="plot_summary",
                        payload={"summary": summary},
                    )
                    logger.info("Plot summary generated for work_id=%s", work_id)
            except Exception as exc:
                logger.warning("Plot summary failed for work_id=%s: %s", work_id, exc)

    async def _run_cache_cleanup(self) -> None:
        """Limpia cachés temporales."""
        try:
            from backend.story_memory.canon_tracker import CanonTracker
            ct = CanonTracker()
            ct._cache.clear()
            logger.debug("CanonTracker cache cleared")
        except Exception as exc:
            logger.debug("Cache cleanup skipped: %s", exc)

    async def _run_vault_backup(self) -> None:
        """Respaldo automático a la Bóveda de Discord para obras activas."""
        try:
            from backend.story_memory.story_storage import StoryStorage
            from backend.story_memory.vault_backup import get_vault_backup
            vault = get_vault_backup()
            if not vault.configured:
                logger.debug("Vault backup not configured; skipping")
                return
            works = StoryStorage().list_works()
            for work in works:
                work_id = work.get("work_id") or work.get("id", "")
                if not work_id:
                    continue
                result = vault.push_async(work_id)
                logger.info("Vault backup enqueued for work_id=%s: %s", work_id, result.get("status"))
        except Exception as exc:
            logger.warning("Vault backup task failed: %s", exc)

    async def stop(self) -> None:
        """Detiene el daemon y cancela tasks pendientes."""
        self._running = False
        if self._main_loop_task:
            self._main_loop_task.cancel()
            try:
                await self._main_loop_task
            except asyncio.CancelledError:
                pass
            self._main_loop_task = None
        logger.info("BackgroundDaemon stopped")

    def get_status(self) -> Dict[str, Any]:
        """Estado del daemon y tareas registradas."""
        return {
            "running": self._running,
            "task_count": len(self._tasks),
            "tasks": [
                {
                    "task_id": t.task_id,
                    "name": t.name,
                    "interval": t.interval,
                    "enabled": t.enabled,
                    "last_run": t.last_run,
                    "run_count": t.run_count,
                    "last_error": t.last_error,
                }
                for t in self._tasks.values()
            ],
        }

    @property
    def tasks(self) -> Dict[str, ScheduledTask]:
        return dict(self._tasks)


_agent_scheduler: Optional[BackgroundDaemon] = None


def get_agent_scheduler(ai_router: Any = None) -> BackgroundDaemon:
    """Singleton del BackgroundDaemon."""
    global _agent_scheduler
    if _agent_scheduler is None:
        _agent_scheduler = BackgroundDaemon(ai_router=ai_router)
    elif ai_router is not None:
        _agent_scheduler._reflection_engine._ai_router = ai_router
    return _agent_scheduler


def reset_agent_scheduler() -> None:
    """Reset el singleton (para testing)."""
    global _agent_scheduler
    _agent_scheduler = None
