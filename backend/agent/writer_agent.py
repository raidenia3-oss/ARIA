# -*- coding: utf-8 -*-
"""
AURA OS - Chunk 2: Writer Agent.

Genera texto consultando a Jan (OpenAI-compat, localhost:1337).
Si Jan no esta disponible, usa un template local (fallback).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import httpx

from backend.agent.swarm_base import BaseAgent, AgentRegistry
from backend.core.decision_engine import JAN_BASE_URL, JAN_MODEL

logger = logging.getLogger("AURA.Agent.Writer")


class WriterAgent(BaseAgent):
    """Agente writer: generacion de texto via Jan / fallback local."""

    DEFAULT_SYSTEM = (
        "Eres un asistente de codigo y reasoning de alta calidad. "
        "Responde de forma concisa y precisa."
    )

    def __init__(self, session_id: str = "", bus=None, model: str = "") -> None:
        super().__init__(name="writer_agent", session_id=session_id, bus=bus)
        self.jan_url = JAN_BASE_URL.rstrip("/") if JAN_BASE_URL else ""
        self.model = model or JAN_MODEL

    # ------------------------------------------------------------------
    def _query_jan(self, prompt: str, system_prompt: str = "") -> str:
        """Consulta Jan (OpenAI-compat) para generar texto."""
        url = f"{self.jan_url}/chat/completions"
        self.emit_thought("jan_call", {"url": url, "model": self.model})
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt or self.DEFAULT_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.7,
            "max_tokens": 1024,
        }
        try:
            with httpx.Client(timeout=15.0) as client:
                resp = client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"]
        except Exception as exc:
            logger.warning("Writer: Jan no disponible (%s) — fallback local", exc)
            return self._local_template(prompt, system_prompt)

    def _local_template(self, prompt: str, system_prompt: str = "") -> str:
        """Fallback local: genera texto usando templates simples."""
        header = f"System: {system_prompt}\n\n" if system_prompt else ""
        body = (
            f"Texto generado para: {prompt[:120]}...\n\n"
            f"(Creado por WriterAgent con fallback local. "
            f"Instala y ejecuta Jan en {self.jan_url} para reasoning completo.)\n"
        )
        return header + body

    # ------------------------------------------------------------------
    async def generate(self, prompt: str, system_prompt: str = "") -> Dict[str, Any]:
        """Variante async del metodo principal (compat con ParallelExecutor)."""
        return self._do_execute(prompt, prompt=prompt, system_prompt=system_prompt)

    def _do_execute(self, task: str, **kwargs) -> Dict[str, Any]:
        """Genera texto para la tarea/prompt dado."""
        prompt = kwargs.get("prompt", task)
        system_prompt = kwargs.get("system_prompt", kwargs.get("system", self.DEFAULT_SYSTEM))

        self.report_progress(25.0, "enviando a Jan")
        engine = "jan"
        try:
            response = self._query_jan(prompt, system_prompt)
            if "fallback" in response:
                engine = "local"
        except Exception as exc:
            logger.error("Writer: error inesperado: %s", exc)
            response = self._local_template(prompt, system_prompt)
            engine = "local"

        self.report_progress(100.0, "texto generado")
        return {
            "agent": self.name,
            "prompt": prompt[:200],
            "response": response,
            "model": self.model,
            "engine": engine,
            "system_used": bool(system_prompt),
        }


AgentRegistry.register("writer_agent", WriterAgent)

