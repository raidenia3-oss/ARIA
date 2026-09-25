# -*- coding: utf-8 -*-
"""ARIA OS - Unified Orchestrator.

Entry point unico que coordina todos los componentes en paralelo:
Input -> ReceiverHub -> ContextAnalyzer -> DecisionEngine -> Orchestrator
     -> ParallelExecutor -> Swarm -> Memory -> Cognitive Graph -> Output

Emite eventos al EventBus en cada paso para streaming en tiempo real.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Any, Dict, List, Optional

from backend.core.context_analyzer import get_context_analyzer
from backend.core.decision_engine import get_decision_engine
from backend.core.event_bus import CoreEvent, EventBus, EventType, get_event_bus
from backend.core.orchestrator import get_orchestrator
from backend.core.receiver_hub import get_receiver_hub

logger = logging.getLogger("ARIA.UnifiedOrchestrator")


def _etype(evt: CoreEvent) -> str:
    """Normaliza el tipo de evento a string (soporta Enum o str)."""
    t = evt.type
    return t.value if hasattr(t, "value") else str(t)


class UnifiedOrchestrator:
    """Nucleo unificado: coordina todos los componentes en paralelo."""

    def __init__(self, bus: Optional[EventBus] = None) -> None:
        self._bus = bus or get_event_bus()
        self._receiver = get_receiver_hub()
        self._analyzer = get_context_analyzer()
        self._decision_engine = get_decision_engine()
        self._orchestrator = get_orchestrator()
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._running = False
        self._jan_ok: Optional[bool] = None
        # RAG engine (lazy)
        self._rag = None
        # Qwen local LLM (lazy)
        self._qwen_model = None
        self._qwen_tokenizer = None
        self._qwen_ok: Optional[bool] = None

    @property
    def rag(self):
        """Motor RAG avanzado (lazy)."""
        if self._rag is None:
            try:
                from backend.rag_engine_advanced import get_rag

                self._rag = get_rag()
            except Exception as exc:
                logger.debug("RAG init fallo: %s", exc)
                self._rag = False
        return self._rag or None

    async def jan_available(self) -> bool:
        """Verifica si Jan esta disponible (cacheado)."""
        if self._jan_ok is not None:
            return self._jan_ok
        try:
            import httpx

            async with httpx.AsyncClient(timeout=2.0) as c:
                r = await c.get("http://localhost:1337/v1/models")
                self._jan_ok = r.status_code == 200
        except Exception:
            self._jan_ok = False
        return self._jan_ok

    def _ensure_qwen(self) -> bool:
        """Lazy init del modelo Qwen 0.5B local (cacheado).

        Solo se activa con AURA_ENABLE_QWEN=1. Por defecto queda
        deshabilitado para no bloquear el flujo (la descarga pesa ~1GB
        y cuelga el primer process()). Sin Qwen se usa fallback local.
        """
        import os

        if os.getenv("ARIA_ENABLE_QWEN", "0") != "1":
            self._qwen_ok = False
            return False
        if self._qwen_ok is not None:
            return self._qwen_ok
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer

            self._qwen_tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-0.5B-Instruct")
            self._qwen_model = AutoModelForCausalLM.from_pretrained(
                "Qwen/Qwen2.5-0.5B-Instruct",
                torch_dtype=torch.float32,
            )
            self._qwen_ok = True
            logger.info("Qwen 0.5B cargado correctamente")
        except Exception as exc:
            logger.warning("Qwen init fallo: %s", exc)
            self._qwen_ok = False
        return self._qwen_ok

    def _qwen_generate(self, prompt: str, max_tokens: int = 256, temperature: float = 0.7) -> str:
        """Genera texto con Qwen 0.5B."""
        if not self._ensure_qwen():
            return ""
        try:
            import torch

            messages = [
                {
                    "role": "system",
                    "content": "Eres ARIA, un asistente de IA útil y natural. Responde de forma concisa y directa.",
                },
                {"role": "user", "content": prompt},
            ]
            text = self._qwen_tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
            inputs = self._qwen_tokenizer(text, return_tensors="pt")
            with torch.no_grad():
                out = self._qwen_model.generate(
                    **inputs,
                    max_new_tokens=max_tokens,
                    temperature=temperature,
                    do_sample=True,
                    pad_token_id=self._qwen_tokenizer.eos_token_id,
                )
            result = self._qwen_tokenizer.decode(
                out[0][len(inputs["input_ids"][0]) :], skip_special_tokens=True
            )
            return result.strip()
        except Exception as exc:
            logger.debug("qwen generate fallo: %s", exc)
            return ""

    async def process(
        self,
        input_msg: str,
        input_type: str = "chat",
        session_id: str = "",
        source: str = "user",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Orquesta TODO el flujo y retorna resultado completo.

        El input vacio se rechaza con ValueError para que la API
        devuelva 400 (los tests Chunk 1 lo exigen).
        """
        if not (input_msg or "").strip():
            raise ValueError("input vacio: se requiere contenido no vacio")
        t0 = time.time()
        session_id = session_id or f"session-{uuid.uuid4().hex[:8]}"
        meta = dict(metadata or {})
        agents_used: List[str] = []
        memory_trace: List[Dict[str, Any]] = []
        grafo_update: Dict[str, Any] = {}

        self._bus.emit_simple(
            EventType.INPUT.value,
            {
                "input_id": f"in-{uuid.uuid4().hex[:8]}",
                "type": input_type,
                "content": input_msg[:500],
                "source": source,
                "session_id": session_id,
            },
            agent="unified_orchestrator",
            status="received",
        )

        try:
            self._receiver.receive(input_type, input_msg, source, session_id, meta)
        except Exception as exc:
            logger.warning("ReceiverHub fallo: %s", exc)

        self._bus.emit_simple(
            EventType.THOUGHT.value,
            {
                "stage": "context_analyzer_start",
                "session_id": session_id,
            },
            agent="unified_orchestrator",
            status="running",
        )

        analysis = self._analyzer.analyze(
            prompt=input_msg,
            session_id=session_id,
            input_type=input_type,
            metadata=meta,
        )
        self._bus.emit_simple(
            EventType.THOUGHT.value,
            {
                "stage": "context_analyzed",
                "urgencia": analysis.get("urgencia"),
                "tipo": analysis.get("tipo"),
                "dominio": analysis.get("dominio"),
                "session_id": session_id,
            },
            agent="unified_orchestrator",
            status="analyzed",
        )

        # --- RAG: buscar contexto semántico antes de decidir ---
        context_used: List[Dict[str, Any]] = []
        rag_context_str = ""
        rag = self.rag
        if rag is not None:
            try:
                context_used = rag.search(input_msg, top_k=5, min_similarity=0.3)
                rag_context_str = rag.build_context(input_msg, top_k=5, min_similarity=0.3)
                if context_used:
                    self._bus.emit_simple(
                        EventType.THOUGHT.value,
                        {
                            "stage": "rag_context_found",
                            "hits": len(context_used),
                            "session_id": session_id,
                        },
                        agent="unified_orchestrator",
                        status="retrieved",
                    )
            except Exception as exc:
                logger.debug("RAG search fallo: %s", exc)

        self._bus.emit_simple(
            EventType.THOUGHT.value,
            {
                "stage": "decision_start",
                "session_id": session_id,
            },
            agent="unified_orchestrator",
            status="running",
        )

        # Enriquecer prompt con contexto RAG
        enriched = analysis.get("enriched_prompt", input_msg)
        if rag_context_str:
            enriched = f"{rag_context_str}\n\n[CONSULTA ACTUAL]\n{input_msg}"

        decision = self._decision_engine.decide(
            enriched_prompt=enriched,
            context=analysis.get("contexto", {}),
            session_id=session_id,
        )
        # decision es un dict con: decision, plan, agents, rationale, priority, used_jan, engine, latency_ms
        dec = decision.get("decision", {}) if isinstance(decision, dict) else {}
        plan = decision.get("plan", []) if isinstance(decision, dict) else []
        agents = decision.get("agents", []) if isinstance(decision, dict) else []
        rationale = decision.get("rationale", "") if isinstance(decision, dict) else ""
        used_jan = decision.get("used_jan", False) if isinstance(decision, dict) else False
        engine = decision.get("engine", "unknown") if isinstance(decision, dict) else "unknown"

        self._bus.emit_simple(
            EventType.DECISION.value,
            {
                "stage": "decision_generated",
                "type": dec.get("type", "task") if isinstance(dec, dict) else "task",
                "plan_steps": len(plan),
                "agents": agents,
                "rationale": (rationale or "")[:120],
                "engine": engine,
                "used_jan": used_jan,
                "session_id": session_id,
            },
            agent="unified_orchestrator",
            status="decided",
        )

        # Construir assignment a partir del plan retornado por el DecisionEngine
        steps = []
        for item in plan:
            if isinstance(item, dict):
                steps.append(
                    {
                        "step": item.get("step", 0),
                        "description": item.get("description", ""),
                        "agent": item.get("agent", "executor_agent"),
                        "tool": item.get("tool", "execute"),
                        "params": item.get("params", {}),
                    }
                )
        assignment = {
            "steps": steps,
            "agents": agents,
            "total_steps": len(steps),
            "session_id": session_id,
        }
        agents_used = list(agents)

        self._bus.emit_simple(
            EventType.ACTION.value,
            {
                "stage": "parallel_execution_start",
                "total_steps": assignment.get("total_steps", 0),
                "agents": agents_used,
                "session_id": session_id,
            },
            agent="unified_orchestrator",
            status="running",
        )

        step_results = await self._run_agents_parallel(assignment, session_id)

        # Generar respuesta usando el motor de IA (ai_router o local_llm_engine)
        response_text = await self._generate_response(
            input_msg, analysis, decision, step_results, context_used
        )

        try:
            from backend.memory.manager import get_memory_manager

            mm = get_memory_manager()
            if mm:
                mm.store(
                    f"session-{session_id[:8]}",
                    f"User: {input_msg}\nAURA: {step_results.get('output', '')}",
                    level="short",
                    source="unified_orchestrator",
                    metadata={"session_id": session_id, "tipo": analysis.get("tipo", "general")},
                )
                memory_trace.append({"stage": "memory_write", "ok": True})
        except Exception as exc:
            memory_trace.append({"stage": "memory_write", "ok": False, "error": str(exc)})

        try:
            from backend.memory.cognitive_graph import get_cognitive_graph

            cg = get_cognitive_graph()
            if cg and response_text:
                cg.ingest(
                    f"User: {input_msg}\nAURA: {response_text}",
                    source="unified_orchestrator",
                    kind="session",
                    summary=f"session-{session_id[:8]}: {response_text[:200]}",
                    metadata={
                        "session_id": session_id,
                        "tags": ["session", analysis.get("tipo", "general")],
                    },
                )
                grafo_update = {"node_added": True, "session_id": session_id}
        except Exception as exc:
            grafo_update = {"node_added": False, "error": str(exc)}

        # Indexar conversación en RAG para búsquedas futuras
        if rag is not None and response_text:
            try:
                rag.index(
                    text=f"User: {input_msg}\nAURA: {response_text}",
                    chat_id=session_id,
                    metadata={"tipo": analysis.get("tipo", "general")},
                )
            except Exception as exc:
                logger.debug("RAG index fallo: %s", exc)

        duration_ms = round((time.time() - t0) * 1000, 2)
        response = {
            "response": response_text,
            "status": "success",
            "duration_ms": duration_ms,
            "agents_used": agents_used,
            "grafo_update": grafo_update,
            "memory_trace": memory_trace,
            "context_used": context_used,
            "session_id": session_id,
            "analysis": {
                "urgencia": analysis.get("urgencia"),
                "tipo": analysis.get("tipo"),
                "dominio": analysis.get("dominio"),
            },
            "decision": {
                "type": dec.get("type", "task") if isinstance(dec, dict) else "task",
                "plan_steps": len(plan),
                "rationale": (rationale or "")[:200],
                "engine": engine,
                "used_jan": used_jan,
            },
            "step_results": step_results.get("steps", []),
        }

        self._bus.emit_simple(
            EventType.RESULT.value,
            {
                "stage": "orchestrator_result",
                "session_id": session_id,
                "duration_ms": duration_ms,
                "response_preview": str(response)[:200],
            },
            agent="unified_orchestrator",
            status="completed",
        )

        self._bus.emit_simple(
            EventType.COMPLETE.value,
            {
                "stage": "orchestrator_complete",
                "session_id": session_id,
                "duration_ms": duration_ms,
                "agents_used": agents_used,
            },
            agent="unified_orchestrator",
            status="completed",
        )

        logger.info(
            "unified_orchestrator: session=%s agents=%d latency=%sms",
            session_id,
            len(agents_used),
            duration_ms,
        )
        return response

    async def _generate_response(
        self,
        input_msg: str,
        analysis: Dict[str, Any],
        decision: Dict[str, Any],
        step_results: Dict[str, Any],
        context_used: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Genera texto de respuesta usando Qwen (local), Jan, o fallback local."""
        # 1. Si hay output de los pasos, usarlo
        output = step_results.get("output", "")
        if output and isinstance(output, str) and len(output.strip()) > 3:
            return output[:2000]

        # 2. Construir prompt enriquecido con contexto RAG
        system_msg = "Eres ARIA, un asistente de IA útil, natural y conciso. Responde en español."
        user_content = input_msg
        if context_used:
            ctx_lines = []
            for h in context_used[:3]:
                snippet = h.get("snippet", "")[:200]
                sim = h.get("similarity", 0)
                ctx_lines.append(f"- (sim={sim:.2f}) {snippet}")
            if ctx_lines:
                user_content = (
                    f"[CONTEXTO DE CONVERSACIONES PREVIAS]\n{chr(10).join(ctx_lines)}\n\n"
                    f"[CONSULTA ACTUAL]\n{input_msg}\n\n"
                    f"Responde de forma personalizada usando el contexto si es relevante."
                )

        # 3. Intentar con Qwen 0.5B local (primero, porque es local y rápido)
        qwen_text = self._qwen_generate(user_content, max_tokens=256, temperature=0.7)
        if qwen_text and len(qwen_text.strip()) > 3:
            return qwen_text[:2000]

        # 4. Intentar con Jan (OpenAI-compat en localhost:1337)
        try:
            if await self.jan_available():
                import httpx

                async with httpx.AsyncClient(timeout=15.0) as c:
                    r = await c.post(
                        "http://localhost:1337/v1/chat/completions",
                        json={
                            "model": "gemma-3-1b-it",
                            "messages": [
                                {"role": "system", "content": system_msg},
                                {"role": "user", "content": user_content},
                            ],
                            "max_tokens": 512,
                            "temperature": 0.7,
                        },
                    )
                    if r.status_code == 200:
                        data = r.json()
                        text = data["choices"][0]["message"]["content"]
                        if text:
                            return text.strip()[:2000]
        except Exception as exc:
            logger.debug("Jan fallo en generate_response: %s", exc)

        # 5. Fallback local para chat
        tipo = analysis.get("tipo", "general")
        if tipo == "chat" or not step_results.get("steps"):
            return self._local_chat_fallback(input_msg, analysis, decision, context_used)
        rationale = (decision.get("rationale", "") if isinstance(decision, dict) else "") or ""
        return rationale[:500] if rationale else "Procesado sin respuesta de texto."

    def _local_chat_fallback(
        self,
        input_msg: str,
        analysis: Dict[str, Any],
        decision: Dict[str, Any],
        context_used: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Respuesta local cuando no hay Jan ni pasos de ejecucion."""
        msg = input_msg.strip().lower()

        # Si hay contexto RAG, generamos respuesta personalizada
        if context_used:
            top = context_used[0]
            return (
                f"Basado en conversaciones previas (similitud {top['similarity']:.2f}), "
                f"encontré: \"{top['snippet'][:120]}\". "
                f"Te recomiendo explorar ese tema. ¿Necesitas mas ayuda?"
            )

        # Saludos
        for greet in ["hola", "hello", "hi", "buenos dias", "buenas"]:
            if msg.startswith(greet) or msg == greet:
                return "Hola, soy AURA. Estoy en modo local en este momento. ¿En que te ayudo?"
        if msg in ["¿cómo estás?", "como estas?", "como estas"]:
            return "Estoy funcionando en modo local. ¿Hay algo quieras que haga?"
        if msg.endswith("?") or any(w in msg for w in ["que", "como", "por que", "porque"]):
            return "Estoy en modo local sin modelo LLM activo. Puedo ayudarte con comandos de sistema, busquedas web, archivos y mas. Prueba: 'busca informacion sobre Python' o 'lista los archivos del escritorio'."
        # Respuesta genérica
        return "Recibí tu mensaje pero el motor de IA local no esta disponible. Puedo ejecutar comandos directos: 'busca web:', 'abre archivo:', 'lista archivos:', 'escribe archivo:', 'ejecuta:'."

    async def _run_agents_parallel(
        self, assignment: Dict[str, Any], session_id: str
    ) -> Dict[str, Any]:
        """Ejecuta los pasos del plan en paralelo vía ParallelExecutor + Swarm."""
        steps = assignment.get("steps", [])
        results: Dict[str, Any] = {"output": "", "steps": []}

        try:
            from backend.core.parallel_executor import get_parallel_executor

            pe = get_parallel_executor()
            exec_result = await pe.execute(assignment, session_id=session_id)
            results["steps"] = exec_result.get("step_results", [])
            results["output"] = exec_result.get("output", "")
            return results
        except Exception as exc:
            logger.debug("ParallelExecutor fallo: %s", exc)

        for step in steps:
            agent_name = step.get("agent", "executor_agent")
            try:
                mod = self._import_agent(agent_name)
                if mod and hasattr(mod, "execute"):
                    step_result = await mod.execute(step.get("params", {}))
                    step["result"] = step_result
                    step["status"] = "completed"
                    results["steps"].append(step)
                    if not results["output"]:
                        results["output"] = str(step_result.get("output", step_result))[:500]
            except Exception as exc:
                step["status"] = "failed"
                step["error"] = str(exc)
                results["steps"].append(step)
        return results

    def _fallback_assignment(self, decision: Any, session_id: str) -> Dict[str, Any]:
        """Construye un assignment basico cuando el Orchestrator falla."""
        steps = []
        for i, step in enumerate(getattr(decision, "plan", [])):
            if hasattr(step, "model_dump"):
                steps.append(step.model_dump())
            elif isinstance(step, dict):
                steps.append(step)
            else:
                steps.append(
                    {
                        "step": i + 1,
                        "description": str(step),
                        "agent": "executor_agent",
                        "tool": "execute",
                        "params": {},
                    }
                )
        return {
            "steps": steps,
            "agents": list(getattr(decision, "agents", [])),
            "total_steps": len(steps),
            "session_id": session_id,
        }

    def _import_agent(self, name: str):
        """Importa un agente por nombre dinamico."""
        mapping = {
            "rag_agent": "backend.agent.rag_agent",
            "writer_agent": "backend.agent.writer_agent",
            "executor_agent": "backend.agent.executor_agent",
        }
        modname = mapping.get(name)
        if not modname:
            return None
        try:
            import importlib

            return importlib.import_module(modname)
        except Exception:
            return None

    async def get_status(self, session_id: str = "") -> Dict[str, Any]:
        """Estado actual del orquestador."""
        jan = await self.jan_available()
        return {
            "status": "ok",
            "jan_available": jan,
            "sessions": len(self._sessions),
            "session_id": session_id,
            "timestamp": time.time(),
        }


_orchestrator: Optional[UnifiedOrchestrator] = None


def get_unified_orchestrator() -> UnifiedOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = UnifiedOrchestrator()
    return _orchestrator


def reset_unified_orchestrator() -> None:
    global _orchestrator
    _orchestrator = None
