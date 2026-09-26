"""Adaptive Learner — Aprende del usuario"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List


class AdaptiveLearner:
    """Aprende patrones y se adapta al usuario"""

    def __init__(self):
        self.history_file = Path('ARIA_v4/AURA_APP/data/adaptive_history.json')
        self.history = self._load()

    def _load(self) -> List[dict]:
        if self.history_file.exists():
            with open(self.history_file) as f:
                return json.load(f)
        return []

    async def learn(self, interaction: Dict) -> None:
        interaction['timestamp'] = datetime.now().isoformat()
        self.history.append(interaction)
        await self._save()

    async def _save(self) -> None:
        with open(self.history_file, 'w') as f:
            json.dump(self.history[-1000:], f, indent=2)

    async def get_preferences(self) -> Dict:
        if len(self.history) < 5:
            return {}

        preferences = {
            'total_interactions': len(self.history),
            'common_intents': {},
            'peak_hours': {},
        }

        for h in self.history:
            intent = h.get('intent', 'unknown')
            preferences['common_intents'][intent] = preferences['common_intents'].get(intent, 0) + 1

        return preferences

    async def should_adapt(self) -> bool:
        return len(self.history) > 10
