"""Integration routes for AURA - Module 23.

Event-Driven Architecture, Webhooks & Integration Hub.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, HTTPException, Query
from fastapi.responses import JSONResponse

from backend.event_bus import EventBus
from backend.webhook_manager import WebhookManager

router = APIRouter(prefix="/api", tags=["integration"])

event_bus = EventBus()
webhook_manager = WebhookManager(event_bus)


@router.post("/events/publish")
async def publish_event(
    payload: Dict[str, Any] = Body(
        ...,
        json_schema_extra={
            "example": {
                "event_type": "narrative.generated",
                "data": {"module": "narrative", "length": 1200},
            }
        },
    ),
) -> Dict[str, Any]:
    event_type = str(payload.get("event_type", "generic"))
    data = payload.get("data", {})
    if not isinstance(data, dict):
        data = {"value": data}
    return await event_bus.publish(event_type, data)


@router.get("/events/history")
async def event_history(limit: int = Query(50, ge=1, le=500)) -> Dict[str, Any]:
    events = event_bus.recent(limit=limit)
    return {"count": len(events), "events": events}


@router.get("/webhooks/subscriptions")
async def list_subscriptions(
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    enabled_only: bool = Query(True, description="Only return enabled subscriptions"),
) -> Dict[str, Any]:
    subs = webhook_manager.get_subscriptions(event_type=event_type)
    if enabled_only:
        subs = [s for s in subs if s["enabled"]]
    return {"count": len(subs), "subscriptions": subs}


@router.post("/webhooks/subscriptions")
async def create_subscription(
    payload: Dict[str, Any] = Body(
        ...,
        json_schema_extra={
            "example": {
                "url": "https://example.com/webhook",
                "event_types": ["narrative.generated", "mobile.earning"],
                "secret": "optional-hmac-secret",
                "enabled": True,
            }
        },
    ),
) -> Dict[str, Any]:
    url = str(payload.get("url", ""))
    if not url:
        return JSONResponse(
            status_code=400,
            content={"detail": "url is required"},
        )
    sub = webhook_manager.add_subscription(
        url=url,
        event_types=payload.get("event_types"),
        secret=payload.get("secret"),
        enabled=bool(payload.get("enabled", True)),
    )
    return {"status": "created", "subscription": webhook_manager._sub_to_dict(sub)}


@router.delete("/webhooks/subscriptions/{subscription_id}")
async def delete_subscription(subscription_id: str) -> Dict[str, Any]:
    removed = webhook_manager.remove_subscription(subscription_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Subscription not found")
    return {"status": "deleted", "subscription_id": subscription_id}


@router.get("/webhooks/deliveries")
async def list_deliveries(
    limit: int = Query(50, ge=1, le=500),
    status: Optional[str] = Query(None, description="Filter by status: success/failed/pending"),
) -> Dict[str, Any]:
    deliveries = webhook_manager.get_deliveries(limit=limit)
    if status:
        deliveries = [d for d in deliveries if d["status"] == status]
    return {"count": len(deliveries), "deliveries": deliveries}


@router.post("/webhooks/test")
async def test_webhook(
    payload: Dict[str, Any] = Body(
        ...,
        json_schema_extra={
            "example": {
                "url": "https://httpbin.org/post",
                "payload": {"test": True, "message": "AURA webhook test"},
                "event_type": "webhook.test",
            }
        },
    ),
) -> Dict[str, Any]:
    url = str(payload.get("url", ""))
    if not url:
        return JSONResponse(
            status_code=400,
            content={"detail": "url is required"},
        )
    result = await webhook_manager.test_webhook(
        url=url,
        payload=payload.get("payload", {"test": True}),
        event_type=str(payload.get("event_type", "webhook.test")),
        secret=payload.get("secret"),
    )
    return {"status": "sent", "result": result}
