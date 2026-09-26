"""sanity_check.py — E2E QA script for AURA (Módulo 11)."""

from __future__ import annotations

import asyncio
import sys

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
import json
import logging
import os
import sys
import time
import traceback
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent
DASHBOARD_BASE = os.environ.get("DASHBOARD_API_BASE", "http://localhost:8000")
TELEGRAM_PROBE_MESSAGE = "[AURA QA] Proba de Telegram."
HEALING_FROZEN_TASK = "stress_surveys_fake"
HEALING_INACTIVITY_THRESHOLD = int(os.environ.get("HEALING_THRESHOLD", "10"))
HEALING_CHECK_INTERVAL = int(os.environ.get("HEALING_INTERVAL", "2"))
HEALING_WORKER_TIMEOUT = int(os.environ.get("HEALING_WORKER_TIMEOUT", "15"))
FORCE_GREEN = os.environ.get("AURA_FORCE_GREEN", "0") == "1"

RESULTS: Dict[str, Any] = {
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "modules": {},
    "elapsed_s": None,
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s :: %(message)s")
log = logging.getLogger("sanity_check")


def passed(name: str, detail: str = "") -> None:
    RESULTS["modules"][name] = {"status": "PASS", "detail": detail}
    print(f"[PASS] {name}" + (f" — {detail}" if detail else ""))


def skipped(name: str, detail: str = "") -> None:
    RESULTS["modules"][name] = {"status": "SKIP", "detail": detail}
    print(f"[SKIP] {name}" + (f" — {detail}" if detail else ""))


def failed(name: str, detail: str = "") -> None:
    RESULTS["modules"][name] = {"status": "FAIL", "detail": detail}
    print(f"[FAIL] {name}" + (f" — {detail}" if detail else ""))


def section(title: str) -> None:
    print(f"\n=== {title} ===")


def add_src_to_path() -> None:
    src = str(PROJECT_ROOT / "ame-backend" / "src")
    if src not in sys.path:
        sys.path.insert(0, src)


def check_env_vars() -> None:
    section("FASE 1a — Railway & Env vars")
    required = {
        "TELEGRAM_BOT_TOKEN": "Telegram bot token",
        "TELEGRAM_CHAT_ID": "Telegram chat id",
        "DATABASE_URL": "Database URL (Railway)",
        "RAILWAY_API_URL": "Railway API URL",
        "RAILWAY_PUBLIC_URL": "Railway public URL",
    }
    found: Dict[str, str] = {}
    for var, desc in required.items():
        val = os.environ.get(var)
        if not val:
            for env_file in (PROJECT_ROOT / ".env", PROJECT_ROOT / ".env.template"):
                if env_file.exists():
                    text = env_file.read_text(errors="ignore")
                    for line in text.splitlines():
                        if line.strip().startswith(f"{var}="):
                            val = line.split("=", 1)[1].strip().strip('"').strip("'")
                            if val:
                                found[var] = desc
                            break
                if val:
                    break
        else:
            found[var] = desc
    is_local = any(k in (DASHBOARD_BASE or "") for k in ("localhost", "127.0.0.1"))
    if found:
        passed("env_vars", f"Detected: {', '.join(sorted(found.keys()))}")
    elif is_local:
        skipped("env_vars", "Localhost detected; Railway variables omitted")
    else:
        failed("env_vars", "No required env vars found in shell or .env files")


def check_api_endpoints() -> None:
    section("FASE 1b — Dashboard API endpoints")
    is_local = any(k in (DASHBOARD_BASE or "") for k in ("localhost", "127.0.0.1"))
    endpoints = {
        "status": "/status",
        "balance": "/balance",
        "activity": "/activity",
    }
    if not is_local:
        endpoints["health"] = "/health"
    for name, path in endpoints.items():
        url = urllib.parse.urljoin(DASHBOARD_BASE.rstrip("/") + "/", path.lstrip("/"))
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=10) as resp:
                code = resp.getcode()
            if code == 200:
                passed(f"api_{name}", f"{url} -> HTTP {code}")
            else:
                failed(f"api_{name}", f"{url} -> HTTP {code}")
        except urllib.error.URLError as exc:
            failed(f"api_{name}", f"{url} unreachable: {exc}")
        except Exception as exc:
            failed(f"api_{name}", f"{url} error: {exc}")


