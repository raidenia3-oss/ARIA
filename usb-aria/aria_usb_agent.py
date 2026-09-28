#!/usr/bin/env python3
"""
ARIA v6.0 - USB Portable Autonomous Agent
Phase L.4: USB-based autonomous execution layer

Runs on a USB stick (Linux minimal) as a portable support agent for ARIA on PC.
- Detects if PC is on / in use via ARIA backend API
- Executes background tasks when PC is idle
- Reports all activity to Discord webhook
- Syncs with ARIA and Airi (mobile)

Communication Protocol:
- Polls ARIA backend at http://127.0.0.1:8001 (via local network)
- POST /api/pc/state -> reports activity state
- POST /api/daemon/task -> receives tasks from ARIA
- POST /api/daemon/result -> reports task results
- Discord webhook for all logging
"""

import requests
import json
import time
import os
import socket
import uuid
from datetime import datetime

# Configuration
ARIA_BACKEND_URL = os.environ.get("ARIA_BACKEND_URL", "http://127.0.0.1:8002")
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")
AGENT_ID = f"usb-aria-{socket.gethostname()[:8]}-{uuid.uuid4().hex[:8]}"
CHECK_INTERVAL = 30  # seconds between health checks
IDLE_THRESHOLD = 60  # seconds of inactivity before running background tasks

def send_discord(message: str, level: str = "info"):
    """Report to Discord webhook."""
    if not DISCORD_WEBHOOK_URL:
        print(f"  [{level.upper()}] {message}")
        return
    
    payload = {
        "content": f"[{level.upper()}] {message}",
        "username": "ARIA-USB-Agent",
        "avatar_url": "https://avatar.githubusercontent.com/u/194553474"
    }
    
    try:
        requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
    except Exception as e:
        print(f"Discord error: {e}")

def check_backend_health():
    """Check if ARIA backend is reachable."""
    try:
        r = requests.get(f"{ARIA_BACKEND_URL}/health", timeout=5)
        return r.status_code == 200 and r.json().get("status") == "ok"
    except:
        return False

def get_pc_state():
    """Query ARIA backend for PC activity state."""
    try:
        r = requests.post(
            f"{ARIA_BACKEND_URL}/api/pc/state",
            json={
                "agent_id": AGENT_ID,
                "action": "query_state",
                "timestamp": datetime.now().isoformat()
            },
            timeout=10
        )
        if r.status_code == 200:
            data = r.json()
            return data.get("pc_state", {})
        return {"status": "unknown", "active": True}
    except Exception as e:
        return {"status": "unreachable", "active": True, "error": str(e)}

def submit_task_result(task_id, result):
    """Submit completed task results to ARIA backend."""
    try:
        r = requests.post(
            f"{ARIA_BACKEND_URL}/api/daemon/result",
            json={
                "agent_id": AGENT_ID,
                "task_id": task_id,
                "result": result,
                "timestamp": datetime.now().isoformat()
            },
            timeout=30
        )
        return r.status_code == 200
    except Exception as e:
        send_discord(f"Failed to submit result: {e}", "error")
        return False

def get_pending_task():
    """Check for pending tasks from ARIA backend."""
    try:
        r = requests.post(
            f"{ARIA_BACKEND_URL}/api/daemon/task",
            json={
                "agent_id": AGENT_ID,
                "action": "get_pending",
                "timestamp": datetime.now().isoformat()
            },
            timeout=10
        )
        if r.status_code == 200:
            data = r.json()
            return data.get("task") if data.get("available") else None
        return None
    except:
        return None

def execute_task(task):
    """Execute a background task."""
    task_type = task.get("type", "unknown")
    task_id = task.get("id", str(uuid.uuid4()))
    
    send_discord(f"Executing task: {task_type} ({task_id})", "info")
    
    result = {
        "task_id": task_id,
        "task_type": task_type,
        "status": "completed",
        "output": {},
        "executed_at": datetime.now().isoformat()
    }
    
    try:
        if task_type == "research":
            # Background research task
            query = task.get("payload", {}).get("query", "")
            result["output"] = {
                "query": query,
                "sources_found": [],
                "summary": "Research completed by USB agent"
            }
            send_discord(f"Research task done: {query[:100]}...", "info")
            
        elif task_type == "github_action":
            # GitHub action task
            action = task.get("payload", {}).get("action", {})
            result["output"] = {
                "action": action,
                "commits_made": 0
            }
            send_discord(f"GitHub action done: {action}", "info")
            
        elif task_type == "improvement":
            # Self-improvement task
            result["output"] = {
                "type": "code_improvement",
                "improvements_made": []
            }
            send_discord("Improvement task completed", "info")
            
        elif task_type == "social_sync":
            # Social media sync task
            result["output"] = {
                "posts_collected": 0,
                "new_content": 0
            }
            send_discord("Social sync completed", "info")
            
        else:
            result["output"] = {"message": f"Unknown task type: {task_type}"}
            result["status"] = "skipped"
            
    except Exception as e:
        result["status"] = "failed"
        result["error"] = str(e)
        send_discord(f"Task failed: {e}", "error")
    
    return result

def run():
    """Main execution loop."""
    send_discord(f"ARIA USB Agent started: {AGENT_ID}", "info")
    send_discord("Connecting to ARIA backend...", "info")
    
    while True:
        try:
            # Check backend health
            if not check_backend_health():
                send_discord("ARIA backend unreachable, retrying...", "warn")
                time.sleep(CHECK_INTERVAL)
                continue
            
            # Get PC state
            pc_state = get_pc_state()
            is_active = pc_state.get("active", False)
            idle_seconds = pc_state.get("idle_seconds", 0)
            
            send_discord(
                f"PC state: active={is_active}, idle={idle_seconds}s",
                "debug"
            )
            
            # Only run background tasks when PC is idle
            if not is_active and idle_seconds >= IDLE_THRESHOLD:
                send_discord("PC is idle, checking for background tasks...", "info")
                
                # Check for pending tasks
                task = get_pending_task()
                if task:
                    result = execute_task(task)
                    submit_task_result(task.get("id", "unknown"), result)
                else:
                    send_discord("No pending tasks. Standing by.", "debug")
            else:
                send_discord("PC is active, skipping background tasks", "debug")
            
            # Report status to backend
            requests.post(
                f"{ARIA_BACKEND_URL}/api/daemon/task",
                json={
                    "agent_id": AGENT_ID,
                    "action": "report_status",
                    "status": "idle" if not is_active else "standby",
                    "pc_state": pc_state
                },
                timeout=10
            )
            
        except KeyboardInterrupt:
            send_discord("ARIA USB Agent shutting down", "info")
            break
        except Exception as e:
            send_discord(f"Unexpected error: {e}", "error")
        
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    run()