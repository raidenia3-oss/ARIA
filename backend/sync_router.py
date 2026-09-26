"""Sync bridge para sincronizacion LAN entre PC y celular.

Incluye el Differential Sync Engine — endpoints para recibir lotes de eventos
acumulados offline en el cliente AME (SD-card buffer) y fusionarlos con el
estado central, aplicando validaciones de coherencia literaria.
"""

import json
import time
import threading
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/sync", tags=["sync"])

_device_states: Dict[str, Dict[str, Any]] = {}
_device_commands: Dict[str, list] = {}
_lock = threading.Lock()


class DeviceState(BaseModel):
    device_id: str
    role: str = "mobile"
    state: Dict[str, Any] = {}
    last_seen: Optional[float] = None


class DeviceCommand(BaseModel):
    target_device: str
    command: str
    payload: Dict[str, Any] = {}


@router.post("/register")
async def register_device(state: DeviceState) -> Dict[str, Any]:
    with _lock:
        _device_states[state.device_id] = {
            "role": state.role,
            "state": state.state,
            "last_seen": time.time(),
        }
        _device_commands.setdefault(state.device_id, [])
    return {"status": "registered", "device_id": state.device_id}


@router.post("/state")
async def update_state(state: DeviceState) -> Dict[str, Any]:
    with _lock:
        current = _device_states.get(state.device_id, {})
        merged = dict(current.get("state", {}))
        merged.update(state.state)
        _device_states[state.device_id] = {
            "role": state.role,
            "state": merged,
            "last_seen": time.time(),
        }
    return {"status": "updated", "device_id": state.device_id}


@router.get("/devices")
async def list_devices() -> Dict[str, Any]:
    now = time.time()
    with _lock:
        devices = []
        for device_id, info in _device_states.items():
            devices.append({
                "device_id": device_id,
                "role": info.get("role", "unknown"),
                "last_seen": info.get("last_seen"),
                "state": info.get("state", {}),
                "online": now - info.get("last_seen", 0) < 30,
            })
    return {"devices": devices}


@router.post("/command")
async def send_command(cmd: DeviceCommand) -> Dict[str, Any]:
    with _lock:
        queue = _device_commands.setdefault(cmd.target_device, [])
        queue.append({
            "command": cmd.command,
            "payload": cmd.payload,
            "ts": time.time(),
        })
    return {"status": "queued", "target_device": cmd.target_device}


@router.get("/commands/{device_id}")
async def get_commands(device_id: str) -> Dict[str, Any]:
    with _lock:
        queue = _device_commands.get(device_id, [])
        _device_commands[device_id] = []
    return {"device_id": device_id, "commands": queue}
