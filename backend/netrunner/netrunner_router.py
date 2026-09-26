# -*- coding: utf-8 -*-
"""AURA Netrunner Router — API endpoints para modo Netrunner.

Endpoints:
  GET  /api/netrunner/scan    - Escanea red y descubre access points
  GET  /api/netrunner/map     - Mapa visual de nodos comprometidos
  POST /api/netrunner/hack    - Intenta hackear un access point
  GET  /api/netrunner/missions - Misiones activas
  GET  /api/netrunner/stats   - Estadisticas del netrunner
"""
from __future__ import annotations

import json
import logging
import random
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel

from backend.netrunner.netrunner_core import (
    NetrunnerState,
    AccessPoint,
    Mission,
    generate_access_points,
    generate_missions_from_aps,
    attempt_hack,
    process_hack_result,
    SecurityLevel,
    AccessStatus,
    NodeType,
)

logger = logging.getLogger("AURA.Netrunner.Router")

netrunner_router = APIRouter(prefix="/api/netrunner", tags=["netrunner"])

_STATE = NetrunnerState()


def get_state() -> NetrunnerState:
    return _STATE


class ScanRequest(BaseModel):
    subnet: str = "192.168.1"
    count: int = 8
    force: bool = False


class HackRequest(BaseModel):
    mission_id: str
    skill: int = 5


class MissionResponse(BaseModel):
    missions: List[Dict[str, Any]]
    pending: int
    completed: int
    failed: int


@netrunner_router.post("/scan")
async def netrunner_scan(req: ScanRequest = Body(...)) -> Dict[str, Any]:
    """Escanea la red local y genera access points + misiones."""
    try:
        from backend.daemon.aura_daemon import get_daemon

        if not req.force and _STATE.last_scan_time and (time.time() - _STATE.last_scan_time < 30):
            return {
                "message": "Escaneo reciente. Usa force=True",
                "access_points": len(_STATE.access_points),
                "scan_cooldown": 30 - int(time.time() - _STATE.last_scan_time),
            }

        aps = generate_access_points(count=req.count, subnet=req.subnet)
        _STATE.access_points = aps
        _STATE.last_scan_time = time.time()

        missions = generate_missions_from_aps(aps, _STATE)
        _STATE.missions.extend(missions)

        daemon = get_daemon()
        daemon.event_bus.emit_simple("netrunner_scan", {
            "access_points": len(aps),
            "missions_created": len(missions),
            "subnet": req.subnet,
            "timestamp": datetime.now().isoformat(),
        }, agent="netrunner")

        return {
            "scan_id": f"NR-{int(time.time())}",
            "access_points": [ap.to_dict() for ap in aps],
            "missions_created": [m.to_dict() for m in missions],
            "total_access_points": len(aps),
            "total_missions": len(_STATE.missions),
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@netrunner_router.get("/map")
async def netrunner_map() -> Dict[str, Any]:
    """Mapa de red con nodos y estado."""
    return {
        "map": _STATE.get_map(),
        "access_points": [ap.to_dict() for ap in _STATE.access_points],
        "compromised": _STATE.compromised,
        "total_nodes": len(_STATE.access_points),
        "compromised_count": len(_STATE.compromised),
        "last_scan": _STATE.last_scan_time,
    }


@netrunner_router.post("/hack")
async def netrunner_hack(req: HackRequest = Body(...)) -> Dict[str, Any]:
    """Intenta hackear un access point mediante mision."""
    try:
        mission = None
        for m in _STATE.missions:
            if m.mission_id == req.mission_id:
                mission = m
                break

        if mission is None:
            raise HTTPException(status_code=404, detail="Mission not found")
        if mission.status != "available":
            raise HTTPException(status_code=400, detail=f"Mission {mission.status}")

        hack_result = attempt_hack(mission, skill=req.skill)
        result = process_hack_result(hack_result, mission, _STATE, event_bus=None)

        daemon = get_daemon()
        if hack_result["success"]:
            daemon.event_bus.emit_simple("netrunner_hack_success", {
                "mission_id": mission.mission_id,
                "target": mission.target_ip,
                "reward": mission.reward,
                "total_rewards": _STATE.total_rewards,
                "ices_breached": hack_result["ices_breached"],
                "timestamp": datetime.now().isoformat(),
            }, agent="netrunner")
            daemon.event_bus.emit_simple("aura_learning_event", {
                "type": "netrunner_skill",
                "skill_gained": random.randint(1, 3),
                "target": mission.target_ip,
                "timestamp": datetime.now().isoformat(),
            }, agent="netrunner")
        else:
            daemon.event_bus.emit_simple("netrunner_hack_fail", {
                "mission_id": mission.mission_id,
                "target": mission.target_ip,
                "damage": hack_result["damage_taken"],
                "timestamp": datetime.now().isoformat(),
            }, agent="netrunner")

        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@netrunner_router.get("/missions")
async def netrunner_missions() -> Dict[str, Any]:
    """Lista misiones activas."""
    available = [m for m in _STATE.missions if m.status == "available"]
    completed = [m for m in _STATE.missions if m.status == "completed"]
    failed = [m for m in _STATE.missions if m.status == "failed"]
    in_progress = [m for m in _STATE.missions if m.status not in ("available", "completed", "failed")]

    return {
        "missions": [m.to_dict() for m in _STATE.missions],
        "summary": {
            "total": len(_STATE.missions),
            "available": len(available),
            "in_progress": len(in_progress),
            "completed": len(completed),
            "failed": len(failed),
        },
        "total_rewards": _STATE.total_rewards,
        "success_rate": (
            _STATE.successful_hacks / _STATE.hack_attempts * 100
            if _STATE.hack_attempts > 0 else 0
        ),
    }


@netrunner_router.get("/stats")
async def netrunner_stats() -> Dict[str, Any]:
    """Estadisticas del netrunner."""
    return {
        "access_points_found": len(_STATE.access_points),
        "missions_total": len(_STATE.missions),
        "missions_completed": _STATE.successful_hacks,
        "missions_failed": _STATE.hack_attempts - _STATE.successful_hacks,
        "nodes_compromised": len(_STATE.compromised),
        "total_rewards": _STATE.total_rewards,
        "hack_attempts": _STATE.hack_attempts,
        "success_rate": (
            _STATE.successful_hacks / _STATE.hack_attempts * 100
            if _STATE.hack_attempts > 0 else 0
        ),
    }


@netrunner_router.get("/access-points")
async def list_access_points() -> Dict[str, Any]:
    """Lista todos los access points descubiertos."""
    return {
        "access_points": [ap.to_dict() for ap in _STATE.access_points],
        "total": len(_STATE.access_points),
    }
