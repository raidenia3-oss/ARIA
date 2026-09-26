"""Memory Manager — Short/Long term memory"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


class MemoryManager:
    """Gestión de memoria (short/long term)"""

    def __init__(self):
        self.short_term = []
        self.long_term = []
        self.short_path = Path('ARIA_v4/AURA_APP/data/short_term.json')
        self.long_path = Path('ARIA_v4/AURA_APP/data/long_term.json')

    async def load(self) -> None:
        if self.short_path.exists():
            with open(self.short_path) as f:
                self.short_term = json.load(f)
        if self.long_path.exists():
            with open(self.long_path) as f:
                self.long_term = json.load(f)

    async def save(self) -> None:
        with open(self.short_path, 'w') as f:
            json.dump(self.short_term[:100], f, indent=2)
        with open(self.long_path, 'w') as f:
            json.dump(self.long_term, f, indent=2)

    async def remember(self, text: str, meta: dict = None) -> None:
        entry = {'text': text, 'timestamp': datetime.now().isoformat(), **(meta or {})}
        self.short_term.append(entry)
        if len(self.short_term) > 50:
            self.long_term.append(self.short_term.pop(0))

    async def recall(self, query: str, limit: int = 5) -> List[dict]:
        return [m for m in self.short_term + self.long_term if query.lower() in str(m).lower()][:limit]

    async def learn(self, user_input: str, result: dict) -> None:
        await self.remember(user_input, {'result': result})

    def all_short(self) -> List[dict]:
        return self.short_term

    def all_long(self) -> List[dict]:
        return self.long_term
