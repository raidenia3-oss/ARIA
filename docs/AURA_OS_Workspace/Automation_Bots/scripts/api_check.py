import requests, json, os, sys

def check_railway_status():
    token = os.environ.get("RAILWAY_TOKEN")
    if not token:
        print("[SKIP] RAILWAY_TOKEN no está exportado")
        return
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    query = """
    { deployments(last: 1) { edges { node { id status createdAt } } } }
    """
    r = requests.post("https://api.railway.app/graphql/v2", json={"query": query}, headers=headers, timeout=15)
    if r.status_code == 200:
        data = r.json()
        print(f"[Railway API] {json.dumps(data, indent=2)}")
    else:
        print(f"[Railway API] Error {r.status_code}: {r.text[:500]}")

def check_vercel_status():
    token = os.environ.get("VERCEL_TOKEN")
    if not token:
        print("[SKIP] VERCEL_TOKEN no está exportado")
        return
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get("https://api.vercel.com/v9/deployments?limit=1", headers=headers, timeout=15)
    if r.status_code == 200:
        data = r.json()
        print(f"[Vercel API] {json.dumps(data, indent=2)[:500]}")
    else:
        print(f"[Vercel API] Error {r.status_code}: {r.text[:500]}")

if __name__ == "__main__":
    check_railway_status()
    check_vercel_status()
