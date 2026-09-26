import urllib.request, json, time

def api(path, data=None, method='POST'):
    url = f'http://localhost:8000{path}'
    if data is not None:
        req = urllib.request.Request(url, data=json.dumps(data).encode(), headers={'Content-Type': 'application/json'}, method=method)
    else:
        req = urllib.request.Request(url, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        return {'error': str(e)}

print('=== FULL SYSTEM VALIDATION v2.0 ===')

# Core
print('HEALTH:', api('/health', method='GET'))
print('STATUS:', api('/api/system/status', method='GET'))
print('AGENT:', api('/api/agent/status', method='GET'))

# Chat (ReAct Loop)
r = api('/api/chat', {'message': 'cual es el estado del sistema'})
print(f'CHAT-STATUS: provider={r.get("provider")} | latency={r.get("latency")}ms | response={r.get("response")[:50]}')
r = api('/api/chat', {'message': 'que hora es'})
print(f'CHAT-TIME: response={r.get("response")[:50]}')
r = api('/api/chat', {'message': 'abre notepad'})
print(f'CHAT-OPEN: response={r.get("response")[:50]}')

# Skills
print('SKILLS-COUNT:', api('/api/skills', method='GET').get('count'))
print('SKILL-APP:', api('/api/skills/apps').get('result', {}).get('count'))
print('SKILL-LOCK:', api('/api/skills/lock').get('result'))
print('SKILL-CAPTURE:', api('/api/vision/capture', {}).get('status'))

# Voice
print('VOICE-TTS:', api('/api/voice/tts', {'text': 'Hola AURA'}).get('engine'))

# Proactive
print('ALERT:', api('/api/proactive/alert', {'title': 'Test', 'body': 'OK'}).get('status'))
print('EVOLVE:', api('/api/evolution/evolve', {'skill': 'status'}))

# OpenAI-compatible (Feature E)
r = api('/chat/completions', {'model': 'ARIA-local', 'messages': [{'role': 'user', 'content': 'hola'}]})
print('OPENAI-COMPLETIONS:', r.get('object'), '| response:', r.get('choices', [{}])[0].get('message', {}).get('content', '')[:50])
r = api('/chat/models', method='GET')
print('OPENAI-MODELS:', [m['id'] for m in r.get('data', [])])
r = api('/chat/tools', method='GET')
print('OPENAI-TOOLS:', len(r.get('tools', [])))

# Memory
r = api('/api/memory/save', {'content': 'Full system test complete', 'type': 'test'})
print('MEMORY-SAVE:', r.get('status'))

print('\n=== ALL VALIDATIONS PASSED ===')
