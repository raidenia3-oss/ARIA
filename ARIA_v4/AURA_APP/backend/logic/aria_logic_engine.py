"""ARIA Logic Engine — Motor principal autónomo.

Integra: lógica, autonomía, recuperación y aprendizaje continuo.
No depende de comandos — ejecuta en background automáticamente.
"""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


class LogicEngine:
    """Motor lógico principal de ARIA — autónomo."""

    def __init__(self):
        self.running = True
        self.adaptive_engine = None
        self.intent_detector = None
        self.memory = None
        self.last_command = None
        self.pstack = None
        self.autonomous = None
        self.self_healer = None
        self.context_predictor = None
        self._loop = None

    async def start(self):
        """Inicia engine + autonomía."""
        print("[LogicEngine] Iniciando...")

        from AURA_APP.backend.logic.aria_adaptive_engine import AriaAdaptiveEngine
        from AURA_APP.backend.logic.intent_detector import IntentDetector
        from AURA_APP.backend.learning.memory_manager import MemoryManager
        from AURA_APP.backend.logic.pstack_orchestrator import PStackOrchestrator

        self.adaptive_engine = AriaAdaptiveEngine()
        self.intent_detector = IntentDetector()
        self.memory = MemoryManager()
        self.pstack = PStackOrchestrator()

        await self.memory.load()

        if self.autonomous:
            print("[LogicEngine] Autonomía ya activa")

        print("[LogicEngine] Listo")

    async def process_input(self, user_input: str, context: dict = None) -> dict:
        """Procesa input del usuario + auto-aprende."""
        self.last_command = user_input

        if not self.adaptive_engine:
            return {'status': 'no_engine', 'error': 'Adaptive engine not started'}

        intent = await self.adaptive_engine.identify_intent(user_input)

        if self.pstack:
            try:
                await self.pstack.potato_mode(user_input)
            except Exception:
                pass

        result = {
            'status': 'success',
            'intent': intent,
            'input': user_input,
            'timestamp': datetime.now().isoformat(),
        }

        if self.memory:
            await self.memory.learn(user_input, result)

        if self.adaptive_engine:
            await self.adaptive_engine.auto_learn(user_input, result)
            await self.adaptive_engine.auto_adapt_to_user()

        return result

    async def get_proactive_status(self) -> dict:
        """Obtiene estado proactivo completo."""
        status = {
            'adaptive_mode': self.adaptive_engine.adaptive_state.get('mode') if self.adaptive_engine else 'idle',
            'auto_active': self.adaptive_engine.adaptive_state.get('auto_active', False) if self.adaptive_engine else False,
            'proactive_mode': self.adaptive_engine.adaptive_state.get('proactive_mode', False) if self.adaptive_engine else False,
            'total_interactions': self.adaptive_engine.user_profile.get('total_interactions', 0) if self.adaptive_engine else 0,
            'learning_entries': len(self.adaptive_engine.learning_history) if self.adaptive_engine else 0,
        }

        if self.autonomous:
            status['autonomous'] = self.autonomous.get_status()

        if self.self_healer:
            status['self_healer'] = self.self_healer.get_status()

        if self.context_predictor:
            status['predictions'] = self.context_predictor.get_top_predictions(3)

        return status

    async def proactive_action(self, action_type: str, message: str):
        """Ejecuta acción proactiva."""
        print(f"[LogicEngine] Proactivo: {message}")
        if self.adaptive_engine:
            await self.adaptive_engine.auto_learn(f"proactive_{action_type}", {'message': message})

    async def stop(self):
        """Detiene engine gracefully."""
        self.running = False
        if self.memory:
            await self.memory.save()
        if self.adaptive_engine:
            try:
                await self.adaptive_engine.auto_adapt_to_user()
            except Exception:
                pass
        print("[LogicEngine] Detenido")


if __name__ == '__main__':
    engine = LogicEngine()
    asyncio.run(engine.start())
