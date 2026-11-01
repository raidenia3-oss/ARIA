from backend.brain_orchestrator import brain
from backend.bot_api import handle_bot_command

orig = brain.think
def think2(prompt='', **kw):
    p = str(prompt or '')
    if p.strip().lower().startswith('bot:'):
        try:
            parts = p[4:].strip()
            if parts.lower() == 'list':
                return {'message': str(handle_bot_command('list')), 'provider': 'unified_brain', 'source': 'bot_cmd', 'confidence': 0.95}
            if parts.lower().startswith('create'):
                name = parts.split('name=')[-1].strip() if 'name=' in parts else 'grook'
                r = handle_bot_command('create', name=name)
                return {'message': 'BOT created: ' + str(r.get('bot_id')), 'provider': 'unified_brain', 'source': 'bot_cmd', 'confidence': 0.95}
        except Exception as e:
            return {'message': 'BOT ERR: ' + str(e), 'provider': 'unified_brain', 'source': 'bot_cmd', 'confidence': 0.9}
    return orig(prompt=p, **kw)
brain.think = think2
print('wired')
