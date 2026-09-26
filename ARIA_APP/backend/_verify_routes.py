import sys
sys.path.insert(0, '.')
sys.path.insert(0, '..')
from app import app

total = 0
categories = {}
for route in app.routes:
    if hasattr(route, 'path') and hasattr(route, 'methods'):
        total += 1
        path = route.path
        if path.startswith('/api/'):
            parts = path.split('/')
            cat = parts[2] if len(parts) > 2 else 'root'
            categories[cat] = categories.get(cat, 0) + 1

print(f'Total routes: {total}')
for cat in sorted(categories):
    print(f'  /api/{cat}/: {categories[cat]} routes')
print()

checks = {}
for route in app.routes:
    if hasattr(route, 'path'):
        p = route.path
        if '/api/ai/local/inference' in p: checks['AI LLM (Ollama)'] = True
        if '/api/ai/stt/transcribe' in p: checks['AI STT (Whisper)'] = True
        if '/api/ai/tts/synthesize' in p: checks['AI TTS (Piper)'] = True
        if '/api/ai/hardware/info' in p: checks['AI Hardware Info'] = True
        if '/api/memory/vector/rag' in p: checks['Vector RAG'] = True
        if '/api/memory/vector/search' in p: checks['Vector Search'] = True
        if '/api/memory/mcp/' in p: checks['LongMemory MCP'] = True
        if '/api/computer/screenshot' in p: checks['Computer Use - Screenshot'] = True
        if '/api/computer/execute' in p: checks['Computer Use - Execute'] = True
        if '/api/computer/list_windows' in p: checks['Computer Use - List Windows'] = True
        if '/api/computer/accessibility_tree' in p: checks['Computer Use - Accessibility'] = True
        if '/api/github/webhook' in p: checks['GitHub Webhooks'] = True
        if '/api/self-improvement' in p: checks['Self-Improvement API'] = True
        if '/api/skills/run' in p: checks['Skills Registry'] = True

for name, ok in checks.items():
    status = 'OK' if ok else 'MISSING'
    print(f'  {name}: {status}')

print()
print('All checks:', 'PASS' if all(checks.values()) else 'FAIL')
