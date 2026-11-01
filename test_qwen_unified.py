"""Test qwen3.5:2b as unified text+vision model."""
import json, urllib.request, time, sys

OLLAMA = "http://localhost:11434"
MODEL = "qwen3.5:2b"

def ollama_chat(messages, model=MODEL, expect_json=False, timeout=120):
    body = json.dumps({
        "model": model, "messages": messages, "stream": False,
        "options": {"temperature": 0.1, "num_ctx": 2048, "keep_alive": 0},
    }).encode()
    req = urllib.request.Request(f"{OLLAMA}/api/chat", data=body,
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read())
    msg = data.get("message", {})
    content = msg.get("content", "")
    return content

def ollama_vision(image_b64, prompt, model=MODEL, timeout=180):
    body = json.dumps({
        "model": model, "stream": False,
        "messages": [{"role": "user", "content": prompt,
                      "images": [image_b64]}],
        "options": {"temperature": 0.1, "num_ctx": 2048, "keep_alive": 0},
    }).encode()
    req = urllib.request.Request(f"{OLLAMA}/api/chat", data=body,
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read())
    return data.get("message", {}).get("content", "")

# --- TEXT TESTS ---
print("=== TEXT TESTS (qwen3.5:2b) ===")
text_tests = [
    ("simple math", "What is 17 * 23? Answer with only the number."),
    ("code gen", "Write a Python function that checks if a number is prime. One line only."),
    ("json extract", 'Return ONLY a JSON object: {"name":"ARIA","version":5}'),
    ("reasoning", "If a bat and a ball cost $1.10 together and the bat costs $1.00 more than the ball, how much does the ball cost? Answer with just the number."),
]
text_pass = 0
for name, prompt in text_tests:
    t0 = time.time()
    try:
        resp = ollama_chat([{"role": "user", "content": prompt}])
        dt = time.time() - t0
        print(f"  [{name}] {dt:.1f}s -> {resp[:120]}")
        text_pass += 1
    except Exception as e:
        print(f"  [{name}] FAIL: {e}")
print(f"Text: {text_pass}/{len(text_tests)} passed")

# --- VISION TESTS ---
print("\n=== VISION TESTS (qwen3.5:2b) ===")
import base64, os
# Find a screenshot or image to test with
candidates = []
for root, dirs, files in os.walk("."):
    for f in files:
        if f.lower().endswith((".png", ".jpg", ".jpeg")):
            candidates.append(os.path.join(root, f))
        if len(candidates) >= 5:
            break
    if len(candidates) >= 5:
        break

if not candidates:
    print("  No images found for vision test")
else:
    img = candidates[0]
    print(f"  Testing with: {img}")
    with open(img, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    try:
        t0 = time.time()
        resp = ollama_vision(b64, "Describe this image in one sentence. What do you see?")
        dt = time.time() - t0
        print(f"  [vision describe] {dt:.1f}s -> {resp[:200]}")
    except Exception as e:
        print(f"  [vision describe] FAIL: {e}")

# --- COMPARE with granite3.2-vision ---
print("\n=== VISION COMPARE (granite3.2-vision:2b) ===")
if candidates:
    with open(candidates[0], "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    try:
        t0 = time.time()
        resp = ollama_vision(b64, "Describe this image in one sentence.", model="granite3.2-vision:2b")
        dt = time.time() - t0
        print(f"  [granite vision] {dt:.1f}s -> {resp[:200]}")
    except Exception as e:
        print(f"  [granite vision] FAIL: {e}")

print("\n=== DONE ===")