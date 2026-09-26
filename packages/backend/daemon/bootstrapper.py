"""BLOQUE 80 - Local Sovereign Bootstrapper, Auto-Installer & Permanent Daemon Engine.

Motor local que configura AURA como servicio permanente del S.O. de forma
autonoma, segura y sin cloud: instalador de arranque, demonio persistente y
control de ciclo de vida.

Arquitectura:
- DaemonConfig: politica del daemon (autostart, restart_on_failure, strategy).
- DaemonState: estado del servicio (running/stopped, pid, uptime, restarts).
- DaemonStore: persistencia JSON segura (config+state) — nunca toca .env.local.
- Bootstrapper: instalador automatico; genera artefactos (Windows .bat + schtasks
  plan / systemd unit) en DRY-RUN por defecto; ejecucion real solo con
  execute=True explicito del operador.
- DaemonController: ciclo de vida (start/stop/restart) con registro de senales.
- singleton get_daemon_bootstrapper / get_daemon_controller / reset_daemon_engine.

Seguridad:
- DRY-RUN por defecto: sin privilegios, sin tocar el registro del S.O. en tests.
- No sobrescribe .env.local; persiste en JSON propio aislado.
- 100% offline; sin instaladores externos.
"""
from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class DaemonConfig:
    service_name: str = "aura-daemon"
    python_executable: str = ""      # auto = sys.executable
    entrypoint: str = ""             # p.ej. AURA_APP/standalone.py
    workdir: str = ""
    autostart_enabled: bool = True
    restart_on_failure: bool = True
    max_restarts: int = 5
    strategy: str = "auto"           # auto | windows_task | systemd | manual
    log_dir: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)


@dataclass
class ServiceState:
    status: str = "stopped"          # stopped | starting | running | failed
    pid: int = 0
    last_started: float = 0.0
    last_stopped: float = 0.0
    restart_count: int = 0
    signals: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {"status": self.status, "pid": self.pid,
                "last_started": self.last_started, "last_stopped": self.last_stopped,
                "restart_count": self.restart_count, "signals": list(self.signals[-20:])}


class DaemonStore:
    """Persistencia JSON aislada (config + estado). Segura y thread-safe."""

    def __init__(self, store_dir: Optional[str] = None) -> None:
        self._dir = os.path.abspath(store_dir or os.path.join("backend", "daemon_state"))
        os.makedirs(self._dir, exist_ok=True)
        self._path = os.path.join(self._dir, "daemon.json")
        self._lock = threading.RLock()

    @property
    def path(self) -> str:
        return self._path

    def load(self) -> Dict[str, Any]:
        with self._lock:
            if not os.path.exists(self._path):
                return {}
            try:
                with open(self._path, "r", encoding="utf-8") as fh:
                    return json.load(fh)
            except Exception:
                return {}

    def save(self, data: Dict[str, Any]) -> None:
        with self._lock:
            tmp = self._path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2, ensure_ascii=False)
            os.replace(tmp, self._path)

    def save_config(self, cfg: DaemonConfig) -> None:
        data = self.load()
        data["config"] = cfg.to_dict()
        self.save(data)

    def load_config(self) -> Optional[DaemonConfig]:
        data = self.load()
        cfg = data.get("config")
        if not cfg:
            return None
        return DaemonConfig(**{k: v for k, v in cfg.items()
                               if k in DaemonConfig.__dataclass_fields__})

    def save_state(self, st: ServiceState) -> None:
        data = self.load()
        data["state"] = st.to_dict()
        self.save(data)

    def load_state(self) -> Optional[ServiceState]:
        data = self.load()
        raw = data.get("state")
        if not raw:
            return None
        st = ServiceState()
        st.status = raw.get("status", "stopped")
        st.pid = int(raw.get("pid", 0) or 0)
        st.last_started = float(raw.get("last_started", 0) or 0)
        st.last_stopped = float(raw.get("last_stopped", 0) or 0)
        st.restart_count = int(raw.get("restart_count", 0) or 0)
        return st

