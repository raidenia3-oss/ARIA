#!/usr/bin/env python3
"""AURA Rollercoin FastAPI — Orquestación autónoma. Daemons: telemetry, clipboard, rollercoin."""

import sys, json, threading, socket, os, signal, time, random, subprocess as sp
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

BASE = Path(__file__).resolve().parent.parent
load_dotenv(BASE / ".env")

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
from automation.rollercoin_bot import _engine, state

ADB = r"C:\Users\User\AppData\Local\Android\Sdk\platform-tools\adb.exe"
app = FastAPI(title="AURA Orchestrator", version="3.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ─── DAEMONS ───────────────────────────────────────────────────
class TelemetryDaemon:
    def __init__(self):
        self._running = False
        self._th = None

    def _loop(self):
        import psutil

        while self._running:
            try:
                cpu = psutil.cpu_percent(interval=1)
                mem = psutil.virtual_memory()
                p = {}
                for pat in ["emulator", "java", "adb", "node", "python"]:
                    for proc in psutil.process_iter(
                        ["pid", "name", "memory_percent", "cpu_percent"]
                    ):
                        try:
                            if pat in proc.info["name"].lower():
                                p[proc.info["pid"]] = {
                                    "name": proc.info["name"],
                                    "ram": proc.info["memory_percent"],
                                    "cpu": proc.info["cpu_percent"],
                                }
                        except:
                            pass
                ports = {}
                for pn, nm in [(5000, "FastAPI"), (5555, "ADB"), (11434, "Ollama")]:
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.settimeout(1)
                    ports[nm] = s.connect_ex(("127.0.0.1", pn)) == 0
                    s.close()
                adb = (
                    "device"
                    in sp.run([ADB, "devices"], capture_output=True, text=True, timeout=5).stdout
                )
                base = {
                    "cpu": cpu,
                    "ram": mem.percent,
                    "adb": adb,
                    "ports": ports,
                    "ts": datetime.now().isoformat(),
                }
                (
                    Path(__file__).resolve().parent.parent / "core" / "telemetry_state.json"
                ).write_text(json.dumps(base, indent=2))
            except:
                pass
            time.sleep(5)

    def start(self):
        if not self._running:
            self._running = True
            self._th = threading.Thread(target=self._loop, daemon=True)
            self._th.start()

    def stop(self):
        self._running = False


class ClipboardDaemon:
    def __init__(self):
        self._running = False
        self._th = None
        self._last = ""

    def _loop(self):
        while self._running:
            try:
                r = sp.run(
                    [ADB, "shell", "service", "call", "clipboard", "1"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if r.stdout and r.stdout != self._last:
                    self._last = r.stdout
            except:
                pass
            time.sleep(2)

    def start(self):
        if not self._running:
            self._running = True
            self._th = threading.Thread(target=self._loop, daemon=True)
            self._th.start()

    def stop(self):
        self._running = False


_td = TelemetryDaemon()
_cd = ClipboardDaemon()
_td.start()
_cd.start()


# ─── ROLLERCOIN ENDPOINTS ──────────────────────────────────────
@app.post("/api/v1/rollercoin/start")
async def r_start(bt: BackgroundTasks):
    if _engine.state.get("running"):
        return {"status": "ALREADY_RUNNING"}
    bt.add_task(lambda: _engine.start())
    return {"status": "STARTING", "engine": "RollercoinEngine", "adb_auto_start": True, "cv2": True}


@app.post("/api/v1/rollercoin/stop")
async def r_stop():
    _engine.stop()
    return {"status": "STOPPED"}


@app.get("/api/v1/rollercoin/status")
async def r_status():
    s = _engine.status
    try:
        adb = "device" in sp.run([ADB, "devices"], capture_output=True, text=True, timeout=5).stdout
    except:
        adb = False
    s["adb"] = adb
    return JSONResponse(content=s)


@app.get("/api/v1/rollercoin/dashboard")
async def r_dash():
    s = _engine.status
    try:
        adb = "device" in sp.run([ADB, "devices"], capture_output=True, text=True, timeout=5).stdout
    except:
        adb = False
    return {
        "status": s.get("status", "IDLE"),
        "games_played": s.get("games_played", 0),
        "games_won": s.get("games_won", 0),
        "total_power": s.get("total_power", 0),
        "last_game": s.get("last_game"),
        "last_reward": s.get("last_reward"),
        "running": s.get("running", False),
        "adb_connected": adb,
        "cooldown_until": s.get("cooldown_until"),
        "errors": s.get("errors", 0),
    }


@app.get("/health")
async def h():
    return {
        "ok": True,
        "service": "aura-orchestrator",
        "daemons": {
            "telemetry": "active",
            "clipboard": "active",
            "rollercoin": _engine.state.get("status", "IDLE"),
        },
    }


if __name__ == "__main__":
    print("AURA Orchestrator v3.0 — http://127.0.0.1:5000")
    uvicorn.run(app, host="0.0.0.0", port=5000)
