from backend.brain_orchestrator import brain
from backend.bot_api import handle_bot_command

orig = brain.think
def think2(prompt='', history=None, tasks=None, parallel=False, **kwargs):
    p = str(prompt or '')
    if p.strip().lower().startswith('bot:'):
        try:
            cmd = p[4:].strip()
            cl = cmd.lower()
            if cl == 'list':
                lst = handle_bot_command('list')
                return {'message': str(lst), 'provider': 'unified_brain', 'source': 'bot_cmd', 'confidence': 0.95, 'autonomous': True, 'should_retrain': False}
            if cl.startswith('create'):
                name = 'grook'
                if 'name=' in cmd:
                    try:
                        name = cmd.split('name=')[-1].strip().split()[0]
                    except:
                        name = 'grook'
                r = handle_bot_command('create', name=name)
                return {'message': 'BOT created: ' + str(r.get('bot_id')), 'provider': 'unified_brain', 'source': 'bot_cmd', 'confidence': 0.95, 'autonomous': True, 'should_retrain': False}
            if cl.startswith('start'):
                bid = None
                if 'bot_id=' in cmd:
                    bid = cmd.split('bot_id=')[-1].strip().split()[0]
                r = handle_bot_command('start', bot_id=bid)
                return {'message': str(r), 'provider': 'unified_brain', 'source': 'bot_cmd', 'confidence': 0.95, 'autonomous': True, 'should_retrain': False}
        except Exception as e:
            return {'message': 'BOT ERR: ' + str(e), 'provider': 'unified_brain', 'source': 'bot_cmd', 'confidence': 0.9, 'autonomous': True, 'should_retrain': False}
    return orig(prompt=prompt, history=history, tasks=tasks, parallel=parallel, **kwargs)
brain.think = think2
print('ok')