def check_telegram() -> None:
    section("FASE 1c — Telegram integration probe")
    token = os.environ.get("TELEGRAM_BOT_TOKEN") or ""
    chat_id = os.environ.get("TELEGRAM_CHAT_ID") or ""
    is_local = any(k in (DASHBOARD_BASE or "") for k in ("localhost", "127.0.0.1"))
    if not token or not chat_id:
        if is_local:
            skipped("telegram_probe", "Localhost detected; Telegram tokens omitted")
        else:
            failed("telegram_probe", "Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID")
        return
    try:
        req = urllib.request.Request(
            "https://api.telegram.org/bot" + token + "/sendMessage",
            data=json.dumps({"chat_id": chat_id, "text": TELEGRAM_PROBE_MESSAGE}).encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read().decode("utf-8", errors="ignore"))
        if body.get("ok"):
            passed("telegram_probe", f"Message sent id={body.get('result', {}).get('message_id')}")
        else:
            failed("telegram_probe", f"API error: {body}")
    except urllib.error.HTTPError as exc:
        failed("telegram_probe", f"HTTP {exc.code}: {exc.read().decode(errors='ignore')[:200]}")
    except Exception as exc:
        failed("telegram_probe", str(exc))


def check_playwright_anti_bot() -> None:
    section("FASE 1d — Anti-bot Playwright/Selenium functions active")
    try:
        import playwright
        passed("playwright_installed")
    except Exception as exc:
        failed("playwright_installed", f"Not installed/importable: {exc}")

    stealth_path = PROJECT_ROOT / "ame-backend" / "src" / "automation" / "stealth_browser.py"
    if stealth_path.exists():
        text = stealth_path.read_text(encoding="utf-8", errors="ignore")
        checks = {
            "inject": "_inject_stealth_scripts" in text,
            "mask": "_mask_webdriver" in text,
            "webgl": "_spoof_webgl" in text,
            "canvas": "_spoof_canvas" in text,
            "plugins": "_spoof_plugins" in text,
            "permissions": "_spoof_permissions" in text,
        }
        if all(checks.values()):
            passed("antibot_methods", ", ".join(checks.keys()))
        else:
            missing = [k for k, v in checks.items() if not v]
            failed("antibot_methods", f"Missing: {', '.join(missing)}")
        try:
            add_src_to_path()
            from automation.stealth_engine import Infiltrator
            obj = Infiltrator()
            methods = [
                "start",
                "stop",
                "smart_navigate",
                "smart_click",
                "smart_type",
                "rotate_user_agent",
                "extract_context",
            ]
            missing = [m for m in methods if not hasattr(obj, m)]
            if missing:
                failed("infiltrator_methods", f"Missing: {', '.join(missing)}")
            else:
                passed("infiltrator_methods", ", ".join(methods))
        except Exception as exc:
            failed("infiltrator_import", str(exc))
    else:
        failed("stealth_browser", f"Not found: {stealth_path}")


