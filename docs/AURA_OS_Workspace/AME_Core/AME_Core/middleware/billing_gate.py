"""
Middleware de autenticacion y control de cuotas para AURA/AME.
Valida tokens de suscripcion activa y limita requests segun el plan.
Simula integracion con pasarelas de pago (Stripe/PayPal) y Railway Billing.
"""

import os, json, time, hashlib, hmac
from datetime import datetime, timedelta

PLANS = {
    "free": {
        "requests_per_hour": 60,
        "max_tokens": 2048,
        "features": ["chat", "health_check"],
        "price": 0,
    },
    "basic": {
        "requests_per_hour": 500,
        "max_tokens": 4096,
        "features": ["chat", "health_check", "osint", "automation"],
        "price": 9.99,
    },
    "pro": {
        "requests_per_hour": 2000,
        "max_tokens": 8192,
        "features": [
            "chat",
            "health_check",
            "osint",
            "automation",
            "rollercoin",
            "mark_xlvi",
            "priority",
        ],
        "price": 29.99,
    },
    "enterprise": {
        "requests_per_hour": 10000,
        "max_tokens": 32768,
        "features": ["all"],
        "price": 99.99,
    },
}


class BillingError(Exception):
    pass


class QuotaExceeded(BillingError):
    pass


class InvalidToken(BillingError):
    pass


class BillingGate:
    def __init__(self, secret_key=None):
        self.secret_key = secret_key or os.getenv("BILLING_SECRET", "aura-billing-secret-dev")
        self._rate_store = {}

    def _make_token(self, user_id: str, plan: str, expires_days: int = 30) -> str:
        payload = {
            "user_id": user_id,
            "plan": plan,
            "expires": (datetime.utcnow() + timedelta(days=expires_days)).isoformat(),
        }
        raw = json.dumps(payload, separators=(",", ":"))
        sig = hmac.new(self.secret_key.encode(), raw.encode(), hashlib.sha256).hexdigest()[:16]
        return f"{raw}.{sig}"

    def validate_token(self, token: str) -> dict:
        try:
            raw, sig = token.rsplit(".", 1)
            expected = hmac.new(self.secret_key.encode(), raw.encode(), hashlib.sha256).hexdigest()[
                :16
            ]
            if not hmac.compare_digest(sig, expected):
                raise InvalidToken("Firma invalida")
            payload = json.loads(raw)
            expires = datetime.fromisoformat(payload["expires"])
            if expires < datetime.utcnow():
                raise InvalidToken("Token expirado")
            return payload
        except (ValueError, KeyError, json.JSONDecodeError) as e:
            raise InvalidToken(f"Token malformado: {e}")

    def check_quota(self, user_id: str, plan: str) -> bool:
        now = time.time()
        hour_key = int(now // 3600)
        store_key = f"{user_id}:{hour_key}"
        limit = PLANS.get(plan, PLANS["free"])["requests_per_hour"]
        if store_key not in self._rate_store:
            self._rate_store[store_key] = 0
            self._clean_old(hour_key)
        if self._rate_store[store_key] >= limit:
            raise QuotaExceeded(f"Limite de {limit} req/h alcanzado para plan {plan}")
        self._rate_store[store_key] += 1
        return True

    def _clean_old(self, current_hour: int):
        for key in list(self._rate_store.keys()):
            if not key.endswith(f":{current_hour}"):
                del self._rate_store[key]

    def has_feature(self, plan: str, feature: str) -> bool:
        plan_data = PLANS.get(plan, PLANS["free"])
        return feature in plan_data["features"] or "all" in plan_data["features"]

    def create_subscription_url(self, plan: str, user_id: str = "demo") -> dict:
        plan_data = PLANS.get(plan, PLANS["free"])
        return {
            "url": f"https://billing.aura-system.com/checkout?" f"plan={plan}&user={user_id}",
            "plan": plan,
            "amount": plan_data["price"],
            "currency": "USD",
            "interval": "monthly",
            "gateway": "stripe",
            "sandbox": True,
        }

    def process_webhook(self, payload: dict) -> dict:
        event_type = payload.get("type", "unknown")
        if event_type == "payment_intent.succeeded":
            return {
                "status": "approved",
                "message": "Pago confirmado, suscripcion activa por 30 dias",
            }
        if event_type == "payment_intent.failed":
            return {"status": "rejected", "message": "Pago rechazado, verificar metodo de pago"}
        return {"status": "ignored", "message": f"Evento {event_type}"}


gate = BillingGate()


def billing_middleware(token: str, feature: str = "chat"):
    payload = gate.validate_token(token)
    plan = payload.get("plan", "free")
    user_id = payload.get("user_id", "anonymous")
    if not gate.has_feature(plan, feature):
        raise BillingError(f"Plan {plan} no incluye la funcion '{feature}'")
    gate.check_quota(user_id, plan)
    return {"user_id": user_id, "plan": plan, "remaining": True}


if __name__ == "__main__":
    test_token = gate._make_token("user_test", "basic", 30)
    print(f"Token de prueba: {test_token}")
    print(f"Validacion: {gate.validate_token(test_token)}")
    print(f"URL de pago Pro: {gate.create_subscription_url('pro')}")
    print(f"Funcion OSINT en plan basic: " f"{gate.has_feature('basic', 'osint')}")
