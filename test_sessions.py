import json
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:8000/api/memory/longmemory"

def test(name, method, path, body=None):
    url = f"{BASE}{path}"
    data = json.dumps(body).encode("utf-8") if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
            print(f"=== {name} ===")
            print(json.dumps(result, indent=2, ensure_ascii=False)[:400])
            print()
            return result
    except urllib.error.HTTPError as e:
        print(f"=== {name} === FAILED: HTTP {e.code}: {e.read().decode()[:200]}")
        print()
        return None

# Test 1: Create session
r = test("Test 1: Create session", "POST", "/sessions",
         {"title": "Test Session", "metadata": {"source": "test"}})
sid = r.get("session_id") if r else None

# Test 2: List sessions
test("Test 2: List sessions", "GET", "/sessions")

# Test 3: Add message
if sid:
    test("Test 3: Add user message", "POST", f"/sessions/{sid}/messages",
         {"role": "user", "content": "Hello ARIA"})
    test("Test 3b: Add assistant message", "POST", f"/sessions/{sid}/messages",
         {"role": "assistant", "content": "Hello! How can I help?"})

# Test 4: Get session
if sid:
    test("Test 4: Get session", "GET", f"/sessions/{sid}")

# Test 5: Get messages
if sid:
    test("Test 5: Get messages", "GET", f"/sessions/{sid}/messages")

# Test 6: Session recall
if sid:
    test("Test 6: Session recall", "POST", f"/sessions/{sid}/recall",
         {"query": "ARIA", "top_k": 3})

# Test 7: LongMemory health
test("Test 7: LongMemory health", "GET", "/health")