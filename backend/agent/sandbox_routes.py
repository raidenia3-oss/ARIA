"""AURA Secure Code Execution Sandbox — REST endpoints (Bloque 58).

Endpoints para ejecución controlada de código y pruebas en sandbox:

- POST   /api/agent/sandbox/execute    — ejecuta código en sandbox aislado
- GET    /api/agent/sandbox/status       — estado del sandbox y métricas
- GET    /api/agent/sandbox/executions   — listado de ejecuciones recientes
- POST   /api/agent/sandbox/lint         — verifica sintaxis de código Python
- POST   /api/agent/sandbox/test         — ejecuta pruebas sobre código Python
- DELETE /api/agent/sandbox/executions   — limpia ejecuciones antiguas/ todas

100% local: el código se ejecuta en subprocessos aislados con límites
estrictos de tiempo, memoria y restricciones de filesystem.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.agent.sandbox import (
    IsolatedSandboxRunner,
    SandboxOutcome,
    SandboxExecutionResult,
    SandboxConfig,
    get_sandbox_runner,
    reset_sandbox_runner,
    lint_python_code,
    analyze_python_code,
)

logger = logging.getLogger("AURA.Agent.Sandbox.Routes")

router = APIRouter(prefix="/api/agent/sandbox", tags=["agent-sandbox"])


def _get_runner() -> IsolatedSandboxRunner:
    return get_sandbox_runner()


class ExecuteRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=50000)
    language: str = Field("python", pattern="^(python|bash|sh)$")
    timeout_seconds: float = Field(default=30.0, ge=0.1, le=300.0)
    memory_limit_mb: float = Field(default=256.0, ge=32.0, le=1024.0)
    cpu_limit_seconds: float = Field(default=10.0, ge=1.0, le=60.0)
    env_vars: Dict[str, str] = Field(default_factory=dict)
    restrictions: Dict[str, Any] = Field(default_factory=dict)


class LintRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=50000)


class TestRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=50000)
    timeout_seconds: float = Field(default=10.0, ge=0.1, le=60.0)


class CleanupRequest(BaseModel):
    older_than_seconds: Optional[float] = Field(default=None, ge=0)


@router.post("/execute")
async def execute_code(payload: ExecuteRequest) -> Dict[str, Any]:
    """Ejecuta código en sandbox aislado con límites de tiempo y recursos."""
    runner = _get_runner()
    try:
        result = await runner.execute(
            code=payload.code,
            language=payload.language,
            timeout=payload.timeout_seconds,
            memory_limit_mb=payload.memory_limit_mb,
            cpu_limit_seconds=payload.cpu_limit_seconds,
            env_vars=payload.env_vars,
            restrictions=payload.restrictions,
        )
        return result.to_dict()
    except Exception as exc:
        logger.debug("Sandbox execute error: %s", exc)
        return {
            "execution_id": "error",
            "outcome": SandboxOutcome.ERROR.value,
            "stdout": "",
            "stderr": str(exc),
            "warnings": ["Error en la ejecución del sandbox"],
        }


@router.get("/status")
async def sandbox_status() -> Dict[str, Any]:
    """Obtiene el estado actual del sandbox y sus métricas."""
    runner = _get_runner()
    return runner.get_status()


@router.get("/executions")
async def list_executions(limit: int = 20) -> Dict[str, Any]:
    """Lista las ejecuciones recientes en el sandbox."""
    runner = _get_runner()
    executions = runner.list_recent_executions(limit=limit)
    return {"count": len(executions), "executions": executions}


@router.get("/executions/{execution_id}")
async def get_execution(execution_id: str) -> Dict[str, Any]:
    """Obtiene el resultado de una ejecución específica."""
    runner = _get_runner()
    result = runner.get_execution_result(execution_id)
    if not result:
        raise HTTPException(status_code=404, detail="execution_not_found")
    return result.to_dict()


@router.post("/lint")
async def lint_code(payload: LintRequest) -> Dict[str, Any]:
    """Verifica la sintaxis de código Python sin ejecutarlo."""
    result = lint_python_code(payload.code)
    return result


@router.post("/test")
async def test_code(payload: TestRequest) -> Dict[str, Any]:
    """Ejecuta pruebas básicas sobre código Python en sandbox."""
    result = analyze_python_code(payload.code, timeout=payload.timeout_seconds)
    return result


@router.post("/cleanup")
async def cleanup_executions(payload: CleanupRequest) -> Dict[str, Any]:
    """Limpia ejecuciones antiguas del sandbox."""
    runner = _get_runner()
    cleaned = runner.clear_executions(older_than_seconds=payload.older_than_seconds)
    return {"cleaned": cleaned, "status": "ok"}


@router.post("/reset")
async def reset_sandbox() -> Dict[str, Any]:
    """Reinicia el sandbox a su estado inicial."""
    reset_sandbox_runner()
    return {"status": "ok", "message": "Sandbox reiniciado"}


__all__ = ["router"]
