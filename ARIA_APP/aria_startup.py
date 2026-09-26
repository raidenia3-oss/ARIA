"""ARIA Auto-Startup — UNIFIED.

Fusiona: ARIA_v4 autonomous startup + original features.
No input() — fully autonomous operation.
La única activación es por voz (wake word) o auto-inicio en Windows.
"""

import asyncio
import sys
import json
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from ARIA_APP.backend.logic.aria_logic_engine import LogicEngine
from ARIA_APP.backend.logic.aria_adaptive_engine import AriaAdaptiveEngine


class AriaAutoStartup:
    """Arranque autónomo — sin comandos manuales."""

    def __init__(self):
        self.engine = None
        self.adaptive = None
        self.autonomous = None
        self.voice = None
        self.healer = None
        self.predictor = None
        self.scheduler = None

    async def startup(self):
        print("""
        ╔════════════════════════════════════════════════════════════╗
        ║                    ARIA OS v4.0                            ║
        ║           Asistente Virtual Inteligente                     ║
        ║                                                            ║
        ║  Activándose automáticamente...                            ║
        ╚════════════════════════════════════════════════════════════╝
        """)

        await self._init_data_dir()

        print("▶ Iniciando motor lógico...")
        self.engine = LogicEngine()
        await self.engine.start()

        print("▶ Iniciando motor adaptativo con autonomía...")
        self.adaptive = AriaAdaptiveEngine()
        self.engine.adaptive_engine = self.adaptive

        print("▶ Iniciando aprendizaje compuesto...")
        from ARIA_APP.backend.learning.compound import CompoundLearning
        self.compound = CompoundLearning()

        print("▶ Activando núcleo autónomo...")
        from ARIA_APP.backend.autonomy.autonomous_core import AutonomousCore
        self.autonomous = AutonomousCore(adaptive_engine=self.adaptive, logic_engine=self.engine)
        await self.autonomous.start()
        self.engine.autonomous = self.autonomous

        print("▶ Activando escucha por voz...")
        from ARIA_APP.backend.autonomy.voice_activation import VoiceActivation
        self.voice = VoiceActivation(on_activate=self._on_voice_wake)
        await self.voice.start()

        print("▶ Iniciando auto-recuperación...")
        from ARIA_APP.backend.autonomy.self_healer import SelfHealer
        self.healer = SelfHealer()
        self.engine.self_healer = self.healer

        print("▶ Iniciando predicción contextual...")
        from ARIA_APP.backend.autonomy.context_predictor import ContextPredictor
        self.predictor = ContextPredictor(adaptive_engine=self.adaptive)
        self.engine.context_predictor = self.predictor

        print("▶ Iniciando programación proactiva...")
        from ARIA_APP.backend.autonomy.proactive_scheduler import ProactiveScheduler
        self.scheduler = ProactiveScheduler(adaptive_engine=self.adaptive)
        self.scheduler.generate_tasks()

        await self._check_usb_expansion()

        user = self.adaptive.user_profile['name']
        print(f"   ✅ Bienvenido, {user}")

        await self._show_initial_status()

        print("\n💡 ARIA activada — escuchando y observando...")

        await self._main_loop()

    async def _init_data_dir(self):
        data_dir = Path('ARIA_APP/data')
        data_dir.mkdir(parents=True, exist_ok=True)

        profile_path = data_dir / 'user_profile.json'
        if not profile_path.exists():
            profile = {
                'name': 'Usuario',
                'language': 'es',
                'timezone': 'America/Lima',
                'preferences': {'auto_adapt': True, 'proactive_suggestions': True},
                'behavior_patterns': [],
                'favorite_commands': [],
                'learning_style': 'visual',
                'created': datetime.now().isoformat(),
                'last_active': None,
                'active_hours': [],
                'total_interactions': 0,
            }
            with open(profile_path, 'w') as f:
                json.dump(profile, f, indent=2, ensure_ascii=False)

    async def _on_voice_wake(self):
        """Maneja activación por wake word."""
        print("\n[ARIA] Despertado por voz")
        if self.adaptive and self.adaptive.adaptive_state['mode'] != 'active':
            result = await self.adaptive._activate()
            print(f"[ARIA] {result['message']}")
            await self.adaptive.auto_adapt_to_user()

    async def _check_usb_expansion(self):
        try:
            from ARIA_APP.backend.usb_intelligence import USBIntelligence
            usb = USBIntelligence()
            usb_status = await usb.get_usb_status()
            if usb_status['usb_count'] > 0:
                print(f"   ✅ Detectados {usb_status['usb_count']} USB")
                expansion = await usb.expand_aria_with_usb()
                await usb.register_usb_learning()
                count = sum(len(v) if isinstance(v, list) else 0 for v in expansion.values())
                print(f"   ✅ Expandida con {count} elementos")
        except Exception as e:
            print(f"   ⚠ USB check: {e}")

    async def _show_initial_status(self):
        print("\n   ┌── Estado Autónomo ──")
        print("   │ Sistemas: activos")
        print("   │ Escucha voz: activa")
        print("   │ Auto-aprendizaje: ON")
        print("   │ Escaneo proactivo: ON")
        print("   │ Auto-recuperación: ON")
        print("   └─────────────────────")

    async def _main_loop(self):
        """Loop principal — autónomo, sin input()."""
        try:
            while True:
                await asyncio.sleep(5)

                if self.autonomous and self.autonomous.running:
                    await self.adaptive.auto_detect_patterns()
                    await self.adaptive.auto_learn("scan_autonomous", {})

        except KeyboardInterrupt:
            await self.shutdown()

    async def shutdown(self):
        print("\n\n▶ ARIA se apaga gracefulmente...")
        if self.autonomous:
            await self.autonomous.stop()
        if self.voice:
            await self.voice.stop()
        if self.engine:
            await self.engine.stop()
        print("▶ ARIA apagado.")


if __name__ == '__main__':
    startup = AriaAutoStartup()
    asyncio.run(startup.startup())
