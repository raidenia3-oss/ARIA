"""Unified Swarm Orchestrator for AURA.

Combines in real time:
- RAG memory context
- Vision descriptions
- System telemetry
- Tool registry / function calling
into a unified system prompt before model inference.
Also implements dynamic model fallback between local Ollama and remote APIs.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger("AURASwarmOrchestrator")

DEFAULT_SYSTEM_PROMPT = """Eres AURA, un asistente avanzado con memoria, vision y control del sistema.
Responde en español de forma concisa y accionable."""

MODEL_FALLBACK_CHAIN = [
    {"provider": "ollama", "model": "llama3.2:latest", "timeout": 20},
    {"provider": "ollama", "model": "llama3.1:latest", "timeout": 20},
    {"provider": "remote", "model": "gpt-3.5-turbo", "timeout": 15},
    {"provider": "remote", "model": "gpt-4o-mini", "timeout": 15},
]


class SwarmOrchestrator:
    def __init__(self) -> None:
        self._system_prompt: str = DEFAULT_SYSTEM_PROMPT
        self._context: Dict[str, Any] = {
            "memory": [],
            "vision": [],
            "telemetry": {},
            "tools": [],
            "actions": [],
        }
        self._current_model_index: int = 0
        self._fallback_history: List[Dict[str, Any]] = []
        self._high_latency_threshold: float = 1.0

    def set_system_prompt(self, prompt: str) -> None:
        self._system_prompt = prompt

    def update_context(self, key: str, value: Any) -> None:
        self._context[key] = value

    def append_context(self, key: str, value: Any) -> None:
        if key not in self._context or not isinstance(self._context[key], list):
            self._context[key] = []
        self._context[key].append(value)

    def build_system_prompt(self) -> str:
        parts = [self._system_prompt]
        memory = self._context.get("memory", [])
        if memory:
            mem_text = "\n".join(f"- {m.get('text', '')}" for m in memory[:5])
            parts.append(f"\n[Memoria relevante]\n{mem_text}")
        vision = self._context.get("vision", [])
        if vision:
            vis_text = "\n".join(f"- {v.get('description', '')}" for v in vision[-3:])
            parts.append(f"\n[Vision]\n{vis_text}")
        telemetry = self._context.get("telemetry", {})
        if telemetry:
            t = telemetry
            tele = f"\n[Telemetria] CPU={t.get('cpu_percent', '?')}% RAM={t.get('ram_percent', '?')}%"
            if t.get("gpu_percent") is not None:
                tele += f" GPU={t['gpu_percent']:.0f}%"
            parts.append(tele)
        tools = self._context.get("tools", [])
        if tools:
            tools_text = "\n".join(f"- {t.get('name')}: {t.get('description', '')}" for t in tools[:8])
            parts.append(f"\n[Herramientas disponibles]\n{tools_text}")
        actions = self._context.get("actions", [])
        if actions:
            acts = [a for a in actions if a.get("requires_confirmation")]
            if acts:
                acts_text = "\n".join(f"- {a.get('tool_name')}: {a.get('confirmation_prompt', '')}" for a in acts[-5:])
                parts.append(f"\n[Acciones pendientes de confirmacion]\n{acts_text}")
        return "\n".join(parts)

    async def select_model(self, latency_hint: Optional[float] = None) -> Dict[str, Any]:
        if latency_hint is not None and latency_hint > self._high_latency_threshold:
            self._current_model_index = (self._current_model_index + 1) % len(MODEL_FALLBACK_CHAIN)
        model = MODEL_FALLBACK_CHAIN[self._current_model_index]
        self._fallback_history.append({
            "selected": model,
            "latency_hint": latency_hint,
            "timestamp": time.time(),
        })
        self._fallback_history = self._fallback_history[-50:]
        return model

    def record_model_result(self, model: Dict[str, Any], success: bool, latency: float) -> None:
        self._fallback_history.append({
            "model": model,
            "success": success,
            "latency": latency,
            "timestamp": time.time(),
        })
        self._fallback_history = self._fallback_history[-50:]

    def get_status(self) -> Dict[str, Any]:
        return {
            "current_model": MODEL_FALLBACK_CHAIN[self._current_model_index],
            "fallback_history": self._fallback_history[-10:],
            "context_keys": list(self._context.keys()),
            "system_prompt_length": len(self._system_prompt),
        }

    def reset(self) -> None:
        self._context = {
            "memory": [],
            "vision": [],
            "telemetry": {},
            "tools": [],
            "actions": [],
        }
        self._fallback_history = []


orchestrator = SwarmOrchestrator()
