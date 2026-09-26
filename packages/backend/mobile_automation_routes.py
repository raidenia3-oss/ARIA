"""Mobile automation routes for AURA."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Query

from backend.mobile_automation_manager import MobileAutomationManager

router = APIRouter(prefix="/api/mobile", tags=["mobile_automation"])

mobile_automation: MobileAutomationManager | None = None


def init_mobile_automation(manager: MobileAutomationManager) -> None:
    global mobile_automation
    mobile_automation = manager


@router.get("/automation/status")
async def get_automation_status() -> Dict[str, Any]:
    if mobile_automation is None:
        raise HTTPException(status_code=500, detail="Mobile automation not initialized")
    return mobile_automation.get_apps_status()


@router.post("/automation/start")
async def start_automation() -> Dict[str, Any]:
    if mobile_automation is None:
        raise HTTPException(status_code=500, detail="Mobile automation not initialized")
    return {
        "status": "started",
        "message": "Mobile automation started",
        "apps_available": len(mobile_automation.known_apps),
    }


@router.post("/automation/stop")
async def stop_automation() -> Dict[str, Any]:
    return {
        "status": "stopped",
        "message": "Mobile automation stopped",
    }


@router.get("/apps/available")
async def get_available_apps() -> Dict[str, Any]:
    if mobile_automation is None:
        raise HTTPException(status_code=500, detail="Mobile automation not initialized")
    apps = await mobile_automation.scan_device_apps()
    return {
        "apps": [app.to_dict() for app in apps],
        "total": len(apps),
        "estimated_daily_earnings": sum(
            app.estimated_earning_per_hour * 24 for app in apps if app.enabled
        ),
    }


@router.post("/apps/{app_name}/enable")
async def enable_app_automation(app_name: str) -> Dict[str, Any]:
    if mobile_automation is None:
        raise HTTPException(status_code=500, detail="Mobile automation not initialized")
    success = await mobile_automation.enable_app(app_name)
    return {
        "app": app_name,
        "enabled": success,
        "status": "enabled" if success else "not_found",
    }


@router.post("/apps/{app_name}/disable")
async def disable_app_automation(app_name: str) -> Dict[str, Any]:
    if mobile_automation is None:
        raise HTTPException(status_code=500, detail="Mobile automation not initialized")
    success = await mobile_automation.disable_app(app_name)
    return {
        "app": app_name,
        "disabled": success,
        "status": "disabled" if success else "not_found",
    }


@router.get("/earnings/today")
async def get_today_earnings() -> Dict[str, Any]:
    if mobile_automation is None:
        raise HTTPException(status_code=500, detail="Mobile automation not initialized")
    return {
        "date": datetime.now().date().isoformat(),
        "earnings": mobile_automation.daily_earnings,
        "apps_running": len(mobile_automation.apps_running),
        "estimated_final": mobile_automation.daily_earnings
        * (24 / datetime.now().hour)
        if datetime.now().hour > 0
        else 0,
    }


@router.get("/earnings/history")
async def get_earnings_history(days: int = Query(7)) -> Dict[str, Any]:
    return {
        "period_days": days,
        "earnings": [],
        "total": 0.0,
        "average_daily": 0.0,
    }


@router.post("/automation/optimize")
async def optimize_automation() -> Dict[str, Any]:
    if mobile_automation is None:
        raise HTTPException(status_code=500, detail="Mobile automation not initialized")
    apps = mobile_automation.known_apps
    apps.sort(key=lambda x: x.estimated_earning_per_hour, reverse=True)
    for i, app in enumerate(apps):
        app.enabled = i < 3
    return {
        "status": "optimized",
        "top_apps": [app.name for app in apps[:3]],
        "message": "Sistema optimizado por rentabilidad",
    }


@router.get("/device/info")
async def get_device_info() -> Dict[str, Any]:
    if mobile_automation is None or not mobile_automation.adb:
        return {"error": "ADB not connected"}
    return {
        "battery_level": None,
        "screen_on": None,
        "storage_available": None,
        "apps_installed": 0,
    }
