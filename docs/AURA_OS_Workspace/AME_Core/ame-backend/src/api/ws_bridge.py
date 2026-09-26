"""WebSocket endpoint for AME bridge with JWT auth and HMAC validation."""

import os
import json
import time
import hmac
import hashlib
import threading
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

router = APIRouter(prefix="/ws", tags=["ws_bridge"])

SECRET = os.getenv("BRIDGE_SECRET", "ame-bridge-local-secret")
HEARTBEAT_TIMEOUT = int(os.getenv("BRIDGE_HEARTBEAT_TIMEOUT", "10"))
MAX_RECONNECT_BACKOFF = int(os.getenv("BRIDGE_BACKOFF_MAX", "60"))
STATE_DIR = Path(os.getenv("BRIDGE_STATE_DIR", "bridge_state"))
STATE_DIR.mkdir(exist_ok=True)
STATE_FILE = STATE_DIR / "state.json"
LOG_FILE = STATE_DIR / "bridge.log"


class _BridgeState:
    lock = threading.Lock()
    last_heartbeat = time.time()
    backoff = 1
    connected = False


def sign(data: dict) -> str:
    raw = json.dumps(data, separators=(",", ":"), sort_keys=True)
    return hmac.new(SECRET.encode(), raw.encode(), hashlib.sha256).hexdigest()[:16]


@router.websocket("/bridge")
async def ws_bridge(
    websocket: WebSocket,
    token: str = Query(default=""),
    signature: str = Query(default=""),
):
    await websocket.accept()
    try:
        if not token:
            await websocket.close(code=4003)
            return

        # Verify token (JWT)
        try:
            from auth_jwt import decode_token

            decode_token(token)
        except Exception:
            await websocket.close(code=4003)
            return

        # Optional HMAC signature validation
        if signature:
            payload = {"token": token, "ts": int(time.time())}
            if not hmac.compare_digest(sign(payload), signature):
                await websocket.close(code=4003)
                return

        _BridgeState.connected = True
        _BridgeState.last_heartbeat = time.time()
        _BridgeState.backoff = 1

        await websocket.send_json({"ok": True, "service": "ame-backend"})

        while True:
            msg = await websocket.receive_text()
            _BridgeState.last_heartbeat = time.time()
            # Persist event in state file
            try:
                state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            except Exception:
                state = {"logs": [], "pending": []}
            event = {
                "ts": datetime.now(timezone.utc).isoformat(),
                "source": "ws_client",
                "action": "ws_message",
                "payload": msg[:1000],
            }
            state.setdefault("logs", []).insert(0, event)
            state["logs"] = state["logs"][:200]
            STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    except WebSocketDisconnect:
        _BridgeState.connected = False
    except Exception:
        _BridgeState.connected = False
        await websocket.close()


def start_bridge_watchdog():
    """Background watchdog that monitors heartbeat and reconnection state."""

    def _watch():
        while True:
            time.sleep(1)
            now = time.time()
            if _BridgeState.connected and (now - _BridgeState.last_heartbeat) > HEARTBEAT_TIMEOUT:
                _BridgeState.connected = False
                _BridgeState.backoff = min(_BridgeState.backoff * 2, MAX_RECONNECT_BACKOFF)

    threading.Thread(target=_watch, daemon=True).start()
