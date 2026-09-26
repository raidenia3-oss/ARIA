import json, urllib.request, urllib.error

BASE = "http://localhost:8000"

def post(path, data, timeout=120):
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=json.dumps(data).encode() if data else b'{}',
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, {"error": e.read().decode()}
    except Exception as e:
        return 0, {"error": str(e)}

def get(path, timeout=30):
    try:
        with urllib.request.urlopen(f"{BASE}{path}", timeout=timeout) as r:
            return r.status, json.loads(r.read().decode())
    except Exception as e:
        return 0, {"error": str(e)}

results = []

tests = [
    ("GET", "/health", None),
    ("GET", "/api/aria/health", None),
    ("GET", "/api/ai/status", None),
    ("GET", "/api/aria/profile", None),
    ("GET", "/api/aria/dataset/validate", None),
    ("GET", "/api/aria/content/library", None),
    ("GET", "/api/system/status", None),
    ("GET", "/api/skills", None),
    ("GET", "/api/aria/widget.html", None),
    ("GET", "/aria_core.js", None),
    ("POST", "/api/aria/chat", {"message": "hola"}),
    ("POST", "/api/chat", {"message": "hola"}),
    ("POST", "/api/aria/test/run", {}),
    ("POST", "/api/aria/content/suggest", {"current_app": "browser", "activity": "searching"}),
    ("POST", "/api/aria/generate/character", {"role": "villain", "traits": ["evil", "charismatic"]}),
    ("POST", "/api/aria/generate/world", {"theme": "sci-fi", "size": "large"}),
    ("POST", "/api/aria/generate/story", {"prompt": "space adventure", "length": "short"}),
    ("POST", "/api/aria/generate/prompt", {"description": "cyberpunk city", "style": "anime"}),
    ("POST", "/api/aria/dataset/create", {}),
    ("POST", "/api/aria/content/interactive", {"scene": "test", "story_id": "final", "branches": 3}),
    ("POST", "/api/aria/learn", {"user_input": "testing final", "feedback": "más"}),
    ("POST", "/api/aria/learn", {"user_input": "final test", "feedback": "técnico"}),
]

for method, path, data in tests:
    if method == "GET":
        status, result = get(path)
    else:
        status, result = post(path, data)
    ok = "OK" if status == 200 and "error" not in result else "FAIL"
    results.append((path, ok, status))
    print(f"[{ok}] {path} (status={status})")

print(f"\n=== SUMMARY ===")
passed = sum(1 for _, s, _ in results if s == "OK")
total = len(results)
print(f"{passed}/{total} tests passed")

if passed == total:
    print("ALL TESTS PASSED ✅")
else:
    print(f"FAILED: {[r[0] for r in results if r[1] == 'FAIL']}")
