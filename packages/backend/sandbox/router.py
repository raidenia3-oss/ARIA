"""BLOQUE 77 - Sandbox Management REST Endpoints (/api/sandbox)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.sandbox.executor import SandboxRequest, get_sandbox_orchestrator

router = APIRouter(prefix="/api/sandbox", tags=["sandbox"])


class RunRequest(BaseModel):
    lang: str = "python"
    code: str = ""
    timeout_ms: int = 5000
    memory_mb: int = 128
    network: bool = False
    args: List[str] = []
    stdin: str = ""


class DestroyRequest(BaseModel):
    sandbox_id: str


def _result_to_dict(r) -> Dict[str, Any]:
    return {
        "sandbox_id": r.sandbox_id,
        "status": r.status,
        "returncode": r.returncode,
        "stdout": r.stdout,
        "stderr": r.stderr,
        "duration_ms": r.duration_ms,
        "memory_peak_mb": r.memory_peak_mb,
        "error": r.error,
    }


@router.post("/run", response_model=Dict[str, Any])
async def run_sandbox(req: RunRequest):
    orch = get_sandbox_orchestrator()
    try:
        result = orch.run(SandboxRequest(
            lang=req.lang, code=req.code, timeout_ms=req.timeout_ms,
            memory_mb=req.memory_mb, network=req.network,
            args=req.args, stdin=req.stdin,
        ))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc))
    return _result_to_dict(result)


@router.get("/status", response_model=Dict[str, Any])
async def sandbox_status():
    return get_sandbox_orchestrator().status()


@router.get("/instances", response_model=List[Dict[str, Any]])
async def sandbox_instances():
    return [
        {"sandbox_id": i.sandbox_id, "lang": i.lang, "status": i.status,
         "workdir": i.workdir, "created_at": i.created_at,
         "destroyed_at": i.destroyed_at}
        for i in get_sandbox_orchestrator().instances()
    ]


@router.post("/destroy", response_model=Dict[str, Any])
async def destroy_sandbox(req: DestroyRequest):
    ok = get_sandbox_orchestrator().destroy(req.sandbox_id)
    if not ok:
        raise HTTPException(status_code=404, detail="sandbox_id not found")
    return {"sandbox_id": req.sandbox_id, "destroyed": True}


@router.get("/health", response_model=Dict[str, Any])
async def sandbox_health():
    st = get_sandbox_orchestrator().status()
    return {"ok": True, "executor": st["executor"], "workdir_root": st["workdir_root"],
            "has_docker": False, "offline_only": True}