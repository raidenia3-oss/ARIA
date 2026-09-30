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
import logging
import subprocess
import requests
from pathlib import Path

sys.path.insert(0, 'ARIA_APP/backend')
from dotenv import load_dotenv
load_dotenv('ARIA_APP/backend/.env')

from skills.custom.self_improvement import get_self_improvement

BASE_URL = os.environ.get("ARIA_BACKEND_URL", "http://127.0.0.1:8002")
TUNNEL_URL = "https://aria-backend.loca.lt"
CHECK_INTERVAL = 300  # 5 minutos

logger = logging.getLogger("aria_autonomous")


def _get_aria_home() -> Path:
    """Return ARIA home directory."""
    return Path(__file__).resolve().parent


def check_for_updates() -> dict:
    """Check for rolling release updates via the pipeline.

    Returns a dict with status info. Safe to call every cycle.
    """
    try:
        from aria_release import RollingReleasePipeline, ReleaseChannel

        aria_home = _get_aria_home()
        channel_str = os.environ.get("ARIA_RELEASE_CHANNEL", "stable")
        try:
            channel = ReleaseChannel.from_string(channel_str)
        except ValueError:
            channel = ReleaseChannel.STABLE

        pipeline = RollingReleasePipeline(
            aria_home=aria_home,
            channel=channel,
            current_version=os.environ.get("ARIA_VERSION", "6.0.0"),
        )

        result = pipeline.check_and_update()
        logger.info("Update check: %s", result)
        return result

    except ImportError as e:
        logger.debug("Rolling release not available: %s", e)
        return {"checked": False, "error": f"ImportError: {e}"}
    except Exception as e:
        logger.warning("Update check failed: %s", e)
        return {"checked": False, "error": str(e)}


def create_snapshot(name: str, description: str = "") -> bool:
    """Create a manual snapshot before risky operations."""
    try:
        from aria_snapshot import SnapshotCreator

        aria_home = _get_aria_home()
        creator = SnapshotCreator(aria_home)
        snap = creator.create(name, description)
        logger.info("Snapshot created: %s (tag: %s)", snap.name, snap.git_tag)
        return True
    except Exception as e:
        logger.warning("Snapshot creation failed: %s", e)
        return False


def ensure_configured(verbose=True):
    """Guarantee the environment is ready before the first cycle.

    ARIA configures itself: a missing dependency or an unmigrated database is
    repaired here rather than crashing the loop. Failures return False so the
    loop logs and retries on its next pass instead of exiting.
    """
    try:
        from aria_autoconfig import ensure_configured as _ensure
    except ImportError as e:
        if verbose:
            print(f"[WARN] auto-config unavailable ({e}); continuing without it")
        return True
    if verbose:
        print("[INFO] Checking environment (self-configuring if needed)...")
    ready = _ensure(Path(__file__).resolve().parent)
    if verbose:
        print(f"[{'OK' if ready else 'WARN'}] Environment {'ready' if ready else 'incomplete'}")
        if not ready:
            print("[INFO] Run: python aria_setup.py --diagnose")
    return ready


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

    # Zero-touch: configure the environment before the first cycle. A failure
    # here is reported, not fatal - the loop still runs and retries next pass.
    ready = ensure_configured()
    if not ready:
        print("[WARN] Environment incomplete; running in degraded mode")
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
                # Check for rolling release updates (every cycle = 5 min)
                update_result = check_for_updates()
                if update_result.get("update_available"):
                    print(f"[INFO] New release available: v{update_result.get('version')}")
                elif update_result.get("applied"):
                    print(f"[INFO] Applied update to v{update_result.get('version')}")

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
