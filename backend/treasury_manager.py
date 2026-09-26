"""
Treasury Manager - Auto-inversion inteligente de ganancias del Rollercoin bot.
Distribuye automaticamente las ganancias en APIs, hosting, modelos y reserva.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from datetime import datetime
from typing import Any, Dict, Optional

from backend.rollercoin_endpoints import rollercoin_bot

logger = logging.getLogger("AURA.Treasury")

TREASURY_STATE_FILE = os.getenv("AURA_TREASURY_STATE", "./treasury_state.json")
ALLOCATION_LOG_FILE = os.getenv("AURA_ALLOCATION_LOG", "./allocation_log.jsonl")


def _now() -> float:
    return time.time()


def _load_json(path: str, default: Any = None) -> Any:
    if not os.path.exists(path):
        return default if default is not None else {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default if default is not None else {}


def _save_json(path: str, data: Any) -> None:
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as exc:
        logger.error("No se pudo guardar %s: %s", path, exc)


class AllocationBudget:
    def __init__(self) -> None:
        self.apis_premium = 0.30
        self.hosting = 0.40
        self.models = 0.20
        self.reserve = 0.10

    def allocate(self, total: float) -> Dict[str, float]:
        return {
            "apis_premium": round(total * self.apis_premium, 4),
            "hosting": round(total * self.hosting, 4),
            "models": round(total * self.models, 4),
            "reserve": round(total * self.reserve, 4),
        }


class APIBudgetManager:
    def __init__(self) -> None:
        self.daily_budget = 0.0
        self.used_today = 0.0
        self.providers = {
            "gemini": {"price_per_query": 0.001, "daily_limit": 1000},
            "groq": {"price_per_query": 0.0001, "daily_limit": 10000},
            "openrouter": {"price_per_query": 0.0005, "daily_limit": 5000},
        }

    def set_daily_budget(self, amount: float) -> None:
        self.daily_budget = amount

    def can_afford_query(self, provider: str) -> bool:
        cost = self.providers.get(provider, {}).get("price_per_query", 0.0)
        return (self.used_today + cost) <= self.daily_budget

    def deduct_cost(self, provider: str) -> None:
        cost = self.providers.get(provider, {}).get("price_per_query", 0.0)
        self.used_today += cost

    def get_status(self) -> Dict[str, Any]:
        return {
            "daily_budget": self.daily_budget,
            "used_today": round(self.used_today, 4),
            "remaining": round(self.daily_budget - self.used_today, 4),
            "percentage_used": round((self.used_today / self.daily_budget * 100) if self.daily_budget > 0 else 0.0, 2),
        }


class HostingUpgradeManager:
    def __init__(self) -> None:
        self.current_tier = "free"
        self.daily_budget = 0.0
        self.tiers = {
            "free": {"ram": 0.5, "cpu": 0.5, "cost": 0},
            "basic": {"ram": 2.0, "cpu": 2, "cost": 10},
            "pro": {"ram": 8.0, "cpu": 4, "cost": 30},
            "premium": {"ram": 16.0, "cpu": 8, "cost": 50},
        }

    def set_daily_budget(self, amount: float) -> None:
        self.daily_budget = amount
        self._check_upgrade()

    def _check_upgrade(self) -> None:
        if self.current_tier == "free" and self.daily_budget >= 10:
            self.upgrade_to("basic")
        elif self.current_tier == "basic" and self.daily_budget >= 30:
            self.upgrade_to("pro")
        elif self.current_tier == "pro" and self.daily_budget >= 50:
            self.upgrade_to("premium")

    def upgrade_to(self, tier: str) -> None:
        if tier in self.tiers:
            self.current_tier = tier

    def get_status(self) -> Dict[str, Any]:
        tier_info = self.tiers[self.current_tier]
        return {
            "current_tier": self.current_tier,
            "ram_gb": tier_info["ram"],
            "cpu_cores": tier_info["cpu"],
            "daily_cost": tier_info["cost"],
            "budget_remaining": round(self.daily_budget - tier_info["cost"], 4),
        }


class ModelUpgradeManager:
    def __init__(self) -> None:
        self.current_model = "Qwen-0.5B"
        self.daily_budget = 0.0
        self.models = {
            "Qwen-0.5B": {"params": 500_000_000, "cost": 0},
            "Qwen-1.5B": {"params": 1_500_000_000, "cost": 5},
            "Qwen-7B": {"params": 7_000_000_000, "cost": 15},
            "Llama2-13B": {"params": 13_000_000_000, "cost": 20},
        }

    def set_daily_budget(self, amount: float) -> None:
        self.daily_budget = amount
        self._check_upgrade()

    def _check_upgrade(self) -> None:
        model_costs = {
            "Qwen-0.5B": 0,
            "Qwen-1.5B": 5,
            "Qwen-7B": 15,
            "Llama2-13B": 20,
        }
        for model, cost in sorted(model_costs.items(), key=lambda x: x[1], reverse=True):
            if self.daily_budget >= cost and self.current_model != model:
                self.upgrade_to(model)
                break

    def upgrade_to(self, model: str) -> None:
        if model in self.models:
            self.current_model = model

    def get_status(self) -> Dict[str, Any]:
        model_info = self.models[self.current_model]
        return {
            "current_model": self.current_model,
            "parameters": model_info["params"],
            "daily_cost": model_info["cost"],
            "budget_remaining": round(self.daily_budget - model_info["cost"], 4),
        }


class ReserveManager:
    def __init__(self) -> None:
        self.reserve_balance = 0.0

    def add_to_reserve(self, amount: float) -> None:
        self.reserve_balance += amount

    def withdraw_from_reserve(self, reason: str, amount: float) -> bool:
        if self.reserve_balance >= amount:
            self.reserve_balance -= amount
            return True
        return False

    def get_status(self) -> Dict[str, Any]:
        return {
            "reserve_balance": round(self.reserve_balance, 4),
            "message": "Fondo para emergencias",
        }


class TreasuryManager:
    def __init__(self) -> None:
        self.budget = AllocationBudget()
        self.api_manager = APIBudgetManager()
        self.hosting_manager = HostingUpgradeManager()
        self.model_manager = ModelUpgradeManager()
        self.reserve_manager = ReserveManager()
        self.daily_allocation_history: list[Dict[str, Any]] = []
        self._last_allocation_date: Optional[str] = None
        self._load_state()

    def _load_state(self) -> None:
        state = _load_json(TREASURY_STATE_FILE, {})
        if state:
            self.api_manager.daily_budget = float(state.get("api_daily_budget", 0.0))
            self.api_manager.used_today = float(state.get("api_used_today", 0.0))
            self.hosting_manager.daily_budget = float(state.get("hosting_daily_budget", 0.0))
            self.hosting_manager.current_tier = state.get("hosting_tier", "free")
            self.model_manager.daily_budget = float(state.get("models_daily_budget", 0.0))
            self.model_manager.current_model = state.get("model", "Qwen-0.5B")
            self.reserve_manager.reserve_balance = float(state.get("reserve_balance", 0.0))
            self._last_allocation_date = state.get("last_allocation_date")

    def _save_state(self) -> None:
        _save_json(TREASURY_STATE_FILE, {
            "api_daily_budget": self.api_manager.daily_budget,
            "api_used_today": self.api_manager.used_today,
            "hosting_daily_budget": self.hosting_manager.daily_budget,
            "hosting_tier": self.hosting_manager.current_tier,
            "models_daily_budget": self.model_manager.daily_budget,
            "model": self.model_manager.current_model,
            "reserve_balance": self.reserve_manager.reserve_balance,
            "last_allocation_date": self._last_allocation_date,
        })

    async def allocate_daily_earnings(self, earnings: Optional[float] = None) -> Dict[str, Any]:
        today = datetime.utcnow().strftime("%Y-%m-%d")
        if earnings is None:
            if rollercoin_bot is None:
                earnings = 0.0
            else:
                try:
                    earnings = float(rollercoin_bot.get_daily_earnings())
                except Exception:
                    earnings = 0.0

        allocation = self.budget.allocate(earnings)

        self.api_manager.set_daily_budget(allocation["apis_premium"])
        self.hosting_manager.set_daily_budget(allocation["hosting"])
        self.model_manager.set_daily_budget(allocation["models"])
        self.reserve_manager.add_to_reserve(allocation["reserve"])
        self._last_allocation_date = today
        self._save_state()

        entry = {
            "date": today,
            "earnings": round(earnings, 4),
            "allocation": allocation,
            "infrastructure_status": self.get_infrastructure_status(),
        }
        self.daily_allocation_history.append(entry)
        try:
            with open(ALLOCATION_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as exc:
            logger.error("No se pudo escribir allocation log: %s", exc)

        logger.info("Daily allocation done: %s", json.dumps(entry, ensure_ascii=False))
        return entry

    def get_infrastructure_status(self) -> Dict[str, Any]:
        return {
            "api_budget": self.api_manager.get_status(),
            "hosting": self.hosting_manager.get_status(),
            "models": self.model_manager.get_status(),
            "reserve": self.reserve_manager.get_status(),
        }

    def get_allocation_forecast(self, days: int = 7) -> Dict[str, Any]:
        if rollercoin_bot is None:
            today_earnings = 0.0
        else:
            try:
                today_earnings = float(rollercoin_bot.get_daily_earnings())
            except Exception:
                today_earnings = 0.0
        forecast = []
        for day in range(1, days + 1):
            projected = today_earnings * (1.05 ** (day - 1))
            forecast.append({
                "day": day,
                "projected_earnings": round(projected, 4),
                "projected_api_budget": round(projected * 0.30, 4),
                "projected_hosting_tier": self._estimate_tier(projected * 0.40),
            })
        return {"forecast": forecast, "growth_rate": "5% daily (conservative)"}

    def _estimate_tier(self, budget: float) -> str:
        if budget >= 50:
            return "premium"
        if budget >= 30:
            return "pro"
        if budget >= 10:
            return "basic"
        return "free"

    def override_allocation(self, apis: Optional[float] = None, hosting: Optional[float] = None,
                           models: Optional[float] = None, reserve: Optional[float] = None) -> Dict[str, Any]:
        if apis is not None:
            self.api_manager.set_daily_budget(apis)
        if hosting is not None:
            self.hosting_manager.set_daily_budget(hosting)
        if models is not None:
            self.model_manager.set_daily_budget(models)
        if reserve is not None:
            self.reserve_manager.add_to_reserve(reserve)
        self._save_state()
        return self.get_infrastructure_status()


treasury_manager = TreasuryManager()
