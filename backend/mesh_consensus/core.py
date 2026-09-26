"""BLOQUE 89 - Swarm consensus core (quorum/majority, local)."""
from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

QUORUM_RATIO = 0.51
DEFAULT_TTL_S = 30.0
MAX_ROUNDS = 200


@dataclass
class ConsensusRound:
    round_id: str = ""
    topic: str = ""
    proposal: str = ""
    voters: List[str] = field(default_factory=list)
    votes: Dict[str, str] = field(default_factory=dict)
    status: str = "open"
    result: str = ""
    created_at: float = 0.0
    closed_at: float = 0.0
    ttl_s: float = DEFAULT_TTL_S

    def __post_init__(self) -> None:
        if not self.round_id:
            self.round_id = uuid.uuid4().hex[:12]
        if not self.created_at:
            self.created_at = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {"round_id": self.round_id, "topic": self.topic,
                "proposal": self.proposal, "voters": list(self.voters),
                "votes": dict(self.votes), "status": self.status,
                "result": self.result, "created_at": self.created_at,
                "closed_at": self.closed_at, "offline_only": True}
