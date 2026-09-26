import urllib.request, json, concurrent.futures, time

BASE = "http://127.0.0.1:8000"

def test(ep, method="GET", body=None, timeout=15):
    try:
        data = None
        headers = {}
        if body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(BASE + ep, data=data, headers=headers, method=method)
        start = time.time()
        r = urllib.request.urlopen(req, timeout=timeout)
        elapsed = time.time() - start
        body_text = r.read().decode()[:120]
        return f"{r.status} {method} {ep} ({elapsed:.1f}s) | {body_text}"
    except Exception as e:
        return f"ERR {method} {ep}: {str(e)[:70]}"

tests = [
    ("/", "GET"),
    ("/health", "GET"),
    ("/api/system/status", "GET"),
    ("/api/system/health", "GET"),
    ("/api/aria/health", "GET"),
    ("/api/skills", "GET"),
    ("/api/proactive/alerts", "GET"),
    ("/api/aria/chat", "POST", {"message": "hola"}),
    ("/aria_widget.html", "GET"),
    ("/aria_dashboard_v5_extreme.html", "GET"),
    ("/aria_core_extreme.js", "GET"),
    ("/aria_core.js", "GET"),
    ("/api/aria/floating/status", "GET"),
    ("/api/evolution/metrics", "GET"),
    ("/api/memory/recent", "GET"),
    ("/api/skills/search", "GET", None),
]

results = []
for t in tests:
    if len(t) == 3:
        results.append(test(t[0], t[1], t[2]))
    else:
        results.append(test(t[0], t[1]))

for r in results:
    print(r)

# Test with proper query for search
print("\n--- Search test ---")
print(test("/api/skills/search?q=status", "GET"))
