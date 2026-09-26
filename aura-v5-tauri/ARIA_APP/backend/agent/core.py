"""ARIA ReAct Loop Core — Plan → Validate → Execute → Synthesize."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from backend.plugins import plugin_manager


@dataclass
class ReActState:
    session_id: str
    user_message: str
    plan: List[str] = field(default_factory=list)
    executed_steps: List[Dict[str, Any]] = field(default_factory=list)
    validation_errors: List[str] = field(default_factory=list)
    final_response: str = ""
    provider: str = "local"
    latency_ms: float = 0.0
    created_at: float = field(default_factory=time.time)


class ReactLoop:
    def __init__(self, skill_registry: Any, memory: Any, ai_manager: Any) -> None:
        self.skill_registry = skill_registry
        self.memory = memory
        self.ai_manager = ai_manager

    def run(self, user_message: str, system_prompt: str = "") -> Dict[str, Any]:
        session_id = str(uuid.uuid4())
        state = ReActState(session_id=session_id, user_message=user_message)
        start = time.time()
        try:
            plan = self._plan(user_message, system_prompt)
            state.plan = plan
            validation = self._validate(plan)
            state.validation_errors = validation.get("errors", [])
            if state.validation_errors:
                state.final_response = "; ".join(state.validation_errors)
            else:
                execution = self._execute(plan, user_message)
                state.executed_steps = execution.get("steps", [])
                state.final_response = self._synthesize(state, system_prompt)
        except Exception as e:
            state.final_response = f"Error en el ciclo ReAct: {e}"
        state.latency_ms = round((time.time() - start) * 1000, 2)
        try:
            provider = getattr(self.ai_manager, "providers", {})
            best = None
            for name, info in provider.items():
                if info.get("available") and not self._is_circuit_open(self.ai_manager, name):
                    best = name
                    break
            state.provider = best or "local"
        except Exception:
            state.provider = "local"
        try:
            self.memory.save_interaction(
                user_message,
                state.final_response,
                meta={
                    "provider": state.provider,
                    "plan": state.plan,
                    "steps": state.executed_steps,
                    "validation_errors": state.validation_errors,
                    "latency_ms": state.latency_ms,
                },
            )
        except Exception:
            pass
        return {
            "session_id": state.session_id,
            "response": state.final_response,
            "provider": state.provider,
            "latency": state.latency_ms,
            "plan": state.plan,
            "executed_steps": state.executed_steps,
            "validation_errors": state.validation_errors,
        }

    def _plan(self, user_message: str, system_prompt: str) -> List[str]:
        text = user_message.lower()
        steps: List[str] = []
        if any(k in text for k in ["estado", "status", "cpu", "ram", "disco"]):
            steps.append("skill:status")
        if any(k in text for k in ["hora", "time", "fecha"]):
            steps.append("skill:time")
        if any(k in text for k in ["ping"]):
            steps.append("skill:ping")
        if any(k in text for k in ["escanear", "scan", "puertos"]):
            steps.append("skill:scan")
        if any(k in text for k in ["buscar", "whois", "dominio"]):
            steps.append("skill:whois")
        if any(k in text for k in ["clima", "weather", "temperatura"]):
            steps.append("skill:weather")
        if any(k in text for k in ["abrir", "abre", "open", "app", "launch", "ejecutar"]):
            steps.append("skill:open")
        if any(k in text for k in ["volumen", "volume"]):
            steps.append("skill:volume")
        if any(k in text for k in ["captura", "screenshot", "pantalla"]):
            steps.append("skill:screenshot")
        if any(k in text for k in ["memoria", "memory", "recordatorio", "recordar"]):
            steps.append("skill:memory")
        if any(k in text for k in ["bloquear", "lock", "cerrar sesión"]):
            steps.append("skill:lock")
        if any(k in text for k in ["procesos", "aplicaciones", "apps corriendo"]):
            steps.append("skill:apps")
        if any(k in text for k in ["controlar", "control", "mouse", "teclado", "click", "digitar", "escribir", "mover"]):
            steps.append("skill:control")
        if any(k in text for k in ["archivo", "archivos", "carpeta", "directorio", "explorar", "listar", "lista", "arbol", "tree"]):
            steps.append("skill:explorer")
        if any(k in text for k in ["ejecutar", "ejecución", "código", "programa", "script", "python"]) and any(k in text for k in ["=", ">>", "print", "def ", "import"]):
            steps.append("skill:code_exec")
        if any(k in text for k in ["navegador", "browser", "abrir web", "webpage", "navega"]):
            steps.append("skill:automation")
        if not steps:
            steps.append("ai:chat")
        return steps

    def _validate(self, plan: List[str]) -> Dict[str, Any]:
        errors: List[str] = []
        for step in plan:
            if not step or ":" not in step:
                errors.append(f"Paso inválido: {step}")
                continue
            if step.startswith("skill:"):
                skill = step.split(":", 1)[1]
                if not self.skill_registry.has(skill):
                    errors.append(f"Skill no encontrada: {skill}")
        return {"valid": not errors, "errors": errors}

    def _execute(self, plan: List[str], user_message: str) -> Dict[str, Any]:
        steps: List[Dict[str, Any]] = []
        context = {"user_message": user_message}
        for step in plan:
            if step == "ai:chat":
                result = self._ai_chat(user_message, context)
                steps.append({"step": step, "result": result})
                continue
            skill_name = step.split(":", 1)[1]
            params = self._extract_params(user_message, skill_name)
            plugin_manager.execute_hook("on_skill_execute", skill_name, params)
            result = self.skill_registry.run(skill_name, params)
            steps.append({"step": step, "params": params, "result": result})
        return {"steps": steps, "context": context}

    def _synthesize(self, state: ReActState, system_prompt: str) -> str:
        if state.executed_steps:
            last = state.executed_steps[-1]
            result = last.get("result", {})
            if isinstance(result, dict):
                if result.get("response"):
                    return result["response"]
                if result.get("result"):
                    inner = result["result"]
                    if isinstance(inner, dict):
                        if inner.get("time"):
                            return f"Son las {inner['time']} del {inner.get('date', '')}."
                        if inner.get("cpu") is not None or "backend" in inner:
                            return f"Sistema: CPU {inner.get('cpu','')}, memoria {inner.get('memory','')}, disco {inner.get('disk','')}. Backend {inner.get('backend','')}."
                        if inner.get("matches") is not None:
                            return f"Encontré {inner['matches']} coincidencia(s) en memoria."
                        if inner.get("host"):
                            return f"Ping a {inner['host']}: {inner.get('status','?')}."
                        if inner.get("opened") is not None:
                            return (
                                f"Abriendo {inner.get('opened')}..."
                                if inner.get("opened")
                                else "¿Qué aplicación quieres abrir?"
                            )
                        if inner.get("action") == "lock":
                            return (
                                "Bloqueando pantalla."
                                if inner.get("status") == "ok"
                                else "No se pudo bloquear."
                            )
                        if inner.get("apps") is not None:
                            return f"Hay {inner.get('count', 0)} procesos corriendo."
                        if inner.get("total") is not None:
                            return f"Archivos: {inner.get('count', 0)} encontrados en {inner.get('path', '...')}"
                        if inner.get("tree"):
                            return f"Estructura:\n{inner['tree']}"
                        if inner.get("status") == "ok" and inner.get("stdout") is not None:
                            output = inner["stdout"][:500]
                            return f"Ejecutado ({inner.get('duration_ms', '?')}ms):\n{output}"
                        if inner.get("status") == "ok" and inner.get("url") is not None:
                            return f"Abriendo: {inner.get('url')} - {inner.get('title', '')}"
                        if inner.get("screenshot"):
                            return "Captura de pantalla guardada."
                        if inner.get("open_ports") is not None:
                            return f"Puertos abiertos en {inner.get('host','localhost')}: {inner['open_ports']}."
                        if inner.get("volume") is not None:
                            return (
                                f"Volumen: {inner['volume']}, muteado: {inner.get('muted', False)}."
                            )
                        if inner.get("temp_c"):
                            return f"Clima en {inner.get('city')}: {inner['temp_c']}°C, {inner.get('condition')}."
                if result.get("skill"):
                    return f"Skill '{result['skill']}' ejecutada correctamente."
        try:
            ai = self.ai_manager.chat(
                state.user_message,
                system_prompt=system_prompt
                or "Eres ARIA, un asistente personal. Responde en español, conciso.",
            )
            return ai.get("message") or ai.get("response") or "Sin respuesta."
        except Exception as e:
            return f"Error IA: {e}"

    def _ai_chat(self, user_message: str, context: Dict[str, Any]) -> Dict[str, Any]:
        try:
            return self.ai_manager.chat(
                user_message,
                system_prompt="Eres ARIA, un asistente personal avanzado. Responde en español de forma concisa y útil.",
            )
        except Exception as e:
            return {"error": str(e), "message": f"Error en motor IA: {e}"}

def _extract_params(self, user_message: str, skill_name: str) -> Dict[str, Any]:
    text = user_message.lower()
    params: Dict[str, Any] = {}
    if skill_name == "whois":
        words = text.split()
        candidates = [w for w in words if "." in w and len(w) > 3]
        params["domain"] = candidates[0] if candidates else "example.com"
    if skill_name == "open":
        words = text.split()
        candidates = [
            w for w in words
            if len(w) > 2 and w not in {"abrir", "abre", "open", "app", "launch", "ejecutar"}
        ]
        params["app"] = candidates[0] if candidates else ""
    if skill_name == "control":
        params["action"] = "mouse_click"
        params["x"] = params.get("x", 500)
        params["y"] = params.get("y", 400)
    if skill_name == "explorer":
        params["path"] = params.get("path", ".")
        params["max_depth"] = params.get("max_depth", 2)
    if skill_name == "code_exec":
        params["action"] = "execute"
    if skill_name == "automation":
        params["action"] = "playwright_navigate"
        params["url"] = params.get("url", "")
    if skill_name == "weather":
        for city in ["buenos aires", "madrid", "ciudad de méxico", "new york", "london"]:
            if city in text:
                params["city"] = city
                break
        params.setdefault("city", "Buenos Aires")
    if skill_name == "memory":
        params["query"] = user_message
    return params

    @staticmethod
    def _is_circuit_open(manager: Any, provider: str) -> bool:
        cb = getattr(manager, "_circuit_breaker", {}).get(provider)
        if not cb:
            return False
        if time.time() - cb.get("last_failure", 0) > 30:
            return False
        return cb.get("failures", 0) >= 3
