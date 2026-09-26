import urllib.request, json, time

def api(path, data=None, method='POST'):
    url = f'http://localhost:8000{path}'
    if data is not None:
        req = urllib.request.Request(url, data=json.dumps(data).encode(), headers={'Content-Type': 'application/json'}, method='POST')
    else:
        req = urllib.request.Request(url, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        return {'error': str(e)}

print('=== BUGS DEBUG ===')
t0 = time.time()
r = api('/api/chat', {'message': 'que hora es'})
t1 = time.time()
print(f'CHAT-TIME: {t1-t0:.2f}s | provider={r.get("provider")} | latency={r.get("latency")}ms')

t0 = time.time()
r = api('/api/chat', {'message': 'estado del sistema'})
t1 = time.time()
print(f'CHAT-STATUS: {t1-t0:.2f}s | latency={r.get("latency")}ms')

t0 = time.time()
r = api('/api/skills/volume')
t1 = time.time()
print(f'SKILL-VOLUME: {t1-t0:.3f}s | error={r.get("result", {}).get("error", "")}')

t0 = time.time()
r = api('/api/skills/screenshot')
t1 = time.time()
err = r.get('result', {}).get('error', 'none')
print(f'SKILL-SCREENSHOT: {t1-t0:.3f}s | error={err}')
