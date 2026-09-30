import urllib.request, json

tests = [
    ('GET', 'http://127.0.0.1:8002/health', None),
    ('GET', 'http://127.0.0.1:8002/api/system/status', None),
    ('GET', 'http://127.0.0.1:8002/api/system/ping', None),
    ('POST', 'http://127.0.0.1:8002/api/daemon/heartbeat', json.dumps({'agent_id':'test-agent','status':'idle'})),
    ('GET', 'http://127.0.0.1:8002/api/pc/state', None),
    ('POST', 'http://127.0.0.1:8002/api/daemon/task', json.dumps({'agent_id':'test-agent','action':'get_pending'})),
]

for method, url, data in tests:
    try:
        req = urllib.request.Request(url, data=data.encode() if data else None, method=method)
        req.add_header('Content-Type', 'application/json')
        r = urllib.request.urlopen(req, timeout=15)
        body = r.read().decode()[:120]
        endpoint = url.replace('http://127.0.0.1:8002', '')
        print(method, endpoint, '->', r.status, body)
    except Exception as e:
        endpoint = url.replace('http://127.0.0.1:8002', '')
        print(method, endpoint, '-> ERROR', e)