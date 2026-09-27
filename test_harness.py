import json
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:8000/api/agents/harness"

def test(name, method, path, body=None):
    url = f"{BASE}{path}"
    data = json.dumps(body).encode("utf-8") if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
            print(f"=== {name} ===")
            print(json.dumps(result, indent=2, ensure_ascii=False))
            print()
            return result
    except urllib.error.HTTPError as e:
        print(f"=== {name} === FAILED")
        print(f"HTTP {e.code}: {e.read().decode()}")
        print()
        return None

# Test 1: Register skill
test("Test 1: Register skill", "POST", "/skills/register",
     {"name": "code_analyzer", "description": "Analyzes code quality", "actions": ["run", "status", "reset"]})

# Test 2: List skills
test("Test 2: List skills", "GET", "/skills")

# Test 3: Set custom prompt
test("Test 3: Set custom prompt", "POST", "/prompts/self-improvement",
     {"prompt": "Eres un agente de mejora automatica"})

# Test 4: Get agent config
test("Test 4: Get agent config", "GET", "/config/self-improvement")

# Test 5: Register MCP
test("Test 5: Register MCP", "POST", "/mcp/register",
     {"name": "filesystem", "url": "mcp://fs"})

# Test 6: List MCP servers
test("Test 6: List MCP servers", "GET", "/mcp/list")