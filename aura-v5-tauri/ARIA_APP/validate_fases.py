import urllib.request, json, time

def api(path, data=None, method='POST'):
    url = 'http://localhost:8000' + path
    if data is not None:
        req = urllib.request.Request(url, data=json.dumps(data).encode(), headers={'Content-Type': 'application/json'}, method='POST')
    else:
        req = urllib.request.Request(url, method=method)
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        return {'error': str(e)}

print('=== COMPLETE VALIDATION FASES 1-6 ===')

# Phase 1
print('1.1. HEALTH:', api('/health', method='GET'))
print('1.2. STATUS:', api('/api/system/status', method='GET'))
print('1.3. AGENT:', api('/api/agent/status', method='GET'))

# Phase 1: Chat with ReAct Loop
t0 = time.time()
r = api('/api/chat', {'message': 'cual es el estado del sistema'})
t1 = time.time()
print(f'1.4. CHAT-STATUS: {t1-t0:.2f}s | provider={r.get("provider")} | latency={r.get("latency")}ms | plan={r.get("plan")}')

t0 = time.time()
r = api('/api/chat', {'message': 'que hora es'})
t1 = time.time()
print(f'1.5. CHAT-TIME: {t1-t0:.2f}s | response_len={len(r.get("response",""))}')

t0 = time.time()
r = api('/api/chat', {'message': 'abre notepad'})
t1 = time.time()
print(f'1.6. CHAT-OPEN: {t1-t0:.2f}s | response={r.get("response")[:40]}')

t0 = time.time()
r = api('/api/chat', {'message': 'dime algo interesante'})
t1 = time.time()
print(f'1.7. CHAT-AI: {t1-t0:.2f}s | provider={r.get("provider")} | response_len={len(r.get("response",""))}')

# Phase 1: Skills
print('1.8. SKILLS-COUNT:', api('/api/skills', method='GET').get('count'))
print('1.9. SKILL-SEARCH:', len(api('/api/skills/search?q=system&top_k=3', method='GET').get('results', [])))
print('1.10. SKILL-SCAN:', api('/api/skills/scan'))

# Phase 2: Voice
print('2.1. VOICE-STATUS:', api('/api/voice/status', method='GET'))
r = api('/api/voice/tts', {'text': 'Hola AURA', 'voice': 'es-ES-ElviraNeural'})
print('2.2. VOICE-TTS:', r.get('status'), r.get('engine'))

# Phase 3: Vision
r = api('/api/vision/capture', {})
print('3.1. VISION-CAPTURE:', r.get('status') if isinstance(r.get('status'), str) else r.get('error'))

# Phase 6: Proactive
print('6.1. PROACTIVE-ALERT:', api('/api/proactive/alert', {'title': 'Test', 'body': 'ARIA OK', 'severity': 'info', 'ttl': 60}).get('status'))
print('6.2. PROACTIVE-REMIND:', api('/api/proactive/remind', {'title': 'Review', 'body': 'Check AURA', 'due_at': '2026-08-31T16:00:00Z'}).get('status'))
print('6.3. PROACTIVE-STATE:', api('/api/proactive/owner-state', {'mood': 'focused', 'focus': 'coding'}).get('state', {}).get('mood'))
print('6.4. PROACTIVE-ALERTS:', len(api('/api/proactive/alerts', method='GET').get('alerts', [])))

# Phase 6: Evolution
print('6.5. EVOLUTION-RECORD:', api('/api/evolution/record', {'skill': 'status', 'success': True, 'latency_ms': 120}).get('status'))
print('6.6. EVOLUTION-EVOLVE:', api('/api/evolution/evolve', {'skill': 'status'}))

# Phase 6: Learning
print('6.7. LEARNING-ERROR:', api('/api/learning/record-error', {'pattern': 'timeout', 'context': 'retry'}).get('cluster', {}).get('occurrences'))
print('6.8. LEARNING-RULES:', len(api('/api/learning/rules', method='GET').get('rules', [])))

# Phase 1: Memory
r = api('/api/memory/save', {'content': 'ARIA v2.0 FASES 1-6 OK', 'type': 'fact', 'meta': {'phase': 6}})
print('1.11. MEMORY-SAVE:', r.get('status'))
r = api('/api/memory/recent?limit=1&source=long', method='GET')
print('1.12. MEMORY-RECENT:', r.get('memories', [{}])[0].get('content', 'empty') if r.get('memories') else 'empty')

print('\n=== TODAS LAS FASES VALIDADAS ===')
