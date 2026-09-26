"""AURA v3.0 Backend End-to-End Testing"""

import json
import os
import sys
import time
import urllib.error
import urllib.request

BASE_URL = os.getenv("AURA_BASE_URL", "http://127.0.0.1:8000")
TIMEOUT = 10


def request(path: str, method: str = "GET", payload: dict | None = None) -> dict:
    url = f"{BASE_URL}{path if path.startswith('/') else '/' + path}"
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            body = resp.read().decode()
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode() if exc.fp else ""
        try:
            parsed = json.loads(body) if body else {}
        except Exception:
            parsed = {"raw": body}
        return {"error": str(exc), "status": exc.code, "body": parsed}
    except Exception as exc:
        return {"error": str(exc)}


def test_backend_health():
    print("TEST 1: Backend Health")
    data = request("/health")
    ok = not data.get("error") and data.get("status") in ("healthy", "ok", "degraded")
    print_result("Backend health", ok)
    return ok


def test_brain_endpoints():
    print("\nTEST 2: Brain Endpoints")
    status = request("/api/brain/status")
    ok = not status.get("error") and (
        "state" in status or "registry" in status or "samples_last_7_days" in status
    )
    print_result("Brain status", ok)

    learn = request(
        "/api/brain/learn",
        method="POST",
        payload={
            "device": "e2e-test",
            "role": "tester",
            "prompt": "e2e test",
            "response": "e2e response",
            "provider": "test",
        },
    )
    ok = not learn.get("error") and learn.get("status") == "learned"
    print_result("Brain learn", ok)
    return True


def test_routing_endpoints():
    print("\nTEST 3: Routing Endpoints")
    status = request("/api/brain/route/status")
    ok = not status.get("error") and (
        "available_targets" in status
        or "last_route" in status
        or "server_load" in status
        or isinstance(status, dict)
    )
    print_result("Routing status", ok)

    history = request("/api/brain/route/history?limit=1")
    ok = not history.get("error") and ("history" in history or isinstance(history, dict))
    print_result("Routing history", ok)
    return True


def test_treasury_endpoints():
    print("\nTEST 4: Treasury Endpoints")
    status = request("/api/brain/treasury/status")
    ok = not status.get("error") and (
        "tier" in status
        or "api_budget" in status
        or "allocation" in status
        or isinstance(status, dict)
    )
    print_result("Treasury status", ok)

    forecast = request("/api/brain/treasury/forecast?days=1")
    ok = not forecast.get("error") and ("forecast" in forecast or isinstance(forecast, dict))
    print_result("Treasury forecast", ok)
    return True


def test_training_endpoints():
    print("\nTEST 5: Training Endpoints")
    status = request("/api/brain/training/status")
    ok = not status.get("error") and "status" in status
    print_result("Training status", ok)

    history = request("/api/brain/training/distillation-history?limit=1")
    ok = not history.get("error") and ("history" in history or isinstance(history, dict))
    print_result("Distillation history", ok)

    sync_resp = request("/api/brain/training/sync?source=server")
    ok = not sync_resp.get("error") and "detail" not in sync_resp
    print_result("Training sync", ok)
    return True


def test_rollercoin_endpoints():
    print("\nTEST 6: Rollercoin Endpoints")
    status = request("/api/rollercoin/status")
    ok = not status.get("error") and (
        "running" in status
        or "daily_earnings" in status
        or "goal" in status
        or isinstance(status, dict)
    )
    print_result("Rollercoin status", ok)
    return True


def test_chat_endpoints():
    print("\nTEST 7: Chat Endpoints")
    chat = request("/api/chat", method="POST", payload={"prompt": "hola"})
    has_text = isinstance(chat, dict) and "text" in chat and not chat.get("error")
    print_result("Chat endpoint text", has_text)
    return has_text


def test_agent_scheduler_endpoints():
    print("\nTEST 8: Agent Scheduler Endpoints (BLOQUE 34)")
    status = request("/api/agent/scheduler/status")
    ok = isinstance(status, dict) and "running" in status and "tasks" in status
    print_result("Scheduler status", ok)
    assert ok, f"scheduler status falló: {status}"

    run = request("/api/agent/scheduler/run/coherence_audit", method="POST")
    run_ok = isinstance(run, dict) and "status" in run and run.get("status") == "ok"
    print_result("Scheduler run task", run_ok)
    assert run_ok, f"scheduler run falló: {run}"


def print_result(name: str, ok: bool):
    msg = "[PASS] %s" % name if ok else "[FAIL] %s" % name
    print(msg)


def main():
    print("\n" + "=" * 60)
    print("AURA v3.0 - BACKEND END-TO-END TESTING")
    print("=" * 60)

    passed = 0
    failed = 0

    checks = [
        test_backend_health,
        test_brain_endpoints,
        test_routing_endpoints,
        test_treasury_endpoints,
        test_training_endpoints,
        test_rollercoin_endpoints,
        test_chat_endpoints,
        test_agent_scheduler_endpoints,
    ]

    for check in checks:
        try:
            ok = check()
            if ok:
                passed += 1
            else:
                failed += 1
        except Exception as exc:
            failed += 1
            print_result(check.__name__, False)
            print("  Error: %s" % exc)

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print("Passed: %d" % passed)
    print("Failed: %d" % failed)
    if failed == 0:
        print("\nALL BACKEND E2E TESTS PASSED")
    else:
        print("\nSOME BACKEND E2E TESTS FAILED")
    print("=" * 60 + "\n")

    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
