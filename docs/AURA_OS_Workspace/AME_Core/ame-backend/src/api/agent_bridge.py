"""
AME Agent Bridge - Endpoint de estado central para sincronización.
Expone:
- GET  /api/bridge/status
- POST /api/bridge/update
"""

import os
import json
import time
import hashlib
import hmac
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(prefix="/api/bridge", tags=["agent_bridge"])

SECRET = os.getenv("BRIDGE_SECRET", "ame-bridge-local-secret")
STATE_DIR = Path(os.getenv("BRIDGE_STATE_DIR", "bridge_state"))
STATE_DIR.mkdir(exist_ok=True)
STATE_FILE = STATE_DIR / "state.json"
LOG_FILE = STATE_DIR / "bridge.log"


class BridgeStatus(BaseModel):
    ok: bool
    service: str
    last_ping: str
    pending_tasks: list[str]
    recent_logs: list[dict]
    env: dict


class BridgeUpdate(BaseModel):
    action: str
    payload: Optional[dict] = None
    source: str = "unknown"
    requires_assist: bool = False
    error_dump: Optional[str] = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sign(data: dict) -> str:
    raw = json.dumps(data, separators=(",", ":"), sort_keys=True)
    return hmac.new(SECRET.encode(), raw.encode(), hashlib.sha256).hexdigest()[:16]


def _validate_signature(data: dict, sig: str) -> bool:
    expected = _sign(data)
    return hmac.compare_digest(expected, sig)


def _read_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {"status": "initializing", "logs": [], "pending": []}


def _write_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def _log_event(event: dict) -> None:
    event["ts"] = _now_iso()
    state = _read_state()
    state.setdefault("logs", []).insert(0, event)
    state["logs"] = state["logs"][:200]
    _write_state(state)
    try:
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    except OSError:
        pass


@router.get("/status")
async def get_status(request: Request) -> BridgeStatus:
    state = _read_state()
    logs = state.get("logs", [])[:50]
    pending = state.get("pending", [])[:100]

    safe_env = {
        "VERCEL_URL": os.getenv("VERCEL_URL", ""),
        "RAILWAY_URL": os.getenv("RAILWAY_URL", os.getenv("RAILWAY_API_URL", "")),
        "HF_SPACE_URL": os.getenv("HF_SPACE_URL", ""),
        "N8N_URL": os.getenv("N8N_URL", ""),
        "BRIDGE_MODE": os.getenv("BRIDGE_MODE", "local"),
    }

    status = BridgeStatus(
        ok=True,
        service="ame-backend",
        last_ping=_now_iso(),
        pending_tasks=pending,
        recent_logs=logs,
        env=safe_env,
    )
    return status


@router.post("/update")
async def post_update(update: BridgeUpdate, x_signature: Optional[str] = None) -> dict:
    event = {
        "action": update.action,
        "source": update.source,
        "payload": update.payload or {},
        "requires_assist": update.requires_assist,
        "error_dump": update.error_dump,
    }
    if x_signature:
        if not _validate_signature(event, x_signature):
            raise HTTPException(status_code=403, detail="Invalid signature")

    state = _read_state()
    if update.requires_assist and update.error_dump:
        state.setdefault("pending", []).append(
            {
                "id": hashlib.md5(update.error_dump.encode()).hexdigest()[:10],
                "created_at": _now_iso(),
                "action": update.action,
                "source": update.source,
                "snippet": (update.error_dump or "")[:500],
            }
        )
        _write_state(state)

    _log_event(event)
    return {"accepted": True, "pending": len(state.get("pending", []))}
