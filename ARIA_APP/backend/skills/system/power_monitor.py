from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .power import run as power_run
from .wol import run as wol_run

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "power_monitor"
CONFIG_FILE = DATA_DIR / "config.json"
POLL_INTERVAL = 5  # segundos


class PowerMonitor:
    """Monitorea el estado de energia (AC/bateria) y dispara WoL al conectar cargador.

    Cuando se detecta una transicion a energia AC (enchufado), envia paquetes
    magic WoL a los MAC configurados para encender otras PCs de la red.

    Nota: la PC que ejecuta ARIA no puede auto-encenderse al enchufar el cargador;
    eso depende del BIOS/UEFI (opcion 'Wake on AC' / 'Restore on AC Power Loss').
    ARIA solo detecta el estado y puede encender OTROS equipos via WoL.
    """

    def __init__(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._poll_interval = POLL_INTERVAL
        self._targets: List[str] = []  # lista de MAC
        self._last_state: Optional[Dict[str, Any]] = None
        self._events: List[Dict[str, Any]] = []
        self._max_events = 100
        self._load_config()

    # ── Config / targets ──────────────────────────────────────────────────

    def _load_config(self) -> None:
        try:
            if CONFIG_FILE.exists():
                data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
                self._targets = list(data.get("wol_targets", []))
                self._poll_interval = int(data.get("poll_interval", POLL_INTERVAL))
        except Exception:
            self._targets = []
            self._poll_interval = POLL_INTERVAL

    def _save_config(self) -> None:
        try:
            CONFIG_FILE.write_text(
                json.dumps(
                    {
                        "wol_targets": self._targets,
                        "poll_interval": self._poll_interval,
                    },
                    indent=2,
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
        except Exception:
            pass

    def add_target(self, mac: str) -> Dict[str, Any]:
        import re
        mac_clean = mac.strip().replace(":", "").replace("-", "").replace(".", "")
        if not re.fullmatch(r"[0-9a-fA-F]{12}", mac_clean):
            return {"ok": False, "error": f"MAC invalida: {mac!r}"}
        mac_norm = ":".join(mac_clean[i:i + 2] for i in range(0, 12, 2)).upper()
        if mac_norm in self._targets:
            return {"ok": False, "error": f"YA configurado: {mac_norm}"}
        self._targets.append(mac_norm)
        self._save_config()
        return {"ok": True, "added": mac_norm, "targets": list(self._targets)}

    def remove_target(self, mac: str) -> Dict[str, Any]:
        import re
        mac_clean = mac.strip().replace(":", "").replace("-", "").replace(".", "")
        if not re.fullmatch(r"[0-9a-fA-F]{12}", mac_clean):
            return {"ok": False, "error": f"MAC invalida: {mac!r}"}
        mac_norm = ":".join(mac_clean[i:i + 2] for i in range(0, 12, 2)).upper()
        if mac_norm not in self._targets:
            return {"ok": False, "error": f"no configurado: {mac_norm}"}
        self._targets.remove(mac_norm)
        self._save_config()
        return {"ok": True, "removed": mac_norm, "targets": list(self._targets)}

    def list_targets(self) -> Dict[str, Any]:
        return {"ok": True, "targets": list(self._targets), "count": len(self._targets)}

    # ── Monitor loop ──────────────────────────────────────────────────────

    def _poll_once(self) -> Dict[str, Any]:
        return power_run({"action": "status"})

    def _record_event(self, event: Dict[str, Any]) -> None:
        event["at"] = datetime.now().isoformat()
        with self._lock:
            self._events.append(event)
            if len(self._events) > self._max_events:
                self._events = self._events[-self._max_events:]

    def _loop(self) -> None:
        while self._running:
            try:
                state = self._poll_once()
                with self._lock:
                    prev = self._last_state
                    self._last_state = state
                if prev is None:
                    continue
                prev_on_ac = bool(prev.get("on_ac"))
                curr_on_ac = bool(state.get("on_ac"))
                if not prev_on_ac and curr_on_ac:
                    # transicion: se conecto el cargador (AC)
                    self._on_ac_connect(state)
                elif prev_on_ac and not curr_on_ac:
                    # transicion: se desconecto el cargador (bateria)
                    self._on_ac_disconnect(state)
            except Exception as exc:
                self._record_event({"type": "error", "error": str(exc)})
            time.sleep(self._poll_interval)

    def _on_ac_connect(self, state: Dict[str, Any]) -> None:
        self._record_event({
            "type": "ac_connect",
            "state": state,
            "message": "Cargador conectado (energia AC)",
        })
        # Enviar WoL a todos los targets configurados
        for mac in list(self._targets):
            try:
                res = wol_run({"mac": mac, "repeats": 5})
                self._record_event({
                    "type": "wol_send",
                    "mac": mac,
                    "result": res,
                })
            except Exception as exc:
                self._record_event({
                    "type": "wol_error",
                    "mac": mac,
                    "error": str(exc),
                })

    def _on_ac_disconnect(self, state: Dict[str, Any]) -> None:
        self._record_event({
            "type": "ac_disconnect",
            "state": state,
            "message": "Cargador desconectado (modo bateria)",
        })

    # ── Public API ────────────────────────────────────────────────────────

    def start(self) -> Dict[str, Any]:
        with self._lock:
            if self._running:
                return {"ok": True, "status": "already_running"}
            self._running = True
            self._thread = threading.Thread(target=self._loop, daemon=True, name="ARIAPowerMonitor")
            self._thread.start()
        return {"ok": True, "status": "started", "poll_interval": self._poll_interval,
                "wol_targets": len(self._targets)}

    def stop(self) -> Dict[str, Any]:
        with self._lock:
            self._running = False
            t = self._thread
        if t:
            t.join(timeout=3)
        return {"ok": True, "status": "stopped"}

    def status(self) -> Dict[str, Any]:
        with self._lock:
            running = self._running
            last = self._last_state
            events = list(self._events)[-10:]
        return {
            "ok": True,
            "running": running,
            "poll_interval": self._poll_interval,
            "wol_targets": list(self._targets),
            "target_count": len(self._targets),
            "last_state": last,
            "recent_events": events,
        }

    def set_poll_interval(self, seconds: int) -> Dict[str, Any]:
        if seconds < 1 or seconds > 3600:
            return {"ok": False, "error": "intervalo debe estar entre 1 y 3600 segundos"}
        with self._lock:
            self._poll_interval = seconds
        self._save_config()
        return {"ok": True, "poll_interval": seconds}


_monitor: PowerMonitor | None = None


def _get_monitor() -> PowerMonitor:
    global _monitor
    if _monitor is None:
        _monitor = PowerMonitor()
    return _monitor


def run(params: Dict[str, Any]) -> Dict[str, Any]:
    action = params.get("action", "")
    mgr = _get_monitor()
    if action == "start":
        return mgr.start()
    if action == "stop":
        return mgr.stop()
    if action == "status":
        return mgr.status()
    if action == "add_target":
        return mgr.add_target(params.get("mac", ""))
    if action == "remove_target":
        return mgr.remove_target(params.get("mac", ""))
    if action == "list_targets":
        return mgr.list_targets()
    if action == "set_poll_interval":
        return mgr.set_poll_interval(int(params.get("seconds", POLL_INTERVAL)))
    return {"error": f"accion desconocida: {action}"}
