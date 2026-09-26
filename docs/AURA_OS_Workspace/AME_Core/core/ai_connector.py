"""AURA AI Connector v2.0 — Kimi K2.7 cache-optimized.
Bloques inmutables para 80% cache hit discount."""
import hashlib, json, logging, subprocess as sp, time, base64
from pathlib import Path

LOG = logging.getLogger("aura.ai_connector")
ADB = r"C:\Users\User\AppData\Local\Android\Sdk\platform-tools\adb.exe"
ROOT = str(Path(__file__).resolve().parent.parent)

REPO_CTX = "REPO:AURA v4 core/main.py FastAPI:5000"
ADB_CTX = f"ADB:{ADB} exec-out screencap -p"
TOOLS_CTX = "TOOLS:system_stats rollercoin_start/stop adb_screenshot adb_tap webfactory_build wallpaper_process"

BLOCKS = [REPO_CTX, ADB_CTX, TOOLS_CTX]
BLOCK_HASH = hashlib.sha256("|".join(BLOCKS).encode()).hexdigest()[:16]

PROMPT = f"You are AURA tactical AI. JSON only. v{BLOCK_HASH}\n" + "|".join(BLOCKS)


def get_prompt(task=""):
    return PROMPT + (f"\nTASK:{task}" if task else "")


def mkmsg(role, content, tc=None):
    m = {"role": role, "content": content}
    if tc:
        m["tool_calls"] = [{"type": "function", "function": tc}]
    return m


def mkresp(tc_id, result):
    return {"role": "tool", "tool_call_id": tc_id, "content": json.dumps(result)}


async def execute_tool(name, args):
    if name == "system_stats":
        return _stats()
    if name == "adb_screenshot":
        return _screenshot(args.get("output", "web_vault/errors/latest_bug.png"))
    if name == "adb_tap":
        return _tap(args.get("x", 0), args.get("y", 0))
    return {"error": f"Unknown:{name}"}


def _stats():
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=0.5)
        mem = psutil.virtual_memory()
        try:
            adb = "device" in sp.run(
                [ADB, "devices"], capture_output=True, text=True, timeout=5
            ).stdout
        except Exception:
            adb = False
        return {"cpu": cpu, "ram": mem.percent, "disk": psutil.disk_usage("/").percent, "adb": adb}
    except Exception as e:
        return {"error": str(e)}


def _screenshot(p):
    try:
        Path(p).parent.mkdir(parents=True, exist_ok=True)
        r = sp.run([ADB, "exec-out", "screencap", "-p"], capture_output=True, timeout=15)
        if r.returncode == 0 and len(r.stdout) > 100:
            d = r.stdout.encode("latin-1") if isinstance(r.stdout, str) else r.stdout
            Path(p).write_bytes(d)
            return {"path": p, "size": len(d), "b64": base64.b64encode(d).decode()}
    except Exception as e:
        return {"error": str(e)}
    return {"error": "screenshot_failed"}


def _tap(x, y):
    try:
        sp.run([ADB, "shell", "input", "tap", str(x), str(y)], timeout=5)
        return {"ok": True, "x": x, "y": y}
    except Exception as e:
        return {"error": str(e)}


async def capture_error_screenshot(msg, src="daemon"):
    r = _screenshot("web_vault/errors/latest_bug.png")
    r["error_msg"] = msg
    r["source"] = src
    r["ts"] = time.time()
    err_path = Path(ROOT) / "web_vault/errors/latest_error.json"
    err_path.parent.mkdir(parents=True, exist_ok=True)
    err_path.write_text(json.dumps(r, ensure_ascii=False))
    return r
