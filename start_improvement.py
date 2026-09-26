#!/usr/bin/env python3
"""
Start ARIA self-improvement loop
"""
import requests
import json
import time
import sys
import os

sys.stdout.reconfigure(encoding="utf-8")

BASE_URL = "http://127.0.0.1:8001"

def start_improvement():
    """Trigger self-improvement cycle"""
    print("🚀 Starting ARIA self-improvement loop...")

    try:
        resp = requests.post(
            f"{BASE_URL}/api/self-improvement/start",
            json={},
            timeout=300
        )

        if resp.status_code == 200:
            data = resp.json()
            print(f"\n✅ Self-improvement activated!")
            print(f"   Status: {data.get('status')}")
            print(f"   Message: {data.get('message')}")
            print(f"\n📊 Cycle result:")
            print(json.dumps(data.get('result', {}), indent=2, ensure_ascii=False))
            return True
        else:
            print(f"❌ Failed: {resp.status_code}")
            print(f"   {resp.text}")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def monitor_cycle():
    """Monitor self-improvement cycle"""
    print("\n📡 Monitoring cycle (press Ctrl+C to stop)...")

    try:
        while True:
            try:
                resp = requests.get(f"{BASE_URL}/api/self-improvement/status", timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    print(f"   Status: {data.get('status')}")
                    print(f"   Initialized: {data.get('initialized')}")
                    print(f"   GitHub configured: {data.get('github_configured')}")
                    print(f"   Last update: {data.get('last_update', 'N/A')}")
            except Exception:
                pass

            time.sleep(5)
    except KeyboardInterrupt:
        print("\n⏹️  Monitoring stopped")

if __name__ == "__main__":
    if start_improvement():
        monitor_cycle()
    sys.exit(0 if start_improvement() else 1)