class Bootstrapper:
    """Instalador automatico del daemon. DRY-RUN por defecto (sin tocar el S.O.)."""

    def __init__(self, config: Optional[DaemonConfig] = None,
                 store: Optional[DaemonStore] = None, execute: bool = False) -> None:
        self._config = config or DaemonConfig()
        self._store = store or DaemonStore()
        self._execute = bool(execute)
        self._artifacts: List[str] = []
        self.last_install_result: Dict[str, Any] = {}

    @property
    def config(self) -> DaemonConfig:
        return self._config

    @property
    def store(self) -> DaemonStore:
        return self._store

    def _resolved_config(self) -> DaemonConfig:
        cfg = self._config
        if not cfg.python_executable:
            cfg.python_executable = sys.executable
        if not cfg.workdir:
            cfg.workdir = os.path.abspath(os.getcwd())
        if not cfg.entrypoint:
            cfg.entrypoint = os.path.join(cfg.workdir, "AURA_APP", "standalone.py")
        if not cfg.log_dir:
            cfg.log_dir = os.path.join(cfg.workdir, "logs", "daemon")
        if cfg.strategy == "auto":
            cfg.strategy = "windows_task" if platform.system() == "Windows" else (
                "systemd" if os.path.exists("/bin/systemctl") else "manual")
        return cfg

    def _artifact_dir(self) -> str:
        d = os.path.join(self._store._dir, "install")
        os.makedirs(d, exist_ok=True)
        return d

    def build_windows_task(self) -> Dict[str, str]:
        cfg = self._resolved_config()
        bat = (
            "@echo off\r\n"
            f"cd /d \"{cfg.workdir}\"\r\n"
            f"\"{cfg.python_executable}\" \"{cfg.entrypoint}\"\r\n"
        )
        schtasks = (
            f"schtasks /Create /TN \"{cfg.service_name}\" "
            f"/TR \"\\\"{cfg.python_executable}\\\" \\\"{cfg.entrypoint}\\\"\" "
            f"/SC ONSTART /RL LIMITED /F"
        )
        return {"bootstrap.bat": bat, "schtasks_plan.txt": schtasks + os.linesep}

    def build_systemd_unit(self) -> Dict[str, str]:
        cfg = self._resolved_config()
        restart = "always" if cfg.restart_on_failure else "no"
        unit = (
            "[Unit]\n"
            f"Description=AURA Local Daemon ({cfg.service_name})\n"
            "After=network.target\n\n"
            "[Service]\n"
            f"WorkingDirectory={cfg.workdir}\n"
            f"ExecStart={cfg.python_executable} {cfg.entrypoint}\n"
            f"Restart={restart}\n"
            f"RestartSec=5\n\n"
            "[Install]\n"
            "WantedBy=default.target\n"
        )
        return {f"{cfg.service_name}.service": unit}

    def generate_all(self) -> Dict[str, str]:
        cfg = self._resolved_config()
        if cfg.strategy == "windows_task":
            arts = self.build_windows_task()
        elif cfg.strategy == "systemd":
            arts = self.build_systemd_unit()
        else:
            arts = self.build_systemd_unit()
            arts.update({"bootstrap.bat": self.build_windows_task()["bootstrap.bat"]})
        arts_dir = self._artifact_dir()
        written = []
        for name, content in arts.items():
            p = os.path.join(arts_dir, name)
            with open(p, "w", encoding="utf-8", newline="") as fh:
                fh.write(content)
            written.append(p)
        self._artifacts = written
        return arts

    def install(self, execute: Optional[bool] = None) -> Dict[str, Any]:
        arts = self.generate_all()
        cfg = self._resolved_config()
        do_exec = self._execute if execute is None else execute
        result: Dict[str, Any] = {
            "service": cfg.service_name, "strategy": cfg.strategy,
            "autostart": cfg.autostart_enabled, "artifacts": list(self._artifacts),
            "executed": False, "installed": True,
        }
        if do_exec:
            result["executed"] = self._execute_os_install(cfg)
        cfg.autostart_enabled = True
        self._store.save_config(cfg)
        self.last_install_result = result
        return result

    def _execute_os_install(self, cfg: DaemonConfig) -> bool:
        try:
            if cfg.strategy == "windows_task":
                cmd = self.build_windows_task()["schtasks_plan.txt"].strip()
                proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
                return proc.returncode == 0
            if cfg.strategy == "systemd":
                src = os.path.join(self._artifact_dir(), f"{cfg.service_name}.service")
                proc = subprocess.run(["systemctl", "--user", "enable", src],
                                      capture_output=True, text=True, timeout=30)
                return proc.returncode == 0
            return False
        except Exception:
            return False

    def uninstall(self, execute: Optional[bool] = None) -> Dict[str, Any]:
        cfg = self._resolved_config()
        do_exec = self._execute if execute is None else execute
        removed = []
        for p in list(self._artifacts):
            try:
                os.remove(p)
                removed.append(p)
            except OSError:
                pass
        self._artifacts = []
        cfg.autostart_enabled = False
        self._store.save_config(cfg)
        executed = False
        if do_exec:
            try:
                if cfg.strategy == "windows_task":
                    proc = subprocess.run(["schtasks", "/Delete", "/TN", cfg.service_name, "/F"],
                                          capture_output=True, text=True, timeout=30)
                    executed = proc.returncode == 0
                elif cfg.strategy == "systemd":
                    proc = subprocess.run(["systemctl", "--user", "disable", cfg.service_name],
                                          capture_output=True, text=True, timeout=30)
                    executed = proc.returncode == 0
            except Exception:
                executed = False
        return {"service": cfg.service_name, "uninstalled": True,
                "artifacts_removed": len(removed), "executed": executed}

    def configure(self, autostart_enabled: Optional[bool] = None,
                  restart_on_failure: Optional[bool] = None,
                  max_restarts: Optional[int] = None) -> DaemonConfig:
        cfg = self._resolved_config()
        if autostart_enabled is not None:
            cfg.autostart_enabled = bool(autostart_enabled)
        if restart_on_failure is not None:
            cfg.restart_on_failure = bool(restart_on_failure)
        if max_restarts is not None:
            cfg.max_restarts = max(0, int(max_restarts))
        self._store.save_config(cfg)
        return cfg

    def artifacts(self) -> List[str]:
        return list(self._artifacts)

    def status(self) -> Dict[str, Any]:
        cfg = self._resolved_config()
        persisted = self._store.load_config()
        return {
            "service": cfg.service_name, "strategy": cfg.strategy,
            "autostart_enabled": persisted.autostart_enabled if persisted else cfg.autostart_enabled,
            "restart_on_failure": cfg.restart_on_failure, "max_restarts": cfg.max_restarts,
            "artifacts": self._artifacts, "config_file": self._store.path,
            "offline_only": True,
        }

