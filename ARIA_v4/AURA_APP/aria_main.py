"""ARIA Main — Entry point"""
import asyncio, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from AURA_APP.backend.logic.aria_logic_engine import LogicEngine
from AURA_APP.ui.desktop_ui import DesktopUI

async def main():
    print("ARIA OS v4.0 — Asistente Virtual Inteligente")
    engine = LogicEngine()
    await engine.start()
    ui = DesktopUI(engine)
    ui.run()
    await engine.stop()

if __name__ == '__main__':
    asyncio.run(main())