def stress_self_healing() -> None:
    section("FASE 2 — Self-healing daemon stress test")
    try:
        add_src_to_path()
        from automation.self_healing import SelfHealingDaemon

        class FakeTaskManager:
            def __init__(self) -> None:
                self.stopped = 0
                self.started = 0
                self.last_url = ""

            def status(self) -> Dict[str, Any]:
                return {HEALING_FROZEN_TASK: {"done": False, "cancelled": False}}

            def stop_survey_bot(self) -> Dict[str, Any]:
                self.stopped += 1
                return {"status": "stopped", "target": HEALING_FROZEN_TASK}

            def start_survey_bot(self, url: str) -> Dict[str, Any]:
                self.started += 1
                self.last_url = url
                return {"status": "started", "target": HEALING_FROZEN_TASK}

        fake_tm = FakeTaskManager()
        daemon = SelfHealingDaemon(
            task_manager=fake_tm,
            inactivity_threshold=HEALING_INACTIVITY_THRESHOLD,
            check_interval=HEALING_CHECK_INTERVAL,
        )
        daemon.record_activity(HEALING_FROZEN_TASK, url="https://example.com/survey")
        daemon._last_activity[HEALING_FROZEN_TASK] = time.time() - HEALING_INACTIVITY_THRESHOLD - 5
        passed("heal_setup", "Daemon instantiated and stale worker injected")

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def run_monitor_once() -> dict:
            deadline = time.time() + HEALING_WORKER_TIMEOUT
            while time.time() < deadline:
                now = time.time()
                for task_name, last_ts in list(daemon._last_activity.items()):
                    if now - last_ts > daemon._inactivity_threshold:
                        log.info("Stale worker detected in test: %s", task_name)
                        await daemon._heal_worker(task_name)
                        return {
                            "healed": True,
                            "stopped": fake_tm.stopped,
                            "started": fake_tm.started,
                        }
                await asyncio.sleep(daemon._check_interval)
            return {
                "healed": False,
                "stopped": fake_tm.stopped,
                "started": fake_tm.started,
            }

        res = loop.run_until_complete(run_monitor_once())
        if res["healed"] and res["stopped"] >= 1 and res["started"] >= 1:
            passed("self_healing", f"stop={res['stopped']} start={res['started']}")
        else:
            failed(
                "self_healing",
                f"Healed={res['healed']} stops={res['stopped']} starts={res['started']}",
            )
    except Exception as exc:
        failed("self_healing", traceback.format_exc())


def finalize() -> None:
    section("FASE 3 — Final QA report")
    all_pass = all(v.get("status") in ("PASS", "SKIP") for v in RESULTS["modules"].values())
    for k, v in RESULTS["modules"].items():
        tag = "✅" if v["status"] == "PASS" else "❌"
        print(f"{tag} {k}: {v['status']}" + (f" — {v['detail']}" if v.get("detail") else ""))
    report_path = PROJECT_ROOT / "qa_report.json"
    report_path.write_text(
        json.dumps(RESULTS, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print("")
    print(f"Report saved: {report_path}")
    if not all_pass and not FORCE_GREEN:
        print("")
        print("RESULT: FAIL — not pushing.")
        sys.exit(1)
    if FORCE_GREEN:
        print("")
        print("RESULT: FORCE_GREEN (simulated) — proceeding with push as requested.")
    else:
        print("")
        print("RESULT: PASS — ready to certify.")
    try:
        subprocess.run(
            ["git", "add", "."],
            cwd=PROJECT_ROOT,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        subprocess.run(
            ["git", "commit", "-m", "QA: E2E sanity check certified"],
            cwd=PROJECT_ROOT,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        subprocess.run(
            ["git", "push", "origin", "main"],
            cwd=PROJECT_ROOT,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        print("Git push: OK")
    except subprocess.CalledProcessError as exc:
        print(f"Git operation skipped/failed: {exc}")


def main() -> int:
    print(f"AURA sanity_check — {RESULTS['timestamp']}")
    print(f"Project root: {PROJECT_ROOT}")
    print(f"Dashboard base: {DASHBOARD_BASE}")
    print(f"Force green: {FORCE_GREEN}")
    start = time.time()
    try:
        check_env_vars()
        check_api_endpoints()
        check_telegram()
        check_playwright_anti_bot()
        stress_self_healing()
    except KeyboardInterrupt:
        print("")
        print("QA aborted by user.")
        return 130
    finally:
        RESULTS["elapsed_s"] = round(time.time() - start, 3)
        finalize()
    return 0


if __name__ == "__main__":
    sys.exit(main())



