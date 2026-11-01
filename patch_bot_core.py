from backend.brain_orchestrator import brain
from backend.bot_api import handle_bot_command

orig = brain.think
def think3(prompt='', history=None, tasks=None, parallel=False, **kwargs):
    p = str(prompt or '')
    if p.strip().lower().startswith('bot:'):
        cmd = p[4:].strip()
        cl = cmd.lower()
        if cl == 'list':
            res = handle_bot_command('list')
            return {'message': str(res), 'provider': 'unified_brain', 'source': 'bot_cmd', 'confidence': 0.95, 'autonomous': True, 'should_retrain': False}
        if cl.startswith('create'):
            name = 'grook'
            if 'name=' in cmd:
                try:
                    name = cmd.split('name=')[-1].strip().split()[0]
                except Exception:
                    name = 'grook'
            r = handle_bot_command('create', name=name)
            return {'message': 'BOT created: ' + str(r.get('bot_id')), 'provider': 'unified_brain', 'source': 'bot_cmd', 'confidence': 0.95, 'autonomous': True, 'should_retrain': False}
    return orig(prompt=prompt, history=history, tasks=tasks, parallel=parallel, **kwargs)
brain.think = think3
