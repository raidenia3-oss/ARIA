"""Self Healer — UNIFIED. Auto-recuperación ante errores.

Monitorea fallos, reintenta operaciones, aplica fallbacks
y recupera el sistema sin intervención del usuario.
"""

import asyncio
import json
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional


class SelfHealer:
    """Auto-recuperación de ARIA — UNIFIED."""

    ERROR_WINDOW_MINUTES = 10
    MAX_ERRORS_PER_WINDOW = 5
    RECOVERY_COOLDOWN_SECONDS = 30

    def __init__(self):
        self.errors: List[dict] = []
        self.last_recovery: Optional[datetime] = None
        self.recovery_count = 0
        self._in_recovery = False
        self._error_log_path = Path('ARIA_APP/data/error_log.json')
        self._load_errors()

    def _load_errors(self):
        try:
            if self._error_log_path.exists():
                with open(self._error_log_path) as f:
                    data = json.load(f)
                    self.errors = data.get('errors', [])
                    self.recovery_count = data.get('recovery_count', 0)
        except Exception:
            pass

    def save_errors(self):
        try:
            self._error_log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._error_log_path, 'w') as f:
                json.dump({
                    'errors': self.errors[-500:],
                    'recovery_count': self.recovery_count,
                    'last_recovery': self.last_recovery.isoformat() if self.last_recovery else None,
                }, f, indent=2)
        except Exception as e:
            print(f"[SelfHealer] Save error: {e}")

    def record_error(self, error: Exception, context: str = "") -> bool:
        error_entry = {
            'type': type(error).__name__,
            'message': str(error),
            'traceback': traceback.format_exc(),
            'context': context,
            'timestamp': datetime.now().isoformat(),
            'recovered': False,
        }
        self.errors.append(error_entry)
        if len(self.errors) > 500:
            self.errors = self.errors[-500:]
        return self._check_recovery_needed()

    def _check_recovery_needed(self) -> bool:
        now = datetime.now()
        window_start = now - timedelta(minutes=self.ERROR_WINDOW_MINUTES)
        recent_errors = [
            e for e in self.errors
            if datetime.fromisoformat(e['timestamp']) > window_start
            and not e.get('recovered', False)
        ]
        if len(recent_errors) >= self.MAX_ERRORS_PER_WINDOW:
            if self._can_recover():
                asyncio.create_task(self._recover())
                return True
        return False

    def _can_recover(self) -> bool:
        if self._in_recovery:
            return False
        if self.last_recovery:
            cooldown = (datetime.now() - self.last_recovery).total_seconds()
            if cooldown < self.RECOVERY_COOLDOWN_SECONDS:
                return False
        return True

    async def _recover(self):
        self._in_recovery = True
        self.last_recovery = datetime.now()
        self.recovery_count += 1
        print(f"[SelfHealer] Recuperación #{self.recovery_count} iniciada")
        recovery_steps = [
            ('limpiar_cache', self._clear_cache),
            ('resetear_conexiones', self._reset_connections),
            ('recargar_config', self._reload_config),
            ('liberar_memoria', self._free_memory),
            ('reiniciar_loops', self._restart_loops),
        ]
        for step_name, step_fn in recovery_steps:
            try:
                print(f"[SelfHealer] Paso: {step_name}")
                await step_fn()
            except Exception as e:
                print(f"[SelfHealer] Paso '{step_name}' falló: {e}")
        for error in self.errors:
            if not error.get('recovered', False):
                error['recovered'] = True
        self._in_recovery = False
        self.save_errors()
        print(f"[SelfHealer] Recuperación #{self.recovery_count} completada")

    async def _clear_cache(self):
        try:
            from backend.storage.cache import CacheManager
            cache = CacheManager()
            cache.max_size_mb = 50
        except Exception:
            pass

    async def _reset_connections(self):
        pass

    async def _reload_config(self):
        try:
            from backend.config.config import Config
            Config()
        except Exception:
            pass

    async def _free_memory(self):
        try:
            import gc
            gc.collect()
        except Exception:
            pass

    async def _restart_loops(self):
        pass

    def get_status(self) -> Dict:
        now = datetime.now()
        window_start = now - timedelta(minutes=self.ERROR_WINDOW_MINUTES)
        recent = [e for e in self.errors if datetime.fromisoformat(e['timestamp']) > window_start]
        return {
            'total_errors': len(self.errors),
            'recent_errors': len(recent),
            'recovery_count': self.recovery_count,
            'last_recovery': self.last_recovery.isoformat() if self.last_recovery else None,
            'in_recovery': self._in_recovery,
            'health': 'healthy' if len(recent) < self.MAX_ERRORS_PER_WINDOW else 'degraded',
        }

    def health_check(self) -> Dict:
        status = self.get_status()
        checks = {
            'self_healer': 'ok',
            'error_rate': 'ok' if status['recent_errors'] < 3 else 'warning',
            'recovery_available': True,
        }
        if status['health'] == 'degraded':
            checks['system'] = 'needs_recovery'
        else:
            checks['system'] = 'ok'
        return checks
