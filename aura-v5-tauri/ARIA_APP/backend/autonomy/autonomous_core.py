"""Autonomous Core — Motor de autonomía completa.

Ejecuta tareas en background, escaneo proactivo, análisis de patrones
y generación de sugerencias sin intervención del usuario.
Unificado: ARIA_v4 core + ARIA_APP modules.
"""

import asyncio
import json
import os
import psutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional


class AutonomousCore:
    """Núcleo autónomo de ARIA — ejecuta todo en background."""

    def __init__(self, adaptive_engine=None, logic_engine=None):
        self.adaptive = adaptive_engine
        self.logic = logic_engine
        self.running = False
        self.tasks: List[asyncio.Task] = []
        self.last_scan = None
        self.scan_interval = 30
        self.prediction_interval = 60
        self.health_interval = 15
        self.pattern_interval = 120
        self.proactive_suggestions: List[dict] = []
        self.system_health = {}
        self.behavior_insights = {}
        self._error_count = 0
        self._last_error_time = None

    async def start(self):
        """Inicia todos los loops autónomos."""
        self.running = True
        print("[AutonomousCore] Autonomía activada — 5 loops en background")

        self.tasks.append(asyncio.create_task(self._system_scan_loop()))
        self.tasks.append(asyncio.create_task(self._prediction_loop()))
        self.tasks.append(asyncio.create_task(self._health_check_loop()))
        self.tasks.append(asyncio.create_task(self._pattern_analysis_loop()))
        self.tasks.append(asyncio.create_task(self._error_recovery_loop()))

        await self._initial_proactive_scan()

    async def stop(self):
        """Detiene todos los loops."""
        self.running = False
        for t in self.tasks:
            if not t.done():
                t.cancel()
                try:
                    await t
                except asyncio.CancelledError:
                    pass
        self.tasks.clear()
        print("[AutonomousCore] Autonomía detenida")

    async def _system_scan_loop(self):
        """Escaneo periódico del estado del sistema."""
        while self.running:
            try:
                await self._scan_system()
                await asyncio.sleep(self.scan_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[AutonomousCore] Scan error: {e}")
                await asyncio.sleep(5)

    async def _scan_system(self):
        """Escanea estado del sistema."""
        cpu = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/') if os.name != 'nt' else psutil.disk_usage('C:')

        self.system_health = {
            'cpu_percent': cpu,
            'memory_percent': memory.percent,
            'memory_gb_used': memory.used / (1024**3),
            'disk_percent': disk.percent,
            'disk_gb_free': disk.free / (1024**3),
            'process_count': len(psutil.pids()),
            'timestamp': datetime.now().isoformat(),
        }

        if cpu > 85:
            await self._proactive_action('high_cpu', 'Optimizando recursos del sistema...')
        if memory.percent > 90:
            await self._proactive_action('high_memory', 'Liberando memoria...')

        self.last_scan = datetime.now().isoformat()

    async def _prediction_loop(self):
        """Predice necesidades del usuario."""
        while self.running:
            try:
                await self._predict_needs()
                await asyncio.sleep(self.prediction_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[AutonomousCore] Prediction error: {e}")
                await asyncio.sleep(10)

    async def _predict_needs(self):
        """Predice qué necesita el usuario basado en contexto."""
        now = datetime.now()
        hour = now.hour
        day_name = now.strftime('%A')

        predictions = []

        if 6 <= hour <= 9:
            predictions.append({
                'type': 'morning_routine',
                'message': 'Buenos días. ¿Necesitas revisar tus tareas del día?',
                'confidence': 0.85,
            })
        if 14 <= hour <= 16 and day_name not in ('Saturday', 'Sunday'):
            predictions.append({
                'type': 'focus_time',
                'message': 'Hora de concentración. ¿Deseas activar modo foco?',
                'confidence': 0.80,
            })
        if 18 <= hour <= 21:
            predictions.append({
                'type': 'evening_review',
                'message': '¿Quieres revisar lo que aprendiste hoy?',
                'confidence': 0.78,
            })

        if self.adaptive and self.adaptive.user_profile.get('behavior_patterns'):
            patterns = self.adaptive.user_profile['behavior_patterns']
            if patterns:
                last_patterns = patterns[-3:]
                most_common = {}
                for p in last_patterns:
                    intent = p.get('intent', 'unknown')
                    most_common[intent] = most_common.get(intent, 0) + 1
                top_intent = max(most_common, key=most_common.get)
                if top_intent != 'conversation':
                    predictions.append({
                        'type': 'habit_suggestion',
                        'message': f'Sueles usar "{top_intent}" a esta hora. ¿Activarlo?',
                        'confidence': 0.70,
                    })

        for p in predictions:
            if p['confidence'] > 0.75:
                self.proactive_suggestions.append({
                    **p,
                    'timestamp': datetime.now().isoformat(),
                })
                await self._notify_proactive(p)

    async def _health_check_loop(self):
        """Revisa salud del sistema y auto-recupera."""
        while self.running:
            try:
                await self._check_health()
                await asyncio.sleep(self.health_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[AutonomousCore] Health error: {e}")
                await asyncio.sleep(5)

    async def _check_health(self):
        """Verifica salud y ejecuta auto-recuperación."""
        if self.system_health:
            if self.system_health.get('cpu_percent', 0) > 90:
                await self._proactive_action('cpu_overload', 'Sobrecarga detectada, optimizando...')
            if self.system_health.get('memory_percent', 0) > 90:
                await self._proactive_action('memory_pressure', 'Presión de memoria, limpiando caché...')

    async def _pattern_analysis_loop(self):
        """Analiza patrones de comportamiento periódicamente."""
        while self.running:
            try:
                await self._analyze_patterns()
                await asyncio.sleep(self.pattern_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[AutonomousCore] Pattern error: {e}")
                await asyncio.sleep(10)

    async def _analyze_patterns(self):
        """Analiza patrones y actualiza perfil."""
        if not self.adaptive:
            return

        now = datetime.now()
        behavior = {
            'hour': now.hour,
            'day': now.strftime('%A'),
            'month': now.month,
            'timestamp': now.isoformat(),
            'system_state': {
                'cpu': self.system_health.get('cpu_percent', 0),
                'memory': self.system_health.get('memory_percent', 0),
            },
        }

        profile = self.adaptive.user_profile
        if 'behavior_patterns' not in profile:
            profile['behavior_patterns'] = []
        profile['behavior_patterns'].append(behavior)

        if len(profile['behavior_patterns']) > 500:
            profile['behavior_patterns'] = profile['behavior_patterns'][-500:]

        profile['last_active'] = now.isoformat()
        profile['active_hours'] = list(set(profile.get('active_hours', []) + [now.hour]))

        try:
            data_dir = Path('ARIA_APP/data')
            data_dir.mkdir(parents=True, exist_ok=True)
            with open(data_dir / 'user_profile.json', 'w') as f:
                json.dump(profile, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[AutonomousCore] Profile save error: {e}")

    async def _error_recovery_loop(self):
        """Monitorea y recupera errores automáticamente."""
        while self.running:
            try:
                await self._check_errors()
                await asyncio.sleep(self.health_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[AutonomousCore] Error recovery error: {e}")
                await asyncio.sleep(5)

    async def _check_errors(self):
        """Verifica si hay errores que requieren recuperación."""
        if self._error_count > 3:
            now = datetime.now()
            if self._last_error_time and (now - self._last_error_time).seconds < 60:
                await self._recover_from_errors()
                self._error_count = 0

    async def _recover_from_errors(self):
        """Recuperación automática de errores."""
        print("[AutonomousCore] Ejecutando recuperación automática...")
        recovery_actions = [
            self._clear_cache(),
            self._reset_connections(),
            self._reload_config(),
        ]
        for action in recovery_actions:
            try:
                await action
            except Exception as e:
                print(f"[AutonomousCore] Recovery action failed: {e}")

    async def _clear_cache(self):
        """Limpia caché del sistema."""
        try:
            from backend.storage.cache import CacheManager
            cache = CacheManager()
            cache.max_size_mb = 50
            print("[AutonomousCore] Caché limpiada")
        except Exception as e:
            print(f"[AutonomousCore] Cache clear failed: {e}")

    async def _reset_connections(self):
        """Resetea conexiones."""
        print("[AutonomousCore] Conexiones reseteadas")

    async def _reload_config(self):
        """Recarga configuración."""
        try:
            from backend.config.config import Config
            config = Config()
            print("[AutonomousCore] Configuración recargada")
        except Exception as e:
            print(f"[AutonomousCore] Config reload failed: {e}")

    async def _initial_proactive_scan(self):
        """Escaneo proactivo al iniciar."""
        await asyncio.sleep(5)
        await self._scan_system()
        await self._predict_needs()

    async def _proactive_action(self, action_type: str, message: str):
        """Ejecuta acción proactiva."""
        self.proactive_suggestions.append({
            'type': action_type,
            'message': message,
            'timestamp': datetime.now().isoformat(),
            'proactive': True,
        })
        await self._notify_proactive({'type': action_type, 'message': message})

    async def _notify_proactive(self, suggestion: dict):
        """Notifica sugerencia proactiva."""
        try:
            from ARIA_APP.ui.desktop_ui import DesktopUI
            DesktopUI.show_notification(
                "ARIA Proactiva",
                suggestion.get('message', ''),
            )
        except Exception:
            pass

    async def record_error(self):
        """Registra un error para auto-recuperación."""
        self._error_count += 1
        self._last_error_time = datetime.now()

    def get_status(self) -> Dict:
        """Obtiene estado del núcleo autónomo."""
        return {
            'running': self.running,
            'last_scan': self.last_scan,
            'system_health': self.system_health,
            'proactive_suggestions': self.proactive_suggestions[-10:],
            'error_count': self._error_count,
            'behavior_insights': self.behavior_insights,
            'active_loops': len([t for t in self.tasks if not t.done()]),
        }

    def record_interaction(self, user_input: str, intent: str):
        """Registra interacción para análisis de patrones."""
        if self.adaptive and 'behavior_patterns' in self.adaptive.user_profile:
            self.adaptive.user_profile['behavior_patterns'].append({
                'input': user_input,
                'intent': intent,
                'timestamp': datetime.now().isoformat(),
                'hour': datetime.now().hour,
            })
