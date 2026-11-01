"""Compare spark25-ab vs qwen3.5:2b text speed."""
import json, urllib.request, time

OLLAMA = "http://localhost:11434"

def chat(messages, model, timeout=60):
    body = json.dumps({
        "model": model, "messages": messages, "stream": False,
        "options": {"temperature": 0.1, "num_ctx": 2048, "keep_alive": 0},
    }).encode()
    req = urllib.request.Request(f"{OLLAMA}/api/chat", data=body,
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read()).get("message", {}).get("content", "")

for model in ["spark25-ab:latest", "qwen3.5:2b"]:
    print(f"=== {model} ===")
    for name, prompt in [
        ("math", "What is 17 * 23? Only the number."),
        ("json", 'Return ONLY JSON: {"name":"ARIA","version":5}'),
    ]:
        t0 = time.time()
        try:
            r = chat([{"role": "user", "content": prompt}], model=model)
            print(f"  [{name}] {time.time()-t0:.1f}s -> {r.strip()[:100]}")
        except Exception as e:
            print(f"  [{name}] FAIL: {e}")
print("DONE")