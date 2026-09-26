"""Webhook management for AURA - Module 23.

Handles outgoing webhooks with HMAC-SHA256 signatures, exponential
backoff retries, and delivery logging.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests as _requests

from backend.event_bus import EventBus, EventPayload, EventSubscriber


@dataclass
class WebhookSubscription:
    """Suscripción a un webhook externo."""

    id: str
    url: str
    event_types: List[str] = field(default_factory=lambda: ["*"])
    secret: str = ""
    enabled: bool = True
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


@dataclass
class WebhookDelivery:
    """Registro de una entrega de webhook."""

    id: str
    subscription_id: str
    event_type: str
    url: str
    status: str
    attempts: int
    http_status: Optional[int]
    response_body: Optional[str]
    last_error: Optional[str]
    payload: Dict[str, Any]
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    delivered_at: Optional[str] = None


class WebhookManager:
    """Gestión de webhooks salientes con firma HMAC y reintentos exponenciales."""

    def __init__(self, event_bus: Optional[EventBus] = None, max_retries: int = 5) -> None:
        self.event_bus = event_bus
        self.subscriptions: List[WebhookSubscription] = []
        self.deliveries: List[WebhookDelivery] = []
        self.max_retries = max_retries
        self._max_deliveries = 1000
        if event_bus is not None:
            sub_name = f"webhook-deliverer-{int(time.time() * 1000)}"
            self._subscriber_name = sub_name
            event_bus.subscribe(EventSubscriber(
                name=sub_name,
                handler=self._on_event,
                event_types=["*"],
            ))

    def add_subscription(
        self,
        url: str,
        event_types: Optional[List[str]] = None,
        secret: Optional[str] = None,
        enabled: bool = True,
    ) -> WebhookSubscription:
        sub = WebhookSubscription(
            id=f"hook-{int(time.time() * 1000)}",
            url=url,
            event_types=event_types or ["*"],
            secret=secret or secrets.token_hex(16),
            enabled=enabled,
        )
        self.subscriptions.append(sub)
        return sub

    def remove_subscription(self, sub_id: str) -> bool:
        before = len(self.subscriptions)
        self.subscriptions = [s for s in self.subscriptions if s.id != sub_id]
        return len(self.subscriptions) < before

    def get_subscriptions(self, event_type: Optional[str] = None) -> List[Dict[str, Any]]:
        subs = self.subscriptions
        if event_type:
            subs = [s for s in subs if "*" in s.event_types or event_type in s.event_types]
        return [self._sub_to_dict(s) for s in subs]

    def get_deliveries(self, limit: int = 50) -> List[Dict[str, Any]]:
        deliveries = self.deliveries[-limit:]
        return [self._delivery_to_dict(d) for d in deliveries]

    def _sub_to_dict(self, sub: WebhookSubscription) -> Dict[str, Any]:
        return {
            "id": sub.id,
            "url": sub.url,
            "event_types": sub.event_types,
            "secret": sub.secret,
            "enabled": sub.enabled,
            "created_at": sub.created_at,
        }

    def _delivery_to_dict(self, d: WebhookDelivery) -> Dict[str, Any]:
        return {
            "id": d.id,
            "subscription_id": d.subscription_id,
            "event_type": d.event_type,
            "url": d.url,
            "status": d.status,
            "attempts": d.attempts,
            "http_status": d.http_status,
            "last_error": d.last_error,
            "created_at": d.created_at,
            "delivered_at": d.delivered_at,
        }

    def _sign_payload(self, payload: Dict[str, Any], secret: str) -> str:
        body = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        return hmac.new(
            secret.encode("utf-8"),
            body.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _backoff_delay(self, attempt: int, base: float = 1.0, cap: float = 60.0) -> float:
        delay = min(base * (2 ** attempt), cap)
        return delay

    def _matching_subs(self, event_type: str) -> List[WebhookSubscription]:
        return [
            s for s in self.subscriptions
            if s.enabled and ("*" in s.event_types or event_type in s.event_types)
        ]

    async def _on_event(self, event: EventPayload) -> Dict[str, Any]:
        matches = self._matching_subs(event.event_type)
        tasks = [self.deliver(sub, event.data, event.event_type) for sub in matches]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return {
            "subscriptions_matched": len(matches),
            "results": [_safe_delivery(r) for r in results],
        }

    async def deliver(
        self,
        subscription: WebhookSubscription,
        payload: Dict[str, Any],
        event_type: str,
    ) -> WebhookDelivery:
        signature = self._sign_payload(payload, subscription.secret)
        headers = {
            "Content-Type": "application/json",
            "X-AURA-Signature": f"sha256={signature}",
            "X-AURA-Event-Type": event_type,
            "User-Agent": "AURA-WebhookManager/1.0",
        }
        body = json.dumps(payload)

        delivery = WebhookDelivery(
            id=f"del-{int(time.time() * 1000000)}",
            subscription_id=subscription.id,
            event_type=event_type,
            url=subscription.url,
            status="pending",
            attempts=0,
            http_status=None,
            response_body=None,
            last_error=None,
            payload=payload,
        )
        self.deliveries.append(delivery)
        if len(self.deliveries) > self._max_deliveries:
            self.deliveries = self.deliveries[-self._max_deliveries :]

        for attempt in range(self.max_retries):
            delivery.attempts = attempt + 1
            try:
                response = await asyncio.to_thread(
                    _requests.post,
                    subscription.url,
                    data=body,
                    headers=headers,
                    timeout=30,
                )
                delivery.http_status = response.status_code
                delivery.response_body = response.text[:2000]
                if response.status_code < 400:
                    delivery.status = "success"
                    delivery.delivered_at = datetime.utcnow().isoformat() + "Z"
                    return delivery
                delivery.last_error = f"HTTP {response.status_code}"
            except Exception as exc:
                delivery.last_error = str(exc)

            if attempt < self.max_retries - 1:
                delay = self._backoff_delay(attempt)
                await asyncio.sleep(delay)

        delivery.status = "failed"
        return delivery

    async def test_webhook(
        self,
        url: str,
        payload: Dict[str, Any],
        event_type: str = "webhook.test",
        secret: Optional[str] = None,
    ) -> Dict[str, Any]:
        secret = secret or secrets.token_hex(16)
        temp_sub = WebhookSubscription(
            id=f"test-{int(time.time() * 1000)}",
            url=url,
            event_types=[event_type],
            secret=secret,
            enabled=True,
        )
        delivery = await self.deliver(temp_sub, payload, event_type)
        return {
            "url": url,
            "event_type": event_type,
            "status": delivery.status,
            "attempts": delivery.attempts,
            "http_status": delivery.http_status,
            "last_error": delivery.last_error,
            "delivered_at": delivery.delivered_at,
        }


def _safe_delivery(result: Any) -> Any:
    if isinstance(result, Exception):
        return {"error": str(result), "type": type(result).__name__}
    return result
