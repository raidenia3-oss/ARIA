"""Verify System — Tests completos"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


class SystemVerification:
    """Verifica que todo funcione"""

    async def run_all_tests(self):
        tests = [
            ("Import aria_brain", self.test_ariabrain_import),
            ("Intent detection", self.test_intent_detection),
            ("USB detection", self.test_usb_detection),
            ("Open source repos", self.test_open_source),
            ("PStack orchestration", self.test_pstack),
            ("API endpoints", self.test_api),
            ("Memory manager", self.test_memory),
            ("Config", self.test_config),
        ]

        passed = 0
        failed = 0

        print("=" * 60)
        print("ARIA v4.0 SYSTEM VERIFICATION")
        print("=" * 60)

        for test_name, test_func in tests:
            try:
                await test_func()
                print(f"✅ {test_name}")
                passed += 1
            except Exception as e:
                print(f"❌ {test_name}: {e}")
                failed += 1

        print("\n" + "=" * 60)
        print(f"RESULTS: {passed} passed, {failed} failed")
        print("=" * 60)
        return passed, failed

    async def test_ariabrain_import(self):
        from AURA_APP.backend.intelligence.aria_brain import AriaBrain
        brain = AriaBrain()
        assert brain is not None

    async def test_intent_detection(self):
        from AURA_APP.backend.logic.intent_detector import IntentDetector
        detector = IntentDetector()
        intent = asyncio.run(detector.detect("Prendete"))
        assert intent['intent'] == 'activate'

    async def test_usb_detection(self):
        from AURA_APP.backend.expansion.usb_intelligence import USBIntelligence
        usb = USBIntelligence()
        status = await usb.get_usb_status()
        assert 'usb_count' in status

    async def test_open_source(self):
        from AURA_APP.backend.integration.headroom_optimizer import HeadroomOptimizer
        from AURA_APP.backend.integration.claude_context_bridge import ClaudeContextBridge
        head = HeadroomOptimizer()
        assert head is not None
        ctx = ClaudeContextBridge()
        assert ctx is not None

    async def test_pstack(self):
        from AURA_APP.backend.logic.pstack_orchestrator import PStackOrchestrator
        pstack = PStackOrchestrator()
        mode = await pstack.potato_mode("Necesito expandir")
        assert mode['detected_workflow'] == 'usb_expansion'

    async def test_api(self):
        from AURA_APP.backend.api.routes.chat import chat_route
        from AURA_APP.backend.api.routes.system import health_route
        assert chat_route is not None
        assert health_route is not None

    async def test_memory(self):
        from AURA_APP.backend.learning.memory_manager import MemoryManager
        mem = MemoryManager()
        await mem.remember("test")
        results = await mem.recall("test")
        assert len(results) >= 1

    async def test_config(self):
        from AURA_APP.backend.config.config import Config
        cfg = Config()
        assert cfg.get('app.name') == 'ARIA OS'


if __name__ == '__main__':
    verifier = SystemVerification()
    asyncio.run(verifier.run_all_tests())
