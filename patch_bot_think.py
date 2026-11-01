from backend.brain_orchestrator import brain
from backend.bot_api import handle_bot_command

orig = brain.think
def think2(prompt='', history=None, tasks=None, parallel=False, **kwargs):
    p = str(prompt or '')
    lp = p.strip().lower()
    if lp.startswith('bot:'):
        parts = p[4:].strip().lower()
        if parts == 'list':
            lst = handle_bot_command('list')
            return {'message': str(lst), 'provider': 'unified_brain', 'source': 'bot_cmd', 'confidence': 0.95, 'autonomous': True}
        if parts.startswith('create'):
            name = 'grook'
            if 'name=' in p:
                name = p.split('name=')[-1].strip().split()[0]
            r = handle_bot_command('create', name=name)
            return {'message': 'BOT created: ' + str(r.get('bot_id')), 'provider': 'unified_brain', 'source': 'bot_cmd', 'confidence': 0.95, 'autonomous': True}
    return orig(prompt=prompt, history=history, tasks=tasks, parallel=parallel, **kwargs)
brain.think = think2
