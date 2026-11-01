from backend.brain_orchestrator import brain
from backend.bot_api import handle_bot_command

# monkey patch think to intercept early
orig_think = brain.think
def bot_think(prompt='', *a, **kw):
    try:
        p = str(prompt or '')
        if p.strip().lower().startswith('bot:'):
            cmd = p[4:].strip()
            cl = cmd.lower()
            if cl == 'list':
                lst = handle_bot_command('list')
                return {'message': str(lst), 'provider': 'unified_brain', 'source': 'bot_cmd', 'confidence': 0.95, 'autonomous': True, 'should_retrain': False}
            if cl.startswith('create'):
                name = 'grook'
                if 'name=' in cmd:
                    name = cmd.split('name=')[-1].strip().split()[0]
                r = handle_bot_command('create', name=name)
                return {'message': 'BOT created: ' + str(r.get('bot_id')), 'provider': 'unified_brain', 'source': 'bot_cmd', 'confidence': 0.95, 'autonomous': True, 'should_retrain': False}
    except Exception as e:
        pass
    return orig_think(prompt=prompt, *a, **kw)
brain.think = bot_think
