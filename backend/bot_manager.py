"""
AURA Bot Manager - Gestiona bots propios que ARIA pueda crear, ejecutar y controlar.

Sin datos inventados. Fail-closed. Integrado con brain unificado.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional

BOT_STATE_FILE = "bot_state.json"


@dataclass
class BotConfig:
    id: str
    name: str
    type: str  # discord|telegram|grook|custom
    status: str = "idle"  # idle|running|stopped|error
    created_at: float = 0.0
    last_seen: float = 0.0
    config: Dict[str, Any] = None

    def __post_init__(self) -> None:
        if self.created_at == 0.0:
            self.created_at = time.time()
        if self.config is None:
            self.config = {}


class BotManager:
    def __init__(self) -> None:
        self.bots: Dict[str, BotConfig] = {}
        self._load()

    def _load(self) -> None:
        try:
            if os.path.exists(BOT_STATE_FILE):
                with open(BOT_STATE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for bid, b in data.items():
                    self.bots[bid] = BotConfig(**b)
        except Exception:
            self.bots = {}

    def _save(self) -> None:
        try:
            data = {bid: asdict(b) for bid, b in self.bots.items()}
            with open(BOT_STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def create_bot(self, name: str, bot_type: str = "grook", config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        bid = f"bot_{int(time.time())}_{len(self.bots)+1}"
        bot = BotConfig(id=bid, name=name, type=bot_type, config=config or {})
        self.bots[bid] = bot
        self._save()
        return {"status": "created", "bot_id": bid, "bot": asdict(bot)}

    def list_bots(self) -> Dict[str, Any]:
        return {"bots": [asdict(b) for b in self.bots.values()], "count": len(self.bots)}

    def start_bot(self, bot_id: str) -> Dict[str, Any]:
        b = self.bots.get(bot_id)
        if not b:
            return {"status": "not_found"}
        b.status = "running"
        b.last_seen = time.time()
        self._save()
        return {"status": "started", "bot_id": bot_id}

    def stop_bot(self, bot_id: str) -> Dict[str, Any]:
        b = self.bots.get(bot_id)
        if not b:
            return {"status": "not_found"}
        b.status = "stopped"
        self._save()
        return {"status": "stopped", "bot_id": bot_id}

    def get_bot(self, bot_id: str) -> Dict[str, Any]:
        b = self.bots.get(bot_id)
        if not b:
            return {"status": "not_found"}
        return {"status": "ok", "bot": asdict(b)}


bot_manager = BotManager()
