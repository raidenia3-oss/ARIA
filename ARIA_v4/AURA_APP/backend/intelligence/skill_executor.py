"""Skill Executor — Ejecuta skills y herramientas"""

from typing import Dict, Any, List


class SkillExecutor:
    """Ejecuta skills del sistema"""

    def __init__(self):
        self.skills = {}
        self.tools = {}
        self.execution_log = []

    async def register_skill(self, name: str, handler: Any) -> None:
        self.skills[name] = handler

    async def execute(self, intent: Dict, user_input: str, context: Dict = None) -> Dict:
        """Ejecuta skill basado en intención"""
        intent_name = intent.get('intent', 'unknown')

        if intent_name in self.skills:
            handler = self.skills[intent_name]
            result = await handler(user_input, context) if callable(handler) else {'status': 'ok'}
        else:
            result = {'status': 'no_skill', 'intent': intent_name}

        self.execution_log.append({
            'intent': intent_name,
            'result': result,
        })

        return {
            'intent': intent_name,
            'result': result,
            'executed': True,
        }

    def list_skills(self) -> List[str]:
        return list(self.skills.keys())
