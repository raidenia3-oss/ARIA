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
import threading
import urllib.request
import urllib.error
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# This file is run as `python v6/aria_usb_agent.py`, so sys.path[0] is v6/ and the
# repo root — where aria_video_library lives — is not importable. Add it rather
# than relying on the caller's PYTHONPATH.
_REPO_ROOT = str(Path(__file__).resolve().parent.parent)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

try:
    from aria_video_library import AddResult, LibraryError, VideoLibrary
except ImportError:  # The agent still polls without the library installed.
    AddResult = None  # type: ignore[assignment]
    LibraryError = RuntimeError  # type: ignore[misc, assignment]
    VideoLibrary = None  # type: ignore[assignment]

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

#: Backend the agent talks to. `main_loop` updates it when a different URL is
#: passed on the command line; task helpers outside the loop read it from here.
CURRENT_BASE_URL = DEFAULT_BASE_URL


#: Discord rejects messages longer than this, and a video notification with its
#: summary easily exceeds it; the same limit is applied in aria_video_library.
DISCORD_CONTENT_LIMIT = 2000
DISCORD_TRUNCATION_MARKER = "\n… *(truncated)*"


def discord_notify(content: str, username: str = "USB-ARIA Agent") -> bool:
    if not DISCORD_WEBHOOK:
        return False
    message = content
    if len(message) > DISCORD_CONTENT_LIMIT:
        message = message[: DISCORD_CONTENT_LIMIT - len(DISCORD_TRUNCATION_MARKER)].rstrip()
        message += DISCORD_TRUNCATION_MARKER
    payload = json.dumps({"content": message, "username": username}).encode()
    req = urllib.request.Request(
        DISCORD_WEBHOOK,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            # Discord answers 204 today; any 2xx is a delivery.
            return 200 <= resp.status < 300
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


@contextmanager
def task_heartbeat(base_url: str, status: str) -> Any:
    """Keep the daemon informed while a long task runs.

    The poll loop only heartbeats between iterations, so a task that takes longer
    than the lease looks like a dead agent and gets re-dispatched. A daemon
    thread posts on its own schedule for the duration of the block.
    """
    stop = threading.Event()

    def beat() -> None:
        while not stop.wait(HEARTBEAT_INTERVAL):
            send_heartbeat(base_url, f"executing:{status}")

    thread = threading.Thread(target=beat, name="aria-task-heartbeat", daemon=True)
    thread.start()
    try:
        yield
    finally:
        stop.set()
        thread.join(timeout=1)
        send_heartbeat(base_url, "idle")


_VIDEO_LIBRARY: Any = None


def get_video_library() -> Any:
    """Lazily build the shared :class:`VideoLibrary`.

    Constructing it creates the stick layout, which is wasted work on every poll
    iteration; the instance is cached because the index write path is not
    reentrant-friendly across processes.
    """
    global _VIDEO_LIBRARY
    if _VIDEO_LIBRARY is None:
        if VideoLibrary is None:
            raise LibraryError("aria_video_library is not importable from this interpreter")
        _VIDEO_LIBRARY = VideoLibrary()
        report = _VIDEO_LIBRARY.storage.report()
        log.info(
            f"Video library at {report['root']} ({report['source']}, "
            f"removable={report['removable']})"
        )
    return _VIDEO_LIBRARY


def handle_instagram_download(
    url: str,
    tags: Optional[list] = None,
    agent_type: Optional[str] = None,
    context: str = "",
) -> Dict[Any, Any]:
    """Download a video, index it, and tell the interested agent about it.

    Returns a plain dict so the result can be embedded in a task submission
    without dragging dataclasses across the HTTP boundary. Failures are reported
    as ``status: "failed"`` rather than raised, because a single bad URL must not
    kill the agent's main loop.
    """
    try:
        result: AddResult = get_video_library().add_reference(
            url, tags=tags, agent_type=agent_type, context=context
        )
    except Exception as e:
        log.error(f"Video reference failed for {url}: {e}")
        return {"status": "failed", "url": url, "error": str(e)}

    payload = result.to_dict()
    payload["status"] = "success"
    payload["url"] = url
    log.info(f"Video reference ready: {result.video.id} (added={result.added})")
    return payload


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

    elif task_type == "video_reference":
        url = payload.get("url", "")
        if not url:
            return ("failed", "video_reference task has no url")
        # A download can run for an hour. Without a heartbeat the daemon sees a
        # silent agent, the claim can be re-dispatched, and a second downloader
        # would race this one for the same file and index.
        with task_heartbeat(CURRENT_BASE_URL, f"video:{url[:80]}"):
            report = handle_instagram_download(
                url,
                tags=payload.get("tags") or [],
                agent_type=payload.get("agent_type"),
                context=payload.get("context", ""),
            )
        return (report.get("status", "failed"), json.dumps(report, default=str))

    else:
        return ("failed", f"Unknown task type: {task_type}")


def main_loop(base_url: str) -> None:
    global CURRENT_BASE_URL
    CURRENT_BASE_URL = base_url
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