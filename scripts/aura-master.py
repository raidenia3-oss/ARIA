#!/usr/bin/env python3
"""AURA Master Launcher & Orchestration CLI (Bloque 38).

Arranque unificado y concurrente de todo el ecosistema local AURA con un solo
comando, apagado limpio (graceful shutdown) y verificación de salud agregada.

Servicios orquestados:
- backend   : FastAPI (uvicorn) — incluye mDNS announcer, WebSocket Gateway y
              el Background Daemon (se inician con el ciclo de vida del app).
- discord   : bot de Discord en Ruby (services/discord-bot/bot.rb) [opcional].

Uso:
    python scripts/aura-master.py                 # todo
    python scripts/aura-master.py --no-discord    # solo backend
    python scripts/aura-master.py --check         # health-check y salir
    python scripts/aura-master.py --port 8000     # puerto del backend

Sin dependencias de terceros: solo stdlib (subprocess, socket, signal, urllib).
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_PORT_DEFAULT = int(os.getenv("AURA_PORT", "8000"))
JAN_URL_DEFAULT = os.getenv("JAN_API_BASE_URL", "http://localhost:1337")
HEALTH_TIMEOUT_SECS = 5
HEALTH_RETRIES = 30  # ~30s para que el backend levante

# Colores mínimos para la terminal (Windows-safe).
_OK, _WARN, _ERR, _INFO, _RST = "", "", "", "", ""
if sys.stdout.isatty():
    _OK, _WARN, _ERR, _INFO, _RST = "\033[92m", "\033[93m", "\033[91m", "\033[96m", "\033[0m"


def log(tag: str, msg: str) -> None:
    color = {"ok": _OK, "warn": _WARN, "err": _ERR}.get(tag, _INFO)
    print(f"{color}[AURA-Master]{_RST} {msg}", flush=True)


# --------------------------------------------------------------------------- #
# Puertos y health-checks
# --------------------------------------------------------------------------- #

def port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    """True si el puerto ya está ocupado en el host (intenta bind; si falla, está en uso)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((host, port))
            return False
        except OSError:
            return True


def check_port_free(port: int) -> None:
    """Verifica que el puerto del backend esté libre antes de arrancar."""
    if port_in_use(port):
        raise RuntimeError(
            f"puerto {port} ya está en uso; libérelo o use --port <n> "
            "(¿otra instancia de AURA corriendo?)"
        )


