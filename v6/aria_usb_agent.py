#!/usr/bin/env python3
"""
USB-ARIA Agent for ARIA v6.0
Polls Axum backend on port 8002, executes daemon tasks, reports results.
"""

import os
import sys
import json
import time
import uuid
import logging
import subprocess
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("aria-usb-agent")

AGENT_ID = f"usb-aria-{uuid.uuid4().hex[:8]}"
DEFAULT_BASE_URL = os.getenv("ARIA_BASE_URL", "http://127.0.0.1:8002")
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK_URL", "")
IDLE_THRESHOLD = int(os.getenv("ARIA_IDLE_THRESHOLD", "60"))
POLL_INTERVAL = int(os.getenv("ARIA_POLL_INTERVAL", "30"))
HEARTBEAT_INTERVAL = int(os.getenv("ARIA_HEARTBEAT_INTERVAL", "30"))


def discord_notify(content: str, username: str = "USB-ARIA Agent") -> bool:
    if not DISCORD_WEBHOOK:
        return False
    payload = json.dumps({"content": content, "username": username}).encode()
    req = urllib.request.Request(
        DISCORD_WEBHOOK,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 204
    except Exception as e:
        log.warning(f"Discord webhook failed: {e}")
        return False


def http_get(url: str, timeout: int = 10) -> Optional[Dict[Any, Any]]:
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        log.debug(f"HTTP {e.code} GET {url}: {e.read().decode()}")
    except Exception as e:
        log.debug(f"GET {url} failed: {e}")
    return None


def http_post(url: str, data: Dict[Any, Any], timeout: int = 10) -> Optional[Dict[Any, Any]]:
    payload = json.dumps(data).encode()
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status in (200, 201):
                return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        log.debug(f"HTTP {e.code} POST {url}: {e.read().decode()}")
    except Exception as e:
        log.debug(f"POST {url} failed: {e}")
    return None


def get_pc_state(base_url: str) -> Optional[Dict[Any, Any]]:
    return http_get(f"{base_url}/api/pc/state")


def get_daemon_task(base_url: str) -> Optional[Dict[Any, Any]]:
    return http_get(f"{base_url}/api/daemon/task")


def claim_task(base_url: str, task_id: str) -> Optional[Dict[Any, Any]]:
    return http_post(f"{base_url}/api/daemon/task", {"agent_id": AGENT_ID, "action": "claim", "task": task_id})


def submit_result(base_url: str, task_id: str, status: str, output: str) -> Optional[Dict[Any, Any]]:
    return http_post(f"{base_url}/api/daemon/result", {
        "agent_id": AGENT_ID,
        "task_id": task_id,
        "status": status,
        "output": output
    })


def send_heartbeat(base_url: str, status: str = "idle") -> Optional[Dict[Any, Any]]:
    return http_post(f"{base_url}/api/daemon/heartbeat", {"agent_id": AGENT_ID, "status": status})


def execute_task(task: Dict[Any, Any]) -> tuple[str, str]:
    task_type = task.get("type", "unknown")
    payload = task.get("payload", {})

    if task_type == "system_command":
        cmd = payload.get("command", "")
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=300
            )
            output = result.stdout
            if result.stderr:
                output += f"\n[stderr] {result.stderr}"
            return ("success" if result.returncode == 0 else "failed", output)
        except subprocess.TimeoutExpired:
            return ("failed", "Command timed out after 300s")
        except Exception as e:
            return ("failed", f"Execution error: {e}")

    elif task_type == "log":
        msg = payload.get("message", "No message")
        log.info(f"Task log: {msg}")
        return ("success", f"Logged: {msg}")

    else:
        return ("failed", f"Unknown task type: {task_type}")


def main_loop(base_url: str) -> None:
    log.info(f"USB-ARIA Agent started: {AGENT_ID}")
    log.info(f"Backend: {base_url}")
    log.info(f"Poll interval: {POLL_INTERVAL}s, Idle threshold: {IDLE_THRESHOLD}s")

    discord_notify(f"🟢 **USB-ARIA Agent Online**\nAgent: `{AGENT_ID}`\nBackend: `{base_url}`")

    last_heartbeat = 0

    while True:
        try:
            now = time.time()

            if now - last_heartbeat >= HEARTBEAT_INTERVAL:
                send_heartbeat(base_url, "polling")
                last_heartbeat = now

            pc_state = get_pc_state(base_url)
            if not pc_state:
                log.debug("PC state unavailable, retrying...")
                time.sleep(POLL_INTERVAL)
                continue

            idle_seconds = pc_state.get("idle_seconds", 0)
            active = pc_state.get("active", False)

            if not active and idle_seconds >= IDLE_THRESHOLD:
                log.info(f"PC idle for {idle_seconds}s, checking for tasks...")
                send_heartbeat(base_url, "checking_tasks")

                task_data = get_daemon_task(base_url)
                if task_data and task_data.get("available"):
                    task = task_data.get("task")
                    task_id = task.get("id") if isinstance(task, dict) else str(task)

                    log.info(f"Claiming task: {task_id}")
                    send_heartbeat(base_url, f"executing:{task_id}")

                    claim_result = claim_task(base_url, task_id)
                    if claim_result and claim_result.get("status") == "assigned":
                        status, output = execute_task(task)
                        log.info(f"Task {task_id} -> {status}")
                        submit_result(base_url, task_id, status, output)
                        send_heartbeat(base_url, "idle")
                    else:
                        log.warning(f"Failed to claim task {task_id}")
                else:
                    log.debug("No pending tasks")

            time.sleep(POLL_INTERVAL)

        except KeyboardInterrupt:
            log.info("Shutdown requested")
            discord_notify(f"🔴 **USB-ARIA Agent Offline**\nAgent: `{AGENT_ID}`")
            break
        except Exception as e:
            log.error(f"Main loop error: {e}")
            discord_notify(f"⚠️ **USB-ARIA Agent Error**\nAgent: `{AGENT_ID}`\n```{e}```")
            time.sleep(5)


def run_with_retry(base_url: str) -> None:
    while True:
        try:
            main_loop(base_url)
        except Exception as e:
            log.critical(f"Fatal error, restarting in 5s: {e}")
            discord_notify(f"💥 **USB-ARIA Agent Crashed**\nAgent: `{AGENT_ID}`\n```{e}```\nRestarting in 5s...")
            time.sleep(5)


if __name__ == "__main__":
    base_url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_BASE_URL
    run_with_retry(base_url)