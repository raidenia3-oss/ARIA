"""Telemetry API service for AURA backend."""

from __future__ import annotations

import json
from pathlib import Path
from typing import List

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="AURA Telemetry API", version="1.0.0")

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "db.json"


class BotStatus(BaseModel):
    id: str
    name: str
    status: str  # Idle | Running | Blocked


class BalanceResponse(BaseModel):
    total_balance: float
    currency: str = "USD"


class ActivityLog(BaseModel):
    ts: str
    level: str
    message: str


class SuccessRateResponse(BaseModel):
    rate: float
    total_tasks: int
    successful_tasks: int


def load_db() -> dict:
    if DB_PATH.exists():
        with open(DB_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "bots": [
            {"id": "bot-1", "name": "Roller Miner", "status": "Idle"},
            {"id": "bot-2", "name": "Survey Harvester", "status": "Running"},
            {"id": "bot-3", "name": "OSINT Recon", "status": "Blocked"},
        ],
        "balance": {"total_balance": 0.0, "currency": "USD"},
        "stats": {"total_tasks": 0, "successful_tasks": 0, "failed_tasks": 0},
        "logs": [],
    }


@app.get("/status", response_model=List[BotStatus])
def get_status() -> List[BotStatus]:
    data = load_db()
    bots = data.get("bots", [])
    return [
        BotStatus(
            id=bot.get("id", f"bot-{idx}"),
            name=bot.get("name", f"Bot {idx}"),
            status=bot.get("status", "Idle"),
        )
        for idx, bot in enumerate(bots, start=1)
    ]


@app.get("/balance", response_model=BalanceResponse)
def get_balance() -> BalanceResponse:
    data = load_db()
    balance = data.get("balance", {})
    return BalanceResponse(
        total_balance=float(balance.get("total_balance", 0.0)),
        currency=balance.get("currency", "USD"),
    )


@app.get("/activity", response_model=List[ActivityLog])
def get_activity(limit: int = 5) -> List[ActivityLog]:
    data = load_db()
    logs = data.get("logs", [])
    critical_levels = {"ERROR", "WARN", "CRITICAL"}
    filtered = [log for log in logs if log.get("level") in critical_levels]
    filtered.sort(key=lambda x: x.get("ts", ""), reverse=True)
    return [
        ActivityLog(
            ts=log.get("ts", ""),
            level=log.get("level", "INFO"),
            message=log.get("message", ""),
        )
        for log in filtered[: max(1, min(limit, 20))]
    ]


@app.get("/success-rate", response_model=SuccessRateResponse)
def get_success_rate() -> SuccessRateResponse:
    data = load_db()
    stats = data.get("stats", {})
    total = int(stats.get("total_tasks", 0))
    successful = int(stats.get("successful_tasks", 0))
    rate = round(successful / total * 100, 1) if total > 0 else 0.0
    return SuccessRateResponse(rate=rate, total_tasks=total, successful_tasks=successful)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "api_service"}
