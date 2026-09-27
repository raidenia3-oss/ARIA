#!/usr/bin/env python3
"""
ARIA v6.0 - Auto-Improvement Loop Controller
Inspired by Grand Sage of Tensura

This script runs the self-improvement cycle autonomously:
- Monitors system health
- Triggers improvement cycles when issues/PRs are detected
- Auto-commits changes
- Maintains localtunnel connection
"""

import sys
import os
import time
import json
import subprocess
import requests

sys.path.insert(0, 'ARIA_APP/backend')
from dotenv import load_dotenv
load_dotenv('ARIA_APP/backend/.env')

from skills.custom.self_improvement import get_self_improvement

BASE_URL = "http://127.0.0.1:8001"
TUNNEL_URL = "https://aria-backend.loca.lt"
CHECK_INTERVAL = 300  # 5 minutos

def check_backend_health():
    try:
        r = requests.get(f"{BASE_URL}/health", timeout=5)
        return r.status_code == 200 and r.json().get("status") == "ok"
    except:
        return False

def check_tunnel_health():
    try:
        r = requests.get(f"{TUNNEL_URL}/health", timeout=5)
        return r.status_code == 200
    except:
        return False

def run_improvement_cycle(full=True):
    si = get_self_improvement()
    si.initialize()
    
    params = {
        'auto_commit': True,
        'triage_issues': True,
        'analyze_prs': True,
        'auto_release': False,
        'gen_docs': True
    } if full else {
        'auto_commit': True,
        'triage_issues': False,
        'analyze_prs': False,
        'auto_release': False,
        'gen_docs': False
    }
    
    return si.run_improvement_cycle(params)

def main():
    print("=" * 60)
    print("ARIA v6.0 - Wise Sage Autonomous Mode")
    print("=" * 60)
    print()
    
    while True:
        if not check_backend_health():
            print("[WARN] Backend health check failed")
            print("[INFO] Backend should be restarted by start_backend.bat")
        elif not check_tunnel_health():
            print("[WARN] Tunnel health check failed")
            print("[INFO] Tunnel should reconnect via start_tunnel.bat")
        else:
            print("[OK] System healthy, running improvement cycle...")
            try:
                result = run_improvement_cycle(full=True)
                actions = result.get("result", {}).get("actions", [])
                for a in actions:
                    status = a.get("status", "unknown")
                    error = a.get("error", "")
                    symbol = "✅" if status in ("committed", "complete", "generated", "skipped") else "❌"
                    print(f"  {symbol} {a['action']}: {status} {error}")
                print(f"[OK] Cycle complete at {time.strftime('%Y-%m-%d %H:%M:%S')}")
            except Exception as e:
                print(f"[ERROR] Cycle failed: {e}")
        
        print(f"[INFO] Waiting {CHECK_INTERVAL}s until next cycle...")
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
