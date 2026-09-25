import asyncio
import json
import os
from typing import Any, Dict, List, Optional

from .base import ConnectorBase


class StripeConnector(ConnectorBase):
    def __init__(self, secret_key: str = "") -> None:
        super().__init__("stripe")
        self.secret_key = secret_key or os.environ.get("STRIPE_SECRET_KEY", "")
        self.base_url = "https://api.stripe.com/v1"
        self._transaction_log: List[Dict[str, Any]] = []

    async def verify_connection(self) -> bool:
        return bool(self.secret_key)

    async def _request(self, method: str, path: str, body: Optional[Dict] = None) -> Dict[str, Any]:
        import base64
        import urllib.request

        url = f"{self.base_url}{path}"
        data = json.dumps(body).encode("utf-8") if body else None
        auth = base64.b64encode(f"{self.secret_key}:".encode()).decode()
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Authorization", f"Basic {auth}")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            self._circuit_open = True
            self._circuit_opened_at = asyncio.get_event_loop().time()
            raise

    async def create_payment(
        self, amount: int, currency: str = "usd", customer_id: Optional[str] = None
    ) -> Dict[str, Any]:
        async def _do():
            body = {"amount": amount, "currency": currency}
            if customer_id:
                body["customer"] = customer_id
            return await asyncio.to_thread(self._request, "POST", "/payment_intents", body)

        return await self.retry_with_exponential_backoff(_do)

    async def get_balance(self) -> Dict[str, Any]:
        async def _do():
            return await asyncio.to_thread(self._request, "GET", "/balance", None)

        return await self.retry_with_exponential_backoff(_do)

    async def create_subscription(self, customer_id: str, price_id: str) -> Dict[str, Any]:
        async def _do():
            body = {"customer": customer_id, "items": [{"price": price_id}]}
            return await asyncio.to_thread(self._request, "POST", "/subscriptions", body)

        return await self.retry_with_exponential_backoff(_do)

    async def handle_webhook(self, payload: str, signature: str) -> Dict[str, Any]:
        async def _do():
            import hashlib
            import hmac
            import time

            event = json.loads(payload)
            timestamp = str(int(time.time()))
            sig = f"{timestamp}.{payload}"
            expected = hmac.new(self.secret_key.encode(), sig.encode(), hashlib.sha256).hexdigest()
            valid = hmac.compare_digest(expected, signature)
            if not valid:
                return {"error": "Invalid signature"}
            self._transaction_log.append(
                {"event": event.get("type"), "data": event.get("data"), "timestamp": timestamp}
            )
            return {"processed": True, "event_type": event.get("type")}

        return await self.retry_with_exponential_backoff(_do)

    async def fallback_mechanism(self, operation: str, **kwargs) -> Dict[str, Any]:
        return {
            "fallback": True,
            "connector": "stripe",
            "operation": operation,
            "transaction_log": self._transaction_log[-10:] if self._transaction_log else [],
        }
