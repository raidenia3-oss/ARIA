"""AURA System Daemon — Auto-sanación y telemetría persistente."""

import asyncio, gc, logging, os, subprocess as sp, threading, time
import psutil
import base64
from pathlib import Path

ADB_PATH = r"C:\Users\User\AppData\Local\Android\Sdk\platform-tools\adb.exe"
LOG = logging.getLogger("aura.system_daemon")

# Error screenshot buffer for Kimi K2.7 vision
ERROR_SCREENSHOT_DIR = Path(__file__).resolve().parent.parent / "web_vault" / "errors"
ERROR_SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


def capture_error_screenshot_sync(error_msg: str, source: str = "daemon") -> dict:
    """Capture ADB screenshot on error, save as Base64 for Kimi vision model."""
    try:
        r = sp.run(
            [ADB_PATH, "exec-out", "screencap", "-p"],
            capture_output=True,
            timeout=15,
        )
        if r.returncode == 0 and len(r.stdout) > 100:
            d = r.stdout.encode("latin-1") if isinstance(r.stdout, str) else r.stdout
            out_path = ERROR_SCREENSHOT_DIR / "latest_bug.png"
            out_path.write_bytes(d)
            b64 = base64.b64encode(d).decode()
            report = {
                "status": "CAPTURED",
                "source": source,
                "error_msg": error_msg,
                "screenshot_size": len(d),
                "ready_for_kimi_vision": True,
                "ts": time.time(),
            }
            (ERROR_SCREENSHOT_DIR / "latest_error.json").write_text(
                __import__("json").dumps(report, ensure_ascii=False)
            )
            return report
    except Exception as e:
        LOG.error(f"Screenshot capture failed: {e}")
    return {"status": "FAILED"}


CPU_THRESHOLD = 90.0
RAM_THRESHOLD = 90.0
CRITICAL_DURATION_S = 30
CLEANUP_INTERVAL_S = 15
TELEMETRY_INTERVAL_S = 5


class SystemDaemon:
    def __init__(self):
        self._running = threading.Event()
        self._thread = None
        self._broadcast_fn = None
        self._cpu_over_threshold_since = None
        self._ram_over_threshold_since = None
        self._cleanup_count = 0
        self._last_telemetry = {}
        self._stop_requested = False

    def set_broadcaster(self, fn):
        self._broadcast_fn = fn

    async def _loop(self):
        while self._running.is_set():
            try:
                cpu = psutil.cpu_percent(interval=1)
                mem = psutil.virtual_memory()
                disk = psutil.disk_usage("/").percent
                now = time.time()

                cpu_hot = cpu > CPU_THRESHOLD
                ram_hot = mem.percent > RAM_THRESHOLD

                if cpu_hot:
                    if self._cpu_over_threshold_since is None:
                        self._cpu_over_threshold_since = now
                    elif now - self._cpu_over_threshold_since > CRITICAL_DURATION_S:
                        await self._auto_cleanup("CPU", cpu, mem.percent)
                        self._cpu_over_threshold_since = None
                else:
                    self._cpu_over_threshold_since = None

                if ram_hot:
                    if self._ram_over_threshold_since is None:
                        self._ram_over_threshold_since = now
                    elif now - self._ram_over_threshold_since > CRITICAL_DURATION_S:
                        await self._auto_cleanup("RAM", cpu, mem.percent)
                        self._ram_over_threshold_since = None
                else:
                    self._ram_over_threshold_since = None

                try:
                    adb_alive = (
                        "device"
                        in sp.run(
                            [ADB_PATH, "devices"], capture_output=True, text=True, timeout=5
                        ).stdout
                    )
                except Exception:
                    adb_alive = False

                ports_status = {}
                for port, name in [(5000, "FastAPI"), (5555, "ADB"), (11434, "Ollama")]:
                    try:
                        s = psutil.net_connections(kind="inet")
                        listening = any(l.laddr.port == port for l in s if hasattr(l, "laddr"))
                        ports_status[name] = listening
                    except Exception:
                        ports_status[name] = False

                procs_of_interest = []
                patterns = ["emulator", "java", "adb", "python", "node", "gradle"]
                for p in psutil.process_iter(["pid", "name", "memory_percent", "cpu_percent"]):
                    try:
                        name_lower = p.info["name"].lower()
                        if any(pat in name_lower for pat in patterns):
                            procs_of_interest.append(
                                {
                                    "pid": p.info["pid"],
                                    "name": p.info["name"],
                                    "mem": round(p.info["memory_percent"], 2),
                                    "cpu": round(p.info["cpu_percent"], 2),
                                }
                            )
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass

                self._last_telemetry = {
                    "type": "system_daemon",
                    "cpu": cpu,
                    "ram": mem.percent,
                    "ram_used_gb": round(mem.used / 1e9, 2),
                    "ram_total_gb": round(mem.total / 1e9, 2),
                    "disk": disk,
                    "adb": adb_alive,
                    "ports": ports_status,
                    "processes": len(procs_of_interest),
                    "top_procs": sorted(procs_of_interest, key=lambda x: x["mem"], reverse=True)[
                        :5
                    ],
                    "cleanups": self._cleanup_count,
                    "ts": time.time(),
                }

                if self._broadcast_fn:
                    await self._broadcast_fn(self._last_telemetry)

            except Exception as e:
                LOG.error(f"SystemDaemon loop error: {e}")
            await asyncio.sleep(TELEMETRY_INTERVAL_S)

    async def _auto_cleanup(self, trigger, cpu, ram):
        self._cleanup_count += 1
        LOG.warning(
            f"[AUTO-CLEANUP #{self._cleanup_count}] Trigger: {trigger} (CPU={cpu}%, RAM={ram}%)"
        )
        gc.collect()
        for p in psutil.process_iter(["pid", "name", "memory_percent"]):
            try:
                name_lower = p.info["name"].lower()
                if "emulator" in name_lower and p.info["memory_percent"] > 5.0:
                    p.kill()
                    LOG.info(f"Killed heavy emulator process PID={p.info['pid']}")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        try:
            sp.run(
                [ADB_PATH, "shell", "am", "force-stop", "com.google.android.emulator"],
                capture_output=True,
                timeout=10,
            )
        except Exception:
            pass
        cleanup_report = {
            "type": "cleanup_event",
            "trigger": trigger,
            "cpu_at": cpu,
            "ram_at": ram,
            "cleanup_id": self._cleanup_count,
            "ts": time.time(),
        }
        if self._broadcast_fn:
            await self._broadcast_fn(cleanup_report)

    def get_telemetry(self):
        return self._last_telemetry.copy()

    def start(self):
        if not self._running.is_set():
            self._running.set()
            self._stop_requested = False
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._thread = threading.Thread(
                target=lambda: loop.run_until_complete(self._loop()), daemon=True
            )
            self._thread.start()
            LOG.info("SystemDaemon started")

    def stop(self):
        self._stop_requested = True
        self._running.clear()
        LOG.info("SystemDaemon stopped")


_system_daemon = SystemDaemon()
