import time
import requests

time.sleep(2)

# Test 1: Health endpoint
print("1. Testing /health endpoint...")
r = requests.get("http://127.0.0.1:5001/health")
print(f"   HTTP {r.status_code}: {r.json()}")

# Test 2: Net Recon endpoint
print("\n2. Testing /api/net_recon endpoint...")
try:
    r = requests.post("http://127.0.0.1:5001/api/net_recon", json={"subnet": "192.168.1.0/24"})
    print(f"   HTTP {r.status_code}: {r.json()}")
except Exception as e:
    print(f"   Error: {e}")

# Test 3: Data Exfil endpoint
print("\n3. Testing /api/data_exfil endpoint...")
try:
    r = requests.post("http://127.0.0.1:5001/api/data_exfil", json={"filepath": "test.txt", "channel": "dns"})
    print(f"   HTTP {r.status_code}: {r.json()}")
except Exception as e:
    print(f"   Error: {e}")

print("\n✅ All endpoints tested.")