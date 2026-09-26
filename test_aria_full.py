import json, urllib.request, urllib.error

BASE = "http://localhost:8000"

def post(path, data, timeout=120):
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

def get(path, timeout=30):
    try:
        with urllib.request.urlopen(f"{BASE}{path}", timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        return {"error": str(e)}

print("=== ARIA CHAT ===")
r = post("/api/aria/chat", {"message": "Hola ARIA, como estas?"})
print(json.dumps(r, indent=2)[:600])

print("\n=== ARIA CHAT 2 ===")
r = post("/api/aria/chat", {"message": "Explícame la magia"})
print(json.dumps(r, indent=2)[:600])

print("\n=== ARIA LEARN ===")
r = post("/api/aria/learn", {"user_input": "me gusta programar", "feedback": "más detalle"})
print(json.dumps(r, indent=2))

print("\n=== ARIA LEARN 2 ===")
r = post("/api/aria/learn", {"user_input": "estoy diseñando UI", "feedback": "menos"})
print(json.dumps(r, indent=2))
