# -*- coding: utf-8 -*-
"""
AURA OS — Chunk 1: Core Decision Engine.

Motor de decisión que consulta a Jan (OpenAI-compat, localhost:1337)
y genera un plan de pasos + asignación de agentes.
Si Jan no está disponible, usa un planner local (fallback).

Flujo:
  contexto → prompt enriquecido → jan (o fallback) → decision → event bus
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

import httpx

from backend.core.event_bus import CoreEvent, EventType, get_event_bus
from backend.core.models import Decision, DecisionStep, DecisionType

logger = logging.getLogger("AURA.DecisionEngine")

# ------------------------------------------------------------------
# Configuración
# ------------------------------------------------------------------

JAN_BASE_URL = "http://localhost:1337/v1"
JAN_TIMEOUT = float(os.getenv("JAN_TIMEOUT", "10"))  # segundos (configurable)
FALLBACK_MAX_STEPS = 6
JAN_MODEL = os.getenv("JAN_MODEL", "gemma-3-1b-it")  # modelo servido por Jan


class DecisionEngine:
    """
    Consulta el modelo Jan (OpenAI-compat) y retorna una decisión
    estructurada. Si Jan no responde, usa el planner local (fallback).
    """

    def __init__(
        self,
        jan_url: str = JAN_BASE_URL,
        timeout: float = JAN_TIMEOUT,
        fallback_max_steps: int = FALLBACK_MAX_STEPS,
    ) -> None:
        self.jan_url = jan_url.rstrip("/")
        self.timeout = timeout
        self.fallback_max_steps = max(1, fallback_max_steps)
        self._bus = get_event_bus()
        self._http: Optional[httpx.Client] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def attach(self, bus: Any = None) -> None:
        """Crea el cliente HTTP hacia Jan."""
        if bus is not None:
            self._bus = bus
        if self._http is None:
            self._http = httpx.Client(
                base_url=self.jan_url,
                timeout=httpx.Timeout(self.timeout, connect=3.0),
            )

    def detach(self) -> None:
        if self._http is not None:
            self._http.close()
            self._http = None

    # ------------------------------------------------------------------
    # Público
    # ------------------------------------------------------------------
    def decide(
        self,
        enriched_prompt: str,
        context: Optional[Dict[str, Any]] = None,
        session_id: str = "",
    ) -> Dict[str, Any]:
        """
        Genera una decisión (plan) a partir de un prompt enriquecido.
        Retorna: decision, plan, agents, used_jan, latency_ms, session_id.
        """
        t0 = time.time()
        self._bus.emit(CoreEvent(
            type=EventType.THOUGHT,
            data={"session_id": session_id, "prompt_preview": (enriched_prompt or "")[:80]},
            agent="decision_engine",
            status="planning",
        ))

        decision = self._call_engine(enriched_prompt or "", context or {}, session_id)
        latency_ms = (time.time() - t0) * 1000.0

        self._bus.emit(CoreEvent(
            type=EventType.DECISION,
            data={
                "session_id": session_id,
                "decision_type": decision.type.value,
                "steps": len(decision.plan),
                "agents": decision.agents,
            },
            agent="decision_engine",
            status="planned",
        ))

        used_jan = decision.type != DecisionType.FALLBACK
        return {
            "decision": decision.model_dump(),
            "plan": [step.model_dump() for step in decision.plan],
            "agents": decision.agents,
            "rationale": decision.rationale,
            "priority": decision.priority,
            "used_jan": used_jan,
            "engine": "jan" if used_jan else "local_fallback",
            "latency_ms": round(latency_ms, 2),
            "session_id": session_id,
        }

    # ------------------------------------------------------------------
    # Interno: Jan o fallback
    # ------------------------------------------------------------------
    def _call_engine(self, prompt: str, context: Dict[str, Any], session_id: str) -> Decision:
        if self._http is None:
            self.attach()
        try:
            payload = self._build_jan_payload(prompt, context, session_id)
            choice = self._query_jan(payload)
            return self._parse_jan_response(choice)
        except Exception as exc:  # noqa: BLE001 — Jan puede estar offline
            logger.warning("Jan no disponible (%s). Usando planner local.", exc)
            self._bus.emit(CoreEvent(
                type=EventType.ERROR,
                data={"error": str(exc), "fallback": "local_planner"},
                agent="decision_engine",
                status="degraded",
            ))
            return self._fallback_decision(prompt, context, session_id)


    # ------------------------------------------------------------------
    # Consulta a Jan
    # ------------------------------------------------------------------
    def _query_jan(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """POST /v1/chat/completions a Jan."""
        assert self._http is not None, "DecisionEngine no inicializado"
        resp = self._http.post("/chat/completions", json=payload)
        resp.raise_for_status()
        body = resp.json()
        choices = body.get("choices") or []
        if not choices:
            raise RuntimeError("Jan devolvió choices vacío")
        return choices[0]

    def _build_jan_payload(self, prompt: str, context: Dict[str, Any], session_id: str) -> Dict[str, Any]:
        system_message = (
            "Eres el motor de decisión de AURA OS.\n"
            "Analiza la solicitud y el contexto, y devuelve un plan de acción.\n"
            "Responde SOLO con JSON válido:\n"
            "{\n"
            '  "rationale": "razón concisa",\n'
            '  "plan": [{"step": 1, "description": "...", "agent": "...", "tool": "...", "params": {}}],\n'
            '  "agents": ["agent1"],\n'
            '  "priority": 0.5\n'
            "}\n"
            "tool en {execute, search, web, files, memory, system}.\n"
            "priority es float 0.0-1.0."
        )
        user_message = (
            f"SESION: {session_id}\n"
            f"CONTEXTO:\n{json.dumps(context, ensure_ascii=False, indent=2, default=str)}\n"
            f"SOLICITUD:\n{prompt}"
        )
        return {
            "model": JAN_MODEL,
            "messages": [
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message},
            ],
            "max_tokens": 1024,
            "temperature": 0.2,
        }

    # ------------------------------------------------------------------
    # Parseo de respuesta
    # ------------------------------------------------------------------
    def _parse_jan_response(self, choice: Dict[str, Any]) -> Decision:
        message = choice.get("message") or {}
        content = (message.get("content") or "").strip()
        if not content:
            raise RuntimeError("Jan devolvió contenido vacío")
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            logger.debug("Respuesta de Jan no es JSON; parseo textual.")
            return self._parse_loose(content)
        return self._build_decision_from_json(data)

    def _build_decision_from_json(self, data: Dict[str, Any]) -> Decision:
        plan_raw = data.get("plan") or data.get("steps") or []
        agents_raw = data.get("agents") or []
        try:
            priority = float(data.get("priority", 0.6))
        except (TypeError, ValueError):
            priority = 0.6
        rationale = data.get("rationale") or data.get("reasoning") or "Plan generado por Jan"

        steps: List[DecisionStep] = []
        for i, item in enumerate(plan_raw[: self.fallback_max_steps]):
            if not isinstance(item, dict):
                continue
            steps.append(DecisionStep(
                step=i + 1,
                description=str(item.get("description") or item.get("task") or ""),
                agent=item.get("agent") or None,
                tool=item.get("tool") or "execute",
                params=item.get("params") or {},
            ))

        if not steps:
            raise RuntimeError("Jan no produjo pasos válidos")

        if isinstance(agents_raw, str):
            agents_raw = [agents_raw]
        agents = [a for a in (agents_raw or []) if isinstance(a, str)]
        if not agents:
            agents = sorted({s.agent for s in steps if s.agent})

        return Decision(
            type=DecisionType.PLAN,
            plan=steps,
            rationale=str(rationale),
            agents=agents,
            priority=min(1.0, max(0.0, priority)),
        )

    # ------------------------------------------------------------------
    # Parseo textual (Jan devolvió texto libre)
    # ------------------------------------------------------------------
    def _parse_loose(self, text: str) -> Decision:
        steps: List[DecisionStep] = []
        for line in text.splitlines():
            stripped = line.strip()
            low = stripped.lower()
            if low.startswith(("paso", "step", "- ", "* ")):
                clean = stripped.lstrip("-* ").strip()
                idx = clean.find(":")
                desc = clean[idx + 1:].strip() if idx > 0 else clean
                if not desc:
                    continue
                steps.append(DecisionStep(
                    step=len(steps) + 1,
                    description=desc,
                    agent="local_planner",
                    tool="execute",
                    params={},
                ))
            if len(steps) >= self.fallback_max_steps:
                break

        if not steps:
            raise RuntimeError("No se pudo extraer plan de la respuesta textual")

        return Decision(
            type=DecisionType.PLAN,
            plan=steps,
            rationale="Plan extraído textualmente de la respuesta de Jan",
            agents=["jan"],
            priority=0.6,
        )

    # ------------------------------------------------------------------
    # Fallback local (Jan offline)
    # ------------------------------------------------------------------
    def _fallback_decision(self, prompt: str, context: Dict[str, Any], session_id: str) -> Decision:
        """Planner heurístico local, sin dependencia de Jan."""
        # Preferir el prompt crudo del usuario si el ContextAnalyzer lo adjuntó
        raw = context.get("prompt") if isinstance(context, dict) else None
        low = (raw or prompt or "").lower()
        steps: List[DecisionStep] = []

        if any(k in low for k in ("archivo", "fichero", "file", "carpeta", "leer", "escribir")):
            steps.append(DecisionStep(step=1, description="Localizar/leer el archivo solicitado",
                                      agent="file_agent", tool="files", params={"prompt": prompt}))
            steps.append(DecisionStep(step=2, description="Procesar el contenido y responder",
                                      agent="analysis_agent", tool="memory", params={}))
        elif any(k in low for k in ("buscar", "search", "web", "internet", "google", "clima", "weather")):
            steps.append(DecisionStep(step=1, description="Ejecutar búsqueda web",
                                      agent="web_agent", tool="web", params={"query": prompt}))
            steps.append(DecisionStep(step=2, description="Resumir y validar resultados",
                                      agent="analysis_agent", tool="memory", params={}))
        elif any(k in low for k in ("sistema", "cpu", "ram", "memoria", "status", "estado", "hora")):
            steps.append(DecisionStep(step=1, description="Consultar estado del sistema",
                                      agent="system_agent", tool="system", params={}))
            steps.append(DecisionStep(step=2, description="Formatear respuesta al usuario",
                                      agent="analysis_agent", tool="memory", params={}))
        else:
            steps.append(DecisionStep(step=1, description="Analizar la solicitud del usuario",
                                      agent="analysis_agent", tool="memory",
                                      params={"prompt": raw or prompt,
                                              "context_keys": sorted(context.keys())}))
            steps.append(DecisionStep(step=2, description="Ejecutar la acción principal",
                                      agent="executor_agent", tool="execute",
                                      params={"prompt": raw or prompt, "session_id": session_id}))

        return Decision(
            type=DecisionType.FALLBACK,
            plan=steps,
            rationale=(
                "Jan no disponible en {} — plan generado por planner local "
                "(urgencia/dominio ya calculados por ContextAnalyzer)".format(self.jan_url)
            ),
            agents=["local_planner"],
            priority=0.4,
        )

    # ------------------------------------------------------------------
    # Salud de Jan
    # ------------------------------------------------------------------
    def jan_health(self) -> Dict[str, Any]:
        if self._http is None:
            self.attach()
        try:
            assert self._http is not None
            resp = self._http.get("/models", timeout=2.0)
            resp.raise_for_status()
            body = resp.json()
            models = [m.get("id") for m in (body.get("data") or []) if isinstance(m, dict)]
            return {"available": True, "url": self.jan_url, "models": models[:10]}
        except Exception as exc:  # noqa: BLE001
            return {"available": False, "url": self.jan_url, "error": str(exc)}


# ------------------------------------------------------------------
# Singleton
# ------------------------------------------------------------------

_engine: Optional[DecisionEngine] = None


def get_decision_engine() -> DecisionEngine:
    global _engine
    if _engine is None:
        _engine = DecisionEngine()
    return _engine


def reset_decision_engine() -> None:
    global _engine
    if _engine is not None:
        _engine.detach()
    _engine = None
