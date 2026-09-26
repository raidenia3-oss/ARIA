"""Learning System — Aprendizaje continuo"""

from typing import Any, Dict


class LearningSystem:
    """Sistema de aprendizaje continuo"""

    def __init__(self):
        self.learned_items = []

    async def learn_from(self, situation: str, decision: Dict, explanation: Dict) -> Dict:
        """Aprende de situación-decisión"""
        entry = {
            'situation': situation,
            'decision': decision,
            'explanation': explanation,
            'learned': True,
        }
        self.learned_items.append(entry)
        return {'status': 'learned', 'total': len(self.learned_items)}