def http_get_json(url: str, timeout: float = HEALTH_TIMEOUT_SECS) -> Optional[Dict[str, Any]]:
    """GET JSON best-effort; None si el servicio no responde."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, socket.timeout, json.JSONDecodeError, OSError):
        return None


def check_backend(port: int) -> Dict[str, Any]:
    """Health-check del backend FastAPI (/health)."""
    data = http_get_json(f"http://127.0.0.1:{port}/health")
    ok = bool(data) and data.get("status") in ("healthy", "ok", "degraded")
    return {"service": "backend", "ok": ok, "detail": (data or {}).get("status", "no response")}


def check_jan() -> Dict[str, Any]:
    """Health-check del motor local Jan (OpenAI-compatible :1337). Best-effort."""
    data = http_get_json(f"{JAN_URL_DEFAULT.rstrip('/')}/v1/models")
    models = [m.get("id") for m in (data or {}).get("data", []) if isinstance(m, dict)]
    return {"service": "jan", "ok": bool(data), "detail": models[0] if models else "no response"}


def check_discord_bot(port: int = BACKEND_PORT_DEFAULT) -> Dict[str, Any]:
    """Health-check del bot Discord vía diagnostics del backend (best-effort)."""
    data = http_get_json(f"http://127.0.0.1:{port}/api/discord/diagnostics")
    return {
        "service": "discord",
        "ok": data is not None,
        "detail": (data or {}).get("status", "no response"),
    }


def aggregate_health(
    port: int, include_jan: bool = True, include_discord: bool = True
) -> Dict[str, Any]:
    """Health-Check Aggregator (func. 2): verifica backend, Jan y Discord."""
    results: List[Dict[str, Any]] = [check_backend(port)]
    if include_jan:
        results.append(check_jan())
    if include_discord:
        results.append(check_discord_bot(port))
    return {
        "overall": "ok" if all(r["ok"] for r in results) else "degraded",
        "checks": results,
    }


# --------------------------------------------------------------------------- #
# Construcción de comandos de cada servicio (func. 1)
# --------------------------------------------------------------------------- #

def backend_command(port: int, python_exe: Optional[str] = None) -> List[str]:
    """Comando del backend FastAPI (uvicorn)."""
    py = python_exe or sys.executable
    return [py, "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", str(port)]


def discord_command() -> Optional[List[str]]:
    """Comando del bot de Discord en Ruby (si ruby/bot.rb están disponibles)."""
    import shutil

    ruby = shutil.which("ruby")
    bot_rb = PROJECT_ROOT / "services" / "discord-bot" / "bot.rb"
    if not ruby or not bot_rb.exists():
        return None
    return [ruby, str(bot_rb)]


def build_services(port: int, include_discord: bool) -> Dict[str, List[str]]:
    """Mapa nombre → comando de los servicios a lanzar."""
    services: Dict[str, List[str]] = {"backend": backend_command(port)}
    if include_discord:
        cmd = discord_command()
        if cmd:
            services["discord"] = cmd
        else:
            log("warn", "Ruby/bot.rb no disponible; se omite el bot de Discord")
    return services


# --------------------------------------------------------------------------- #
# Graceful Shutdown Controller (func. 3)
# --------------------------------------------------------------------------- #

class ServiceSupervisor:
    """Lanza los servicios en paralelo y los apaga ordenadamente.

    - Registra handlers de SIGINT/SIGTERM para apagar sin huérfanos.
    - Termina (SIGTERM/terminate) y espera; si un hijo no muere, SIGKILL.
    - Detecta hijos muertos inesperadamente sin colgar la terminal.
    """

    def __init__(self) -> None:
        self.procs: Dict[str, subprocess.Popen] = {}
        self._stopping = False

    def start_all(self, services: Dict[str, List[str]]) -> None:
        env = os.environ.copy()
        env.setdefault("PYTHONUNBUFFERED", "1")
        for name, cmd in services.items():
            log("info", f"arrancando {name}: {' '.join(cmd)}")
            self.procs[name] = subprocess.Popen(cmd, cwd=str(PROJECT_ROOT), env=env)
        self._install_signal_handlers()

    def wait_ready(self, port: int, retries: int = HEALTH_RETRIES) -> bool:
        """Espera a que el backend responda /health."""
        for _ in range(retries):
            if self._stopping:
                return False
            check = check_backend(port)
            if check["ok"]:
                log("ok", f"backend listo en :{port} ({check.get('detail', '')})")
                return True
            time.sleep(1)
        log("err", f"backend no respondió tras {retries}s")
        return False

    def poll(self) -> List[str]:
        """Detecta hijos muertos inesperadamente (sin bloquear)."""
        dead: List[str] = []
        for name, proc in list(self.procs.items()):
            code = proc.poll()
            if code is not None and not self._stopping:
                log("err", f"servicio '{name}' terminó inesperadamente (code={code})")
                dead.append(name)
        return dead

    def wait(self) -> None:
        """Bloquea mientras los hijos vivan; sale en Ctrl+C o si todos mueren."""
        try:
            while not self._stopping:
                self.poll()
                if not self.procs:
                    break
                if all(p.poll() is not None for p in self.procs.values()):
                    break
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        self.shutdown()

    def shutdown(self) -> None:
        """Graceful shutdown: TERM → espera → KILL. Sin huérfanos."""
        if self._stopping and not self.procs:
            return
        self._stopping = True
        log("info", "apagado ordenado de servicios...")
        for name, proc in self.procs.items():
            if proc.poll() is None:
                log("info", f"terminando {name} (pid={proc.pid})")
                try:
                    proc.terminate()
                except OSError:
                    pass
        deadline = time.time() + 10
        for name, proc in self.procs.items():
            try:
                proc.wait(timeout=max(0.1, deadline - time.time()))
            except subprocess.TimeoutExpired:
                log("warn", f"{name} no terminó a tiempo; enviando SIGKILL")
                try:
                    proc.kill()
                    proc.wait(timeout=5)
                except (OSError, subprocess.TimeoutExpired):
                    pass
        self.procs.clear()
        log("ok", "todos los servicios apagados; recursos liberados")

    def _install_signal_handlers(self) -> None:
        def _handler(signum, frame):  # noqa: ANN001, ARG001
            log("warn", f"señal {signum} recibida (Ctrl+C): iniciando graceful shutdown")
            self._stopping = True

        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                signal.signal(sig, _handler)
            except (ValueError, OSError):
                pass  # entornos sin señales disponibles


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="aura-master",
        description="AURA Master Launcher — arranque unificado del ecosistema local",
    )
    parser.add_argument("--port", type=int, default=BACKEND_PORT_DEFAULT,
                        help="puerto del backend FastAPI (default 8000)")
    parser.add_argument("--no-discord", action="store_true",
                        help="no arrancar el bot de Discord (Ruby)")
    parser.add_argument("--check", action="store_true",
                        help="solo ejecutar el health-check aggregator y salir")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)

    if args.check:
        report = aggregate_health(args.port, include_discord=not args.no_discord)
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0 if report["overall"] == "ok" else 1

    try:
        check_port_free(args.port)
    except RuntimeError as exc:
        log("err", str(exc))
        return 2

    services = build_services(args.port, include_discord=not args.no_discord)
    supervisor = ServiceSupervisor()
    supervisor.start_all(services)

    if supervisor.wait_ready(args.port):
        report = aggregate_health(args.port, include_jan=True, include_discord=False)
        for check in report["checks"]:
            mark = "OK " if check["ok"] else "DEGRADED"
            log("warn" if not check["ok"] else "ok", f"[{mark}] {check['service']}: {check['detail']}")

    log("info", "AURA en marcha. Pulse Ctrl+C para apagar todo ordenadamente.")
    supervisor.wait()
    return 0


if __name__ == "__main__":
    sys.exit(main())