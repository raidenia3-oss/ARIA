"""Quick targeted test: qwen3.5 text only, then small vision test."""
import json, urllib.request, time, base64, os

OLLAMA = "http://localhost:11434"

def chat(messages, model="qwen3.5:2b", timeout=60):
    body = json.dumps({
        "model": model, "messages": messages, "stream": False,
        "options": {"temperature": 0.1, "num_ctx": 2048, "keep_alive": 0},
    }).encode()
    req = urllib.request.Request(f"{OLLAMA}/api/chat", data=body,
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read()).get("message", {}).get("content", "")

# 1. Text test
print("=== TEXT qwen3.5:2b ===")
t0 = time.time()
r = chat([{"role": "user", "content": "What is 17 * 23? Only the number."}])
print(f"  math: {time.time()-t0:.1f}s -> {r.strip()}")

# 2. JSON test
t0 = time.time()
r = chat([{"role": "user", "content": 'Return ONLY JSON: {"name":"ARIA","version":5}'}])
print(f"  json: {time.time()-t0:.1f}s -> {r.strip()}")

# 3. Small vision test - find smallest image
print("\n=== VISION qwen3.5:2b (small image) ===")
cands = []
for root, dirs, files in os.walk("."):
    for f in files:
        if f.lower().endswith((".png", ".jpg", ".jpeg")):
            p = os.path.join(root, f)
            cands.append((os.path.getsize(p), p))
cands.sort()
if cands:
    size, path = cands[0]
    print(f"  Using: {path} ({size} bytes)")
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    body = json.dumps({
        "model": "qwen3.5:2b", "stream": False,
        "messages": [{"role": "user", "content": "What text or objects do you see? One short sentence.",
                      "images": [b64]}],
        "options": {"temperature": 0.1, "num_ctx": 2048, "keep_alive": 0},
    }).encode()
    req = urllib.request.Request(f"{OLLAMA}/api/chat", data=body,
        headers={"Content-Type": "application/json"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            resp = json.loads(r.read()).get("message", {}).get("content", "")
        print(f"  qwen vision: {time.time()-t0:.1f}s -> {resp[:200]}")
    except Exception as e:
        print(f"  qwen vision FAIL: {e}")

print("\n=== DONE ===")