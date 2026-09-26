"""Learning Route"""

from typing import Dict


async def learn_route(user_input: str) -> Dict:
    from AURA_APP.backend.logic.aria_adaptive_engine import AriaAdaptiveEngine

    engine = AriaAdaptiveEngine()
    intent = await engine.identify_intent(user_input)
    result = await engine.execute_intelligently(intent, user_input)

    return {
        'status': 'learned',
        'intent': intent,
        'result': result,
    }