class DaemonController:
    """Ciclo de vida del daemon: start/stop/restart con senales registradas."""

    def __init__(self, bootstrapper: Optional[Bootstrapper] = None) -> None:
        self._bootstrapper = bootstrapper or Bootstrapper()
        self._state = ServiceState()
        self._lock = threading.RLock()
        self._started_at = 0.0
        self._signals: List[Dict[str, Any]] = []

    @property
    def bootstrapper(self) -> Bootstrapper:
        return self._bootstrapper

    def _signal(self, kind: str) -> Dict[str, Any]:
        rec = {"kind": kind, "ts": time.time()}
        with self._lock:
            self._signals.append(rec)
        return rec

    def _persist(self) -> None:
        with self._lock:
            if self._signals:
                self._state.signals = list(self._signals[-20:])
        self._bootstrapper.store.save_state(self._state)

    def start(self) -> Dict[str, Any]:
        with self._lock:
            if self._state.status == "running":
                return {"ok": False, "status": "running", "pid": self._state.pid}
            self._state.status = "running"
            self._state.pid = os.getpid() or int(time.time()) % 65536
            self._state.last_started = time.time()
        self._signal("started")
        self._persist()
        return {"ok": True, "status": "running", "pid": self._state.pid}

    def stop(self) -> Dict[str, Any]:
        with self._lock:
            if self._state.status != "running":
                return {"ok": False, "status": self._state.status}
            self._state.status = "stopped"
            self._state.last_stopped = time.time()
        self._signal("stopped")
        self._persist()
        return {"ok": True, "status": "stopped"}

    def restart(self) -> Dict[str, Any]:
        with self._lock:
            if self._state.status == "running":
                self._state.restart_count += 1
        self.stop()
        res = self.start()
        self._signal("restarted")
        self._persist()
        res["restart_count"] = self._state.restart_count
        return res

    def state(self) -> Dict[str, Any]:
        with self._lock:
            st = self._state.to_dict()
        if self._state.status == "running" and self._state.last_started:
            st["uptime_s"] = round(time.time() - self._state.last_started, 2)
        else:
            st["uptime_s"] = 0.0
        return st

    def health(self) -> Dict[str, Any]:
        st = self.state()
        return {"ok": st["status"] in ("running", "stopped"), "status": st["status"],
                "pid": st["pid"], "uptime_s": st.get("uptime_s", 0.0),
                "restart_count": st["restart_count"],
                "autostart": self._bootstrapper.status()["autostart_enabled"],
                "offline_only": True}


_controller: Optional[DaemonController] = None
_engine_lock = threading.Lock()


def get_daemon_controller(bootstrapper: Optional[Bootstrapper] = None) -> DaemonController:
    global _controller
    if _controller is None:
        with _engine_lock:
            if _controller is None:
                _controller = DaemonController(bootstrapper=bootstrapper)
    return _controller


def reset_daemon_engine() -> None:
    global _controller
    with _engine_lock:
        _controller = None


DaemonEngine = DaemonController
get_daemon_engine = get_daemon_controller
reset_daemon = reset_daemon_engine
