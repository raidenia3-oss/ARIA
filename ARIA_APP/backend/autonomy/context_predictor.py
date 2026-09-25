"""Context Predictor — UNIFIED. Predicción contextual proactiva.

Analiza tiempo, patrones, historial y estado del sistema para
predecir qué necesita el usuario antes de que lo pida.
"""

import json
import psutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class ContextPredictor:
    """Predice necesidades basándose en contexto completo — UNIFIED."""

    def __init__(self, adaptive_engine=None):
        self.adaptive = adaptive_engine
        self.context_history: List[dict] = []
        self.patterns: Dict[str, Any] = {}
        self.predictions: List[dict] = []
        self._load_patterns()

    def _load_patterns(self):
        try:
            path = Path('ARIA_APP/data/context_patterns.json')
            if path.exists():
                with open(path) as f:
                    self.patterns = json.load(f)
        except Exception:
            pass

    def save_patterns(self):
        try:
            path = Path('ARIA_APP/data/context_patterns.json')
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, 'w') as f:
                json.dump(self.patterns, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[ContextPredictor] Save error: {e}")

    def predict(self) -> List[Dict]:
        now = datetime.now()
        hour = now.hour
        day = now.strftime('%A')
        is_weekend = day in ('Saturday', 'Sunday')
        month = now.month

        predictions = []
        predictions.extend(self._time_based_predictions(hour, is_weekend, month))
        predictions.extend(self._system_based_predictions())
        predictions.extend(self._pattern_based_predictions(now))
        predictions.extend(self._behavior_based_predictions(now))
        predictions.extend(self._contextual_predictions(now))

        predictions.sort(key=lambda p: p.get('confidence', 0), reverse=True)
        self.predictions = predictions
        return predictions

    def _time_based_predictions(self, hour: int, weekend: bool, month: int) -> List[Dict]:
        predictions = []
        if 5 <= hour <= 8:
            predictions.append({'type': 'morning_start', 'message': 'Hora de comenzar el día. ¿Necesitas revisar tus tareas?', 'confidence': 0.88, 'category': 'time', 'action': 'show_tasks'})
        elif 8 < hour <= 12:
            predictions.append({'type': 'peak_productivity', 'message': 'Máxima productividad. ¿Activar modo enfoque?', 'confidence': 0.85, 'category': 'time', 'action': 'focus_mode'})
        elif 12 < hour <= 14:
            predictions.append({'type': 'midday_break', 'message': 'Mediodía. ¿Necesitas descansar?', 'confidence': 0.78, 'category': 'time', 'action': 'suggest_break'})
        elif 14 < hour <= 17:
            predictions.append({'type': 'afternoon_work', 'message': 'Tarde de trabajo. ¿Revisando progreso?', 'confidence': 0.82, 'category': 'time', 'action': 'show_progress'})
        elif 17 < hour <= 20:
            predictions.append({'type': 'evening_transition', 'message': 'Fin del trabajo. ¿Quieres guardar el estado?', 'confidence': 0.80, 'category': 'time', 'action': 'save_state'})
        elif 20 < hour <= 23:
            predictions.append({'type': 'night_review', 'message': 'Hora de revisar lo aprendido hoy.', 'confidence': 0.75, 'category': 'time', 'action': 'show_learning'})
        else:
            predictions.append({'type': 'sleep_mode', 'message': '¿Preparándote para dormir? Guardo tu sesión.', 'confidence': 0.72, 'category': 'time', 'action': 'sleep_prep'})

        if weekend:
            predictions.append({'type': 'weekend_mode', 'message': 'Fin de semana. ¿Modo relajación o productividad?', 'confidence': 0.76, 'category': 'time', 'action': 'weekend_mode'})

        return predictions

    def _system_based_predictions(self) -> List[Dict]:
        predictions = []
        try:
            cpu = psutil.cpu_percent(interval=0.5)
            memory = psutil.virtual_memory()
            if cpu > 70:
                predictions.append({'type': 'system_optimization', 'message': 'Alto uso de CPU. ¿Liberar recursos?', 'confidence': 0.82, 'category': 'system', 'action': 'optimize_cpu'})
            if memory.percent > 80:
                predictions.append({'type': 'memory_management', 'message': 'Memoria al 80%. ¿Limpiar caché?', 'confidence': 0.80, 'category': 'system', 'action': 'manage_memory'})
        except Exception:
            pass
        return predictions

    def _pattern_based_predictions(self, now: datetime) -> List[Dict]:
        predictions = []
        if not self.adaptive:
            return predictions
        patterns = self.adaptive.user_profile.get('behavior_patterns', [])
        if len(patterns) < 5:
            return predictions
        hour = now.hour
        hour_patterns = [p for p in patterns if p.get('hour') == hour]
        if len(hour_patterns) >= 2:
            top_intent = max(set(p.get('intent', 'unknown') for p in hour_patterns), key=lambda i: sum(1 for x in hour_patterns if x.get('intent') == i))
            predictions.append({'type': 'habitual_action', 'message': f'Sueles hacer "{top_intent}" a esta hora. ¿Activar?', 'confidence': 0.75, 'category': 'pattern', 'action': top_intent})
        return predictions

    def _behavior_based_predictions(self, now: datetime) -> List[Dict]:
        predictions = []
        if not self.adaptive:
            return predictions
        patterns = self.adaptive.user_profile.get('behavior_patterns', [])
        if len(patterns) < 3:
            return predictions
        last_5 = patterns[-5:]
        intents = [p.get('intent', 'unknown') for p in last_5]
        unique = list(set(intents))
        if len(unique) == 1 and unique[0] != 'conversation':
            predictions.append({'type': 'repeated_action', 'message': f'Has repetido "{unique[0]}" varias veces. ¿Automatizar?', 'confidence': 0.75, 'category': 'behavior', 'action': 'automate'})
        return predictions

    def _contextual_predictions(self, now: datetime) -> List[Dict]:
        predictions = []
        time_since_last = None
        if self.adaptive and self.adaptive.user_profile.get('last_active'):
            try:
                last = datetime.fromisoformat(self.adaptive.user_profile['last_active'])
                time_since_last = (now - last).total_seconds()
            except Exception:
                pass
        if time_since_last and time_since_last > 3600:
            predictions.append({'type': 'returning_user', 'message': 'Hace mucho que no nos vemos. ¿Todo bien?', 'confidence': 0.70, 'category': 'context', 'action': 'check_in'})
        elif time_since_last and time_since_last < 300:
            predictions.append({'type': 'ongoing_session', 'message': 'Sigues activo. ¿Algo más?', 'confidence': 0.68, 'category': 'context', 'action': 'check_continue'})
        return predictions

    def get_top_predictions(self, limit: int = 3) -> List[Dict]:
        return self.predictions[:limit]

    def record_context(self, context: Dict):
        context['timestamp'] = datetime.now().isoformat()
        self.context_history.append(context)
        if len(self.context_history) > 1000:
            self.context_history = self.context_history[-1000:]
