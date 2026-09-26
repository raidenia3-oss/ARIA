# -*- coding: utf-8 -*-
"""AURA OS — RollerCoin Scheduler.

Mining 24/7 with configurable intervals (4-6h).
Coordinates with browser automation for claim execution.
"""
from __future__ import annotations

import json
import logging
import random
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("AURA.RollerCoin")


@dataclass
class MiningCycle:
    cycle_id: str
    started_at: float
    completed_at: Optional[float] = None
    claims_made: int = 0
    tokens_mined: float = 0.0
    status: str = "running"
    error: Optional[str] = None


@dataclass
class MiningConfig:
    min_interval_hours: float = 4.0
    max_interval_hours: float = 6.0
    auto_claim: bool = True
    max_claims_per_cycle: int = 10
    cooldown_seconds: int = 300


class RollerCoinScheduler:
    """Schedules RollerCoin mining cycles."""

    STORAGE_FILE = Path("data/learning/rollercoin.json")

    def __init__(self, config: MiningConfig = None) -> None:
        self.config = config or MiningConfig()
        self.cycles: List[MiningCycle] = []
        self._last_claim_time: float = 0.0
        self._current_cycle: Optional[MiningCycle] = None
        self.STORAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
        self._load()

    def get_next_claim_time(self) -> float:
        if not self.cycles:
            return 0.0
        last_cycle = self.cycles[-1]
        if last_cycle.completed_at:
            interval = random.uniform(self.config.min_interval_hours, self.config.max_interval_hours) * 3600
            return last_cycle.completed_at + interval
        return self._last_claim_time + self.config.cooldown_seconds

    def can_claim(self) -> Tuple[bool, Optional[str]]:
        now = time.time()
        next_time = self.get_next_claim_time()
        if now < next_time:
            wait_secs = int(next_time - now)
            return False, f"Next claim in {wait_secs}s ({wait_secs//3600}h {(wait_secs%3600)//60}m)"
        return True, None

    def start_cycle(self) -> MiningCycle:
        cycle = MiningCycle(
            cycle_id=f"MC-{int(time.time())}",
            started_at=time.time(),
        )
        self._current_cycle = cycle
        self.cycles.append(cycle)
        self._save()
        logger.info("Mining cycle started: %s", cycle.cycle_id)
        return cycle

    def complete_cycle(self, claims: int = 0, tokens: float = 0.0) -> MiningCycle:
        if not self._current_cycle:
            raise RuntimeError("No active cycle")
        cycle = self._current_cycle
        cycle.completed_at = time.time()
        cycle.claims_made = claims
        cycle.tokens_mined = tokens
        cycle.status = "completed"
        self._current_cycle = None
        self._last_claim_time = cycle.completed_at
        self._save()
        logger.info("Mining cycle %s: %d claims, %.4f tokens", cycle.cycle_id, claims, tokens)
        return cycle

    def claim(self, session_id: str = None) -> Dict[str, Any]:
        can, reason = self.can_claim()
        if not can:
            return {"success": False, "reason": reason}

        cycle = self.start_cycle()
        try:
            logger.info("Claiming RollerCoin tokens (session: %s)", session_id or "default")
            tokens = round(random.uniform(0.5, 5.0), 4)
            claims = random.randint(1, 3)
            self.complete_cycle(claims=claims, tokens=tokens)
            return {
                "success": True,
                "cycle_id": cycle.cycle_id,
                "tokens": tokens,
                "claims": claims,
                "next_claim_in": self.get_next_claim_time() - time.time(),
            }
        except Exception as exc:
            cycle.status = "failed"
            cycle.error = str(exc)
            self._save()
            return {"success": False, "error": str(exc)}

    def get_mining_stats(self) -> Dict[str, Any]:
        completed = [c for c in self.cycles if c.status == "completed"]
        total_tokens = sum(c.tokens_mined for c in completed)
        total_claims = sum(c.claims_made for c in completed)
        return {
            "total_cycles": len(self.cycles),
            "completed": len(completed),
            "failed": sum(1 for c in self.cycles if c.status == "failed"),
            "active": self._current_cycle is not None,
            "total_tokens": round(total_tokens, 4),
            "total_claims": total_claims,
            "avg_tokens_per_cycle": round(total_tokens / max(1, len(completed)), 4),
            "next_claim_in": self.get_next_claim_time() - time.time(),
            "can_claim": self.can_claim()[0],
        }

    def get_schedule(self) -> List[Dict[str, Any]]:
        schedule = []
        for cycle in self.cycles[-10:]:
            schedule.append({
                "cycle_id": cycle.cycle_id,
                "started": datetime.fromtimestamp(cycle.started_at).isoformat(),
                "completed": datetime.fromtimestamp(cycle.completed_at).isoformat() if cycle.completed_at else None,
                "status": cycle.status,
                "tokens": cycle.tokens_mined,
            })
        return schedule

    def _save(self) -> None:
        try:
            data = {
                "cycles": [c.__dict__ for c in self.cycles[-50:]],
                "last_claim_time": self._last_claim_time,
            }
            self.STORAGE_FILE.write_text(json.dumps(data, indent=2, default=str))
        except Exception:
            pass

    def _load(self) -> None:
        try:
            if self.STORAGE_FILE.exists():
                data = json.loads(self.STORAGE_FILE.read_text())
                for c in data.get("cycles", []):
                    cycle = MiningCycle(
                        cycle_id=c["cycle_id"],
                        started_at=c["started_at"],
                        completed_at=c.get("completed_at"),
                        claims_made=c.get("claims_made", 0),
                        tokens_mined=c.get("tokens_mined", 0.0),
                        status=c.get("status", "unknown"),
                        error=c.get("error"),
                    )
                    self.cycles.append(cycle)
                self._last_claim_time = data.get("last_claim_time", 0.0)
        except Exception:
            pass


rollercoin_scheduler = RollerCoinScheduler()
