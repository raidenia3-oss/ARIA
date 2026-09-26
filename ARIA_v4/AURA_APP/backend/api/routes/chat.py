"""Chat Route"""

from typing import Dict


async def chat_route(message: str, session_id: str = None) -> Dict:
    from AURA_APP.backend.logic.aria_logic_engine import LogicEngine

    engine = LogicEngine()
    await engine.start()
    result = await engine.process_input(message)
    await engine.stop()

    return {
        'response': result.get('intent', 'unknown'),
        'session_id': session_id or 'default',
        'status': 'ok',
    }
