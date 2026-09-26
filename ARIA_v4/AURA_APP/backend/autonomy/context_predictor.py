"""Context Predictor — Predicción contextual proactiva.

Analiza tiempo, patrones, historial y estado del sistema para
predecir qué necesita el usuario antes de que lo pida.
"""

import json
import psutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class ContextPredictor:
    """Predice necesidades basándose en contexto completo."""

    def __init__(self, adaptive_engine=None):
        self.adaptive = adaptive_engine
        self.context_history: List[dict] = []
        self.patterns: Dict[str, Any] = {}
        self.predictions: List[dict] = []
        self._load_patterns()

    def _load_patterns(self):
        """Carga patrones almacenados."""
        try:
            path = Path('ARIA_v4/AURA_APP/data/context_patterns.json')
            if path.exists():
                with open(path) as f:
                    self.patterns = json.load(f)
        except Exception:
            pass

    def save_patterns(self):
        """Guarda patrones."""
        try:
            path = Path('ARIA_v4/AURA_APP/data/context_patterns.json')
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, 'w') as f:
                json.dump(self.patterns, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[ContextPredictor] Save error: {e}")

    def predict(self) -> List[Dict]:
        """Genera predicciones basadas en contexto actual."""
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
        """Predicciones basadas en hora."""
        predictions = []

        if 5 <= hour <= 8:
            predictions.append({
                'type': 'morning_start',
                'message': 'Hora de comenzar el día. ¿Deseas ver tus tareas pendientes?',
                'confidence': 0.88,
                'category': 'time',
                'action': 'show_tasks',
            })
        elif 8 < hour <= 12:
            predictions.append({
                'type': 'peak_productivity',
                'message': 'Máxima productividad. ¿Activar modo enfoque?',
                'confidence': 0.85,
                'category': 'time',
                'action': 'focus_mode',
            })
        elif 12 < hour <= 14:
            predictions.append({
                'type': 'midday_break',
                'message': 'Mediodía. ¿Necesitas descansar o quieres seguir trabajando?',
                'confidence': 0.78,
                'category': 'time',
                'action': 'suggest_break',
            })
        elif 14 < hour <= 17:
            predictions.append({
                'type': 'afternoon_work',
                'message': 'Tarde de trabajo. ¿Revisando el progreso del día?',
                'confidence': 0.82,
                'category': 'time',
                'action': 'show_progress',
            })
        elif 17 < hour <= 20:
            predictions.append({
                'type': 'evening_transition',
                'message': 'Fin del trabajo. ¿Quieres guardar el estado actual?',
                'confidence': 0.80,
                'category': 'time',
                'action': 'save_state',
            })
        elif 20 < hour <= 23:
            predictions.append({
                'type': 'night_review',
                'message': 'Hora de revisar lo aprendido hoy.',
                'confidence': 0.75,
                'category': 'time',
                'action': 'show_learning',
            })
        else:
            predictions.append({
                'type': 'sleep_mode',
                'message': '¿Preparándote para dormir? Guardo tu sesión.',
                'confidence': 0.72,
                'category': 'time',
                'action': 'sleep_prep',
            })

        if weekend:
            predictions.append({
                'type': 'weekend_mode',
                'message': 'Fin de semana. ¿Modo relajación o productividad personal?',
                'confidence': 0.76,
                'category': 'time',
                'action': 'weekend_mode',
            })

        if month in (9, 10, 11) and hour <= 9:
            predictions.append({
                'type': 'seasonal',
                'message': 'Cambio de estación. ¿Ajustar temperatura o crear recordatorios?',
                'confidence': 0.65,
                'category': 'time',
                'action': 'seasonal_adjust',
            })

        return predictions

    def _system_based_predictions(self) -> List[Dict]:
        """Predicciones basadas en estado del sistema."""
        predictions = []

        try:
            cpu = psutil.cpu_percent(interval=0.5)
            memory = psutil.virtual_memory()

            if cpu > 70:
                predictions.append({
                    'type': 'system_optimization',
                    'message': 'Alto uso de CPU. ¿Liberar recursos automáticamente?',
                    'confidence': 0.82,
                    'category': 'system',
                    'action': 'optimize_cpu',
                })
            if memory.percent > 80:
                predictions.append({
                    'type': 'memory_management',
                    'message': 'Memoria al 80%%. ¿Limpiar caché y cerrar innecesarios?',
                    'confidence': 0.80,
                    'category': 'system',
                    'action': 'manage_memory',
                })
        except Exception:
            pass

        disk_usage = psutil.disk_usage('C:') if os.name == 'nt' else psutil.disk_usage('/')
        if disk_usage.percent > 90:
            predictions.append({
                'type': 'disk_warning',
                'message': 'Disco casi lleno. ¿Liberar espacio o mover datos a USB?',
                'confidence': 0.85,
                'category': 'storage',
                'action': 'disk_cleanup',
            })

        return predictions

    def _pattern_based_predictions(self, now: datetime) -> List[Dict]:
        """Predicciones basadas en patrones históricos."""
        predictions = []

        if not self.adaptive:
            return predictions

        patterns = self.adaptive.user_profile.get('behavior_patterns', [])
        if len(patterns) < 5:
            return predictions

        recent = patterns[-50:]
        hour = now.hour
        hour_actions = {}
        for p in recent:
            if p.get('hour') == hour:
                intent = p.get('intent', 'unknown')
                hour_actions[intent] = hour_actions.get(intent, 0) + 1

        if hour_actions:
            top_action = max(hour_actions, key=hour_actions.get)
            count = hour_actions[top_action]
            if count >= 2 and top_action != 'conversation':
                predictions.append({
                    'type': 'habitual_action',
                    'message': f'Sueles hacer "{top_action}" a esta hora. ¿Activarlo?',
                    'confidence': min(0.90, 0.60 + count * 0.05),
                    'category': 'pattern',
                    'action': top_action,
                })

        return predictions

    def _behavior_based_predictions(self, now: datetime) -> List[Dict]:
        """Predicciones basadas en comportamiento reciente."""
        predictions = []

        if not self.adaptive:
            return predictions

        patterns = self.adaptive.user_profile.get('behavior_patterns', [])
        if len(patterns) < 3:
            return predictions

        last_5 = patterns[-5:]
        intents = [p.get('intent', 'unknown') for p in last_5]
        unique_intents = list(set(intents))

        if len(unique_intents) == 1 and unique_intents[0] != 'conversation':
            predictions.append({
                'type': 'repeated_action',
                'message': f'Has repetido "{unique_intents[0]}" varias veces. ¿Quieres automatizarlo?',
                'confidence': 0.75,
                'category': 'behavior',
                'action': 'automate',
            })

        try:
            freq = len(patterns) / max((now - datetime.fromisoformat(patterns[0].get('timestamp', now.isoformat()))).total_seconds() / 3600, 0.1)
            if freq > 5:
                predictions.append({
                    'type': 'high_activity',
                    'message': 'Alta actividad detectada. ¿Necesitas ayuda organizando?',
                    'confidence': 0.72,
                    'category': 'behavior',
                    'action': 'help_organize',
                })
        except Exception:
            pass

        return predictions

    def _contextual_predictions(self, now: datetime) -> List[Dict]:
        """Predicciones contextuales diversas."""
        predictions = []

        time_since_last = None
        if self.adaptive and self.adaptive.user_profile.get('last_active'):
            try:
                last = datetime.fromisoformat(self.adaptive.user_profile['last_active'])
                time_since_last = (now - last).total_seconds()
            except Exception:
                pass

        if time_since_last and time_since_last > 3600:
            predictions.append({
                'type': 'returning_user',
                'message': 'Hace mucho que no nos vemos. ¿Todo bien?',
                'confidence': 0.70,
                'category': 'context',
                'action': 'check_in',
            })

        if time_since_last and time_since_last < 300:
            predictions.append({
                'type': 'ongoing_session',
                'message': 'Sigues activo. ¿Algo más que necesites?',
                'confidence': 0.68,
                'category': 'context',
                'action': 'check_continue',
            })

        return predictions

    def get_top_predictions(self, limit: int = 3) -> List[Dict]:
        """Obtiene las predicciones con mayor confianza."""
        return [p for p in self.predictions[:limit]]

    def record_context(self, context: Dict):
        """Registra contexto para análisis."""
        context['timestamp'] = datetime.now().isoformat()
        self.context_history.append(context)
        if len(self.context_history) > 1000:
            self.context_history = self.context_history[-1000:]
