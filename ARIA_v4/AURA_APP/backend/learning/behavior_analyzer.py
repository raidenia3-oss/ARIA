"""Behavior Analyzer — Analiza patrones con auto-aprendizaje.

Mejorado para:
- Detección automática de patrones horarios
- Clasificación de tipo de interacción
- Predicción de próximas acciones
- Auto-generación de insights
"""

import json
import statistics
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


class BehaviorAnalyzer:
    """Analiza patrones con auto-aprendizaje."""

    def __init__(self):
        self.patterns_file = Path('ARIA_v4/AURA_APP/data/behavior_patterns.json')
        self.patterns = self._load()
        self.insights: List[dict] = []

    def _load(self) -> dict:
        if self.patterns_file.exists():
            try:
                with open(self.patterns_file) as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            'interactions': [],
            'hourly': {},
            'commands': {},
            'intents': {},
            'session_lengths': [],
            'context_switches': [],
        }

    async def analyze(self, user_input: str, intent: str = 'unknown') -> Dict:
        now = datetime.now()
        hour = now.hour

        interaction = {
            'time': now.isoformat(),
            'hour': hour,
            'day': now.strftime('%A'),
            'day_of_week': now.weekday(),
            'input': user_input,
            'intent': intent,
            'type': self._classify_interaction(user_input, intent),
            'complexity': self._estimate_complexity(user_input),
            'duration_estimate': self._estimate_duration(intent),
        }

        self.patterns['interactions'].append(interaction)

        self._update_hourly(hour)
        self._update_intents(intent)
        self._update_commands(user_input, intent)

        await self._save()
        await self._generate_insights()

        return interaction

    def _classify_interaction(self, user_input: str, intent: str) -> str:
        lower = user_input.lower()
        if intent == 'activate':
            return 'startup'
        elif intent in ('learn', 'memoriza', 'recuerda'):
            return 'learning'
        elif intent == 'greet':
            return 'social'
        elif intent == 'query':
            if any(w in lower for w in ['hora', 'tiempo', 'clima', 'fecha']):
                return 'information_query'
            return 'general_query'
        elif intent == 'search':
            return 'research'
        elif intent == 'maximize':
            return 'configuration'
        elif intent == 'usb':
            return 'hardware'
        elif any(w in lower for w in ['ayuda', 'help', 'qué puedes', 'qué haces']):
            return 'discovery'
        elif len(user_input.strip()) < 5:
            return 'brief'
        else:
            return 'conversation'

    def _estimate_complexity(self, user_input: str) -> float:
        words = len(user_input.split())
        if words < 3:
            return 0.2
        elif words < 7:
            return 0.5
        elif words < 15:
            return 0.7
        else:
            return 0.9

    def _estimate_duration(self, intent: str) -> int:
        durations = {
            'greet': 10,
            'query': 60,
            'search': 120,
            'learning': 180,
            'conversation': 300,
            'configuration': 240,
            'hardware': 90,
        }
        return durations.get(intent, 120)

    def _update_hourly(self, hour: int):
        key = str(hour)
        if key not in self.patterns['hourly']:
            self.patterns['hourly'][key] = {'count': 0, 'intents': []}
        self.patterns['hourly'][key]['count'] += 1

    def _update_intents(self, intent: str):
        if intent not in self.patterns['intents']:
            self.patterns['intents'][intent] = 0
        self.patterns['intents'][intent] += 1

    def _update_commands(self, user_input: str, intent: str):
        first_word = user_input.strip()[:30].lower()
        if first_word not in self.patterns['commands']:
            self.patterns['commands'][first_word] = {'count': 0, 'intent': intent}
        self.patterns['commands'][first_word]['count'] += 1

    async def _generate_insights(self):
        """Genera insights automáticos."""
        interactions = self.patterns['interactions']
        if len(interactions) < 5:
            return

        recent = interactions[-20:]
        intents = [i.get('intent', 'unknown') for i in recent]
        from collections import Counter
        intent_counts = Counter(intents)
        top_intent = intent_counts.most_common(1)[0]

        if top_intent[1] >= 5:
            insight = {
                'type': 'dominant_intent',
                'message': f'Predominantemente usas "{top_intent[0]}"',
                'confidence': 0.85,
                'generated_at': datetime.now().isoformat(),
            }
            if not any(ins.get('type') == 'dominant_intent' for ins in self.insights[-5:]):
                self.insights.append(insight)

        hourly = self.patterns.get('hourly', {})
        if hourly:
            peak_hour = max(hourly.items(), key=lambda x: x[1].get('count', 0))
            insight = {
                'type': 'peak_hour',
                'message': f'Más activo a las {peak_hour[0]}:00',
                'confidence': 0.80,
                'generated_at': datetime.now().isoformat(),
            }
            if not any(ins.get('type') == 'peak_hour' for ins in self.insights[-5:]):
                self.insights.append(insight)

        await self._save_insights()

    async def _save(self):
        try:
            self.patterns_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.patterns_file, 'w') as f:
                data = dict(self.patterns)
                data['interactions'] = data['interactions'][-500:]
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[BehaviorAnalyzer] Save error: {e}")

    async def _save_insights(self):
        try:
            insights_file = self.patterns_file.parent / 'insights.json'
            with open(insights_file, 'w') as f:
                json.dump(self.insights[-50:], f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[BehaviorAnalyzer] Insights save error: {e}")

    def get_patterns(self) -> Dict:
        return self.patterns

    def get_insights(self, limit: int = 10) -> List[dict]:
        return self.insights[-limit:]

    def get_peak_hours(self) -> List[Dict]:
        hourly = self.patterns.get('hourly', {})
        sorted_hours = sorted(hourly.items(), key=lambda x: x[1].get('count', 0), reverse=True)
        return [
            {'hour': int(h), 'count': d.get('count', 0)}
            for h, d in sorted_hours[:5]
        ]

    def get_intent_distribution(self) -> Dict:
        total = sum(self.patterns.get('intents', {}).values())
        if total == 0:
            return {}
        return {
            intent: round(count / total, 3)
            for intent, count in self.patterns.get('intents', {}).items()
        }
