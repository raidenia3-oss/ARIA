import json, urllib.request, urllib.error

BASE = "http://localhost:8000"

def post(path, data, timeout=60):
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=json.dumps(data).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return {"error": e.read().decode()}
    except Exception as e:
        return {"error": str(e)}

def get(path, timeout=15):
    try:
        with urllib.request.urlopen(f"{BASE}{path}", timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        return {"error": str(e)}

print("=== SERVER ===")
print(get("/health"))

print("\n=== ARIA HEALTH ===")
print(get("/api/aria/health"))

print("\n=== AI STATUS ===")
print(json.dumps(get("/api/ai/status"), indent=2))

print("\n=== ARIA CHAT (greeting) ===")
r = post("/api/aria/chat", {"message": "Hola ARIA"})
print(json.dumps(r, indent=2)[:500])

print("\n=== ARIA CHAT (magic question) ===")
r = post("/api/aria/chat", {"message": "Explícame cómo funciona la magia"})
print(json.dumps(r, indent=2)[:500])

print("\n=== MAIN CHAT ===")
r = post("/api/chat", {"message": "Hola como estas?"})
print(json.dumps(r, indent=2)[:500])

print("\n=== ARIA PROFILE ===")
print(json.dumps(get("/api/aria/profile"), indent=2)[:500])

print("\n=== CONTENT SUGGEST ===")
r = post("/api/aria/content/suggest", {"current_app": "anime viewer", "activity": "watching", "searches": [{"query": "demon slayer"}]})
print(json.dumps(r, indent=2)[:500])

print("\n=== CHARACTER GEN ===")
r = post("/api/aria/generate/character", {"role": "hero", "traits": ["mysterious", "strong"]})
print(json.dumps(r, indent=2)[:500])

print("\n=== DATASET CREATE ===")
r = post("/api/aria/dataset/create", {})
print(json.dumps(r, indent=2)[:300])

print("\n=== STORY GEN ===")
r = post("/api/aria/generate/story", {"prompt": "A wizard discovers a portal", "length": "short"})
print(json.dumps(r, indent=2)[:300])

print("\n=== WORLD GEN ===")
r = post("/api/aria/generate/world", {"theme": "fantasy", "size": "medium"})
print(json.dumps(r, indent=2)[:300])

print("\n=== PROMPT GEN ===")
r = post("/api/aria/generate/prompt", {"description": "dark wizard battle", "style": "anime"})
print(json.dumps(r, indent=2)[:300])

print("\n=== TESTS ===")
r = post("/api/aria/test/run", {})
print(json.dumps(r, indent=2)[:300])

print("\n=== INTERACTIVE STORY ===")
r = post("/api/aria/content/interactive", {"scene": "el heroe despierta", "story_id": "test1", "branches": 3})
print(json.dumps(r, indent=2)[:400])
