import time
import requests
import sys

sys.stdout.reconfigure(encoding='utf-8') # Configure stdout for UTF-8

token = sys.argv[1]
url = "https://huggingface.co/api/spaces/raiden456/raiden456aura-chat"
headers = {"Authorization": f"Bearer {token}"}

print("Monitoring space build status...")
for i in range(30):
    try:
        r = requests.get(url, headers=headers)
        r.raise_for_status()
        data = r.json()
        runtime = data.get("runtime", {})
        stage = runtime.get("stage", "N/A")
        error = runtime.get("error", "N/A")
        print(f"[{i+1}/30] Stage: {stage}, Error: {error}")
        
        if stage == "RUNNING":
            print(f"\n✅ Space is RUNNING!")
            print(f"URL: https://raiden456-raiden456aura-chat.hf.space")
            sys.exit(0)
        elif stage == "RUNTIME_ERROR":
            print(f"\n❌ Space RUNTIME_ERROR: {error}")
            sys.exit(1)
    except Exception as e:
        print(f"[{i+1}/30] Error checking: {e}")
    time.sleep(15)

print("\n⚠️ Timeout: Space did not reach RUNNING state within timeout.")
sys.exit(1)
