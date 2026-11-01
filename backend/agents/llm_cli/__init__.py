"""Gemini CLI provider via subprocess.

FASE 1: un solo proveedor, Gemini CLI (@google/gemini-cli).
El nucleo del proveedor vive en provider.py; quota.py maneja el presupuesto
diario y el cooldown; redact.py limpia los prompts salientes antes de llegar
al CLI. Nada de esto estima cuota: todo lo que se reporta es medido o
configurable via fuente documentada.
"""

from __future__ import annotations

from backend.agents.llm_cli.provider import GeminiCLIService, get_gemini_cli_service
from backend.agents.llm_cli.quota import QuotaManager, get_quota_manager
from backend.agents.llm_cli.redact import redact_prompt

__all__ = [
    "GeminiCLIService",
    "get_gemini_cli_service",
    "QuotaManager",
    "get_quota_manager",
    "redact_prompt",
]