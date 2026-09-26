"""Omniroute fallback — ReAct Loop for when external providers are unavailable."""
from __future__ import annotations

import time
import uuid
from typing import Dict, Any, List, Optional


class ReactLoop:
    """Minimal ReAct Loop fallback for Omniroute failures.

    When all 300+ external providers are unavailable, this provides
    a basic response using locally available tools and skills.
    """

    def __init__(
        self,
        skill_registry: Any = None,
        memory: Any = None,
        ai_manager: Any = None,
    ):
        self.skill_registry = skill_registry
        self.memory = memory
        self.ai_manager = ai_manager
        # BLOQUE 52: contexto visual inyectado por el ScreenBridge (VLM Context Injector)
        self._vision_context: Optional[Dict[str, Any]] = None
        self._vision_context_text: str = ""

    def set_vision_context(self, context: Any) -> None:
        """Recibe y almacena el contexto visual del ScreenBridge.

        El contexto contiene metadatos textuales inteligibles
        (``context_text``) que el nucleo de razonamiento puede inyectar
        en el prompt del sistema y en el agente de automatizacion web.
        100% offline: proviene del VisionAnalyzer local (Ollama/Jan).
        """
        self._vision_context = context
        if isinstance(context, dict):
            self._vision_context_text = (
                context.get("context_text")
                or context.get("description")
                or ""
            )
        elif context is None:
            self._vision_context_text = ""
        else:
            self._vision_context_text = str(context)

    def get_vision_context(self) -> Optional[Dict[str, Any]]:
        """Devuelve el contexto visual almacenado (o None)."""
        return self._vision_context

    def get_vision_context_text(self) -> str:
        """Resumen textual del contexto visual para inyectar en prompts."""
        return self._vision_context_text

    async def process(
        self,
        message: str,
        system_prompt: str = "",
    ) -> str:
        """Process a message and return a response (async)."""
        # BLOQUE 52: inyeccion de contexto visual al flujo de razonamiento del nucleo
        if not system_prompt and self._vision_context_text:
            base_prompt = "Eres AURA, un asistente de IA avanzado."
            system_prompt = (
                f"{base_prompt}\n\n[Contexto visual del escritorio] "
                f"{self._vision_context_text}"
            )
        try:
            if self.ai_manager and hasattr(self.ai_manager, "chat"):
                result = self.ai_manager.chat(
                    message,
                    system_prompt=system_prompt or "Eres AURA, un asistente de IA avanzado.",
                )
                if isinstance(result, dict) and "message" in result:
                    return result["message"]
                return str(result) if result else self._fallback_response(message)
            else:
                return self._fallback_response(message)
        except Exception as e:
            return self._fallback_response(message)

    def _fallback_response(self, message: str) -> str:
        """Generate a basic response when no AI provider is available."""
        base = (
            f"[AURA Local Fallback] Recibido: '{message}'. "
            f"El servicio de IA remoto no esta disponible. "
            f"Por favor verifica tu conexion o revisa el dashboard de proveedores con: "
            f"GET /api/providers/recommendations"
        )
        # BLOQUE 52: el contexto visual enriquece la respuesta de fallback
        if self._vision_context_text:
            base = f"[Contexto visual] {self._vision_context_text}\n" + base
        return base
