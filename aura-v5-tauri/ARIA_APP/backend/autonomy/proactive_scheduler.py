"""Proactive Scheduler — UNIFIED. Programación inteligente basada en patrones.

No usa cron manual — aprende del usuario y programa tareas
automáticamente basándose en comportamiento.
"""

import json
import psutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class ProactiveScheduler:
    """Programador inteligente basado en patrones — UNIFIED."""

    def __init__(self, adaptive_engine=None):
        self.adaptive = adaptive_engine
        self.scheduled_tasks: List[dict] = []
        self.completed_tasks: List[dict] = []
        self._tasks_path = Path('ARIA_APP/data/proactive_tasks.json')
        self._load_tasks()
        self._current_loop = None

    def _load_tasks(self):
        try:
            if self._tasks_path.exists():
                with open(self._tasks_path) as f:
                    data = json.load(f)
                    self.scheduled_tasks = data.get('tasks', [])
                    self.completed_tasks = data.get('completed', [])
        except Exception:
            pass

    def save_tasks(self):
        try:
            self._tasks_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._tasks_path, 'w') as f:
                json.dump({'tasks': self.scheduled_tasks, 'completed': self.completed_tasks[-100:]}, f, indent=2)
        except Exception as e:
            print(f"[ProactiveScheduler] Save error: {e}")

    def generate_tasks(self) -> List[dict]:
        now = datetime.now()
        hour = now.hour
        day = now.strftime('%A')
        predictions = []
        predictions.extend(self._habit_tasks(now))
        predictions.extend(self._system_tasks(now))
        predictions.extend(self._maintenance_tasks(now))
        predictions.extend(self._learning_tasks(now))
        for task in predictions:
            if not any(t.get('id') == task['id'] for t in self.scheduled_tasks):
                self.scheduled_tasks.append(task)
        self.scheduled_tasks = self.scheduled_tasks[-100:]
        self.save_tasks()
        return predictions

    def _habit_tasks(self, now: datetime) -> List[dict]:
        tasks = []
        if not self.adaptive:
            return tasks
        patterns = self.adaptive.user_profile.get('behavior_patterns', [])
        if len(patterns) < 3:
            return tasks
        hour = now.hour
        day = now.strftime('%A')
        habit_counts = {}
        for p in patterns:
            if p.get('hour') == hour and p.get('day') == day:
                intent = p.get('intent', 'unknown')
                habit_counts[intent] = habit_counts.get(intent, 0) + 1
        for intent, count in habit_counts.items():
            if count >= 2 and intent != 'conversation':
                tasks.append({'id': f'habit_{hour}_{day}_{intent}', 'type': 'habit', 'action': intent,
                              'message': f'Sueles hacer "{intent}" a esta hora. ¿Activar?',
                              'priority': min(10, count), 'auto_executable': count >= 3,
                              'timestamp': now.isoformat()})
        return tasks

    def _system_tasks(self, now: datetime) -> List[dict]:
        tasks = []
        try:
            cpu = psutil.cpu_percent(interval=0.3)
            if cpu < 30 and now.hour >= 2:
                tasks.append({'id': f'optimize_{now.strftime("%Y%m%d")}', 'type': 'system_optimize',
                              'action': 'optimize', 'message': 'Sistema tranquilo. ¿Optimizar?',
                              'priority': 5, 'auto_executable': True, 'timestamp': now.isoformat()})
        except Exception:
            pass
        return tasks

    def _maintenance_tasks(self, now: datetime) -> List[dict]:
        tasks = []
        if now.hour == 2 and now.minute < 5:
            tasks.append({'id': f'backup_{now.strftime("%Y%m%d")}', 'type': 'backup', 'action': 'backup',
                          'message': '¿Crear respaldo automático?', 'priority': 7,
                          'auto_executable': False, 'timestamp': now.isoformat()})
        if now.hour == 3 and now.minute < 5:
            tasks.append({'id': f'clean_{now.strftime("%Y%m%d")}', 'type': 'cleanup', 'action': 'cleanup',
                          'message': 'Limpiar archivos temporales y caché.', 'priority': 3,
                          'auto_executable': True, 'timestamp': now.isoformat()})
        return tasks

    def _learning_tasks(self, now: datetime) -> List[dict]:
        tasks = []
        if not self.adaptive:
            return tasks
        history = getattr(self.adaptive, 'learning_history', [])
        if len(history) > 0 and (now.hour == 21 or now.hour == 22):
            tasks.append({'id': f'review_{now.strftime("%Y%m%d")}', 'type': 'learning_review', 'action': 'review',
                          'message': f'Has aprendido {len(history)} cosas. ¿Revisar resumen?',
                          'priority': 6, 'auto_executable': False, 'timestamp': now.isoformat()})
        return tasks

    def complete_task(self, task_id: str):
        for task in self.scheduled_tasks:
            if task.get('id') == task_id:
                task['completed'] = True
                task['completed_at'] = datetime.now().isoformat()
                self.completed_tasks.append(task)
                self.scheduled_tasks.remove(task)
                self.save_tasks()
                return True
        return False

    def get_pending(self) -> List[dict]:
        return [t for t in self.scheduled_tasks if not t.get('completed', False)]

    def get_suggestions(self, limit: int = 3) -> List[dict]:
        pending = self.get_pending()
        pending.sort(key=lambda t: t.get('priority', 0), reverse=True)
        return pending[:limit]
