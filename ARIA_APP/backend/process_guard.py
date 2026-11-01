# -*- coding: utf-8 -*-
"""ARIA OS - Process Guard.

Politica unica de terminacion de procesos del proyecto.

Regla base (inviolable):

    ARIA solo puede terminar procesos que ella misma haya creado.

Todo lo demas se niega. Concretamente, ARIA nunca termina procesos que
pertenecen a la sesion del usuario: navegadores (Chrome, Edge, Firefox...),
exploradores de archivos, editores, terminales, clientes de correo, juegos, y
cualquier proceso con ventana visible abierta por el usuario.

Por que existe: el 2026-10-19 ARIA ejecuto `taskkill /F /IM chrome.exe` para
intentar leer la base de cookies del navegador y cerro las ~28 ventanas de
Chrome que el usuario tenia abiertas. Ese tipo de accion no se puede repetir
por descuido, asi que se estructuraliza: no basta con "no hay que hacerlo",
hay que que el codigo y el gate lo impidan.

Diseno:

- `HARD_PROTECTED`: procesos del sistema / shell grafico. Nunca se matan,
  ni siquiera si son hijos de ARIA.
- `USER_PROCESS_NAMES`: procesos tipicos de la sesion del usuario. Nunca se
  matan por nombre; solo si descienden de ARIA y no tienen ventana visible.
- La propiedad se decide por arbol de procesos (`ppid`), no por nombre: una
  ventana de Chrome abierta por ARIA (Playwright) es hija de ARIA y si se
  puede cerrar; el Chrome del usuario no lo es.
- Terminacion por nombre esta prohibida: `taskkill /IM` / `Stop-Process -Name`
 .matarian tambien procesos no vistos. Solo se acepta un PID explicito.
- Toda terminacion pasa por `safe_terminate()`, que deja rastro en el log.
"""

from __future__ import annotations

import logging
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set

logger = logging.getLogger("ARIA.ProcessGuard")

# ─── Politica ────────────────────────────────────────────────────────────────

#: Procesos criticos del sistema y del shell grafico. Nunca se terminan.
HARD_PROTECTED: Set[str] = {
    "system", "system idle process", "registry", "memory compression",
    "smss.exe", "csrss.exe", "wininit.exe", "winlogon.exe", "lsass.exe",
    "services.exe", "lsm.exe", "svchost.exe", "fontdrvhost.exe",
    "dwm.exe", "explorer.exe", "taskhostw.exe", "ctfmon.exe",
    "sihost.exe", "rdpclip.exe", "spoolsv.exe", "audiodrv.exe",
    "wudfhost.exe", "conhost.exe", "rundll32.exe", "lsm.exe",
    "securityhealthservice.exe", "wmiprvse.exe", "dllhost.exe",
}

#: Procesos tipicos de la sesion del usuario. Nunca se matan por nombre.
USER_PROCESS_NAMES: Set[str] = {
    # navegadores
    "chrome.exe", "msedge.exe", "firefox.exe", "brave.exe", "opera.exe",
    "opera_gx.exe", "vivaldi.exe", "browser.exe", "iexplore.exe",
    "msedgewebview2.exe", "chromium.exe", "thorium.exe", "librewolf.exe",
    "safari.exe", "waterfox.exe", "comodo_browser.exe", "coccoc.exe",
    # editores y terminales
    "code.exe", "cursor.exe", "windsurf.exe", "notepad.exe", "notepad++.exe",
    "devenv.exe", "pycharm64.exe", "idea64.exe", "webstorm64.exe",
    "windowsterminal.exe", "cmd.exe", "powershell.exe", "pwsh.exe",
    "conhost.exe", "alacritty.exe", "wezterm-gui.exe", "hyper.exe",
    # comunicacion y multimedia
    "whatsapp.exe", "telegram.exe", "discord.exe", "slack.exe", "teams.exe",
    "zoom.exe", "spotify.exe", "steam.exe", "obs64.exe", "vlc.exe",
    "photoshop.exe", "premiere.exe", "obsidian.exe", "figma.exe",
    # sistema/utilidades del usuario
    "explorer.exe", "onedrive.exe", "dropbox.exe", "google drive.exe",
    "keepassxc.exe", "bitwarden.exe", "1password.exe", "docker desktop.exe",
    "vmware.exe", "vmware-vmx.exe", "virtualbox.exe", "vboxheadless.exe",
    "mstsc.exe", "putty.exe", "winscp.exe", "notepad++.exe",
    "aria os.exe", "aura os.exe",
}

#: Procesos que ARIA gestiona como servicio propio y puede reiniciar.
ARIA_MANAGED: Set[str] = {
    "ollama.exe", "ollama_llama_server.exe", "ollama runner.exe",
}

#: Artefactos propios de ARIA (build outputs) que si pueden reiniciarse.
ARIA_ARTIFACT_NAMES: Set[str] = {
    "aria os.exe", "aura os.exe", "aria.exe", "aura.exe",
    "aria_native.exe", "electron.exe",
}

#: Carpetas de build cuyos binarios son propiedad de ARIA.
ARIA_ARTIFACT_DIRS = ("dist", "release", "build")

#: Raiz del proyecto (backend -> ARIA_APP -> proyecto).
PROJECT_ROOT = Path(__file__).resolve().parents[2]

#: Substrings que delatan terminacion masiva por nombre.
DANGEROUS_COMMAND_PATTERNS = (
    ("taskkill", "taskkill"),
    ("stop-process", "Stop-Process"),
    ("killall", "killall"),
    ("pkill", "pkill"),
    ("kill -9", "kill -9"),
    ("wmic process", "wmic process delete"),
    ("process.kill", "process.kill"),
    ("process.terminate", "process.terminate"),
    (".kill()", ".kill()"),
    ("terminate()", "terminate()"),
    ("tskill", "tskill"),
)

#: Comandos de shell que matan por nombre de imagen. Prohibidos siempre.
NAME_KILL_PATTERNS = (
    "taskkill",
    "killall",
    "pkill",
    "tskill",
)


@dataclass
class GuardVerdict:
    """Resultado de una consulta al guard."""
    allowed: bool
    reason: str
    code: str
    pid: Optional[int] = None
    name: Optional[str] = None
    owned: bool = False
    visible_window: bool = False
    window_title: Optional[str] = None
    detail: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "code": self.code,
            "pid": self.pid,
            "name": self.name,
            "owned": self.owned,
            "visible_window": self.visible_window,
            "window_title": self.window_title,
            "detail": self.detail,
        }


# ─── Deteccion de ventanas visibles (Windows) ────────────────────────────────


def _enum_windows() -> List[Dict[str, Any]]:
    """Devuelve las ventanas de primer nivel visibles con su PID y titulo."""
    if sys.platform != "win32":
        return []
    try:
        import ctypes
        from ctypes import wintypes
    except Exception:  # pragma: no cover - ctypes siempre existe en CPython
        return []

    try:
        user32 = ctypes.windll.user32
    except Exception:
        return []

    windows: List[Dict[str, Any]] = []
    proc_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def _callback(hwnd, _lparam):
        try:
            if not user32.IsWindowVisible(hwnd):
                return True
            length = user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(max(1, length + 1))
            user32.GetWindowTextW(hwnd, buf, len(buf))
            title = buf.value
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value:
                windows.append({
                    "hwnd": int(hwnd),
                    "pid": int(pid.value),
                    "title": title or "",
                })
        except Exception:
            pass
        return True

    try:
        user32.EnumWindows(proc_type(_callback), 0)
    except Exception:
        return windows
    return windows


class ProcessGuard:
    """Guardia de procesos de ARIA OS."""

    def __init__(self, root_pid: Optional[int] = None) -> None:
        self.root_pid = root_pid if root_pid is not None else os.getpid()
        self._registered: Dict[int, Dict[str, Any]] = {}
        self._window_cache: Dict[int, Dict[str, Any]] = {}
        self._window_cache_ts: float = 0.0
        self._window_cache_ttl: float = 2.0

    # ── Ventanas ──────────────────────────────────────────────────────────
    def _visible_windows(self, max_age: Optional[float] = None) -> Dict[int, Dict[str, Any]]:
        ttl = self._window_cache_ttl if max_age is None else max_age
        now = time.time()
        if self._window_cache and (now - self._window_cache_ts) < ttl:
            return self._window_cache
        index: Dict[int, Dict[str, Any]] = {}
        for win in _enum_windows():
            index[win["pid"]] = win
        self._window_cache = index
        self._window_cache_ts = now
        return index

    def window_for(self, pid: int) -> Optional[Dict[str, Any]]:
        return self._visible_windows().get(pid)

    def has_visible_window(self, pid: int) -> bool:
        return pid in self._visible_windows()

    # ── Propiedad ─────────────────────────────────────────────────────────
    def _proc(self, pid: int):
        try:
            import psutil
            return psutil.Process(pid)
        except Exception:
            return None

    def _exe_of(self, pid: int) -> str:
        proc = self._proc(pid)
        if proc is None:
            return ""
        try:
            return proc.exe() or ""
        except Exception:
            return ""

    def is_aria_artifact(self, pid: int) -> bool:
        """True si el proceso es un binario de ARIA (build output propio).

        Verificable por ruta: solo cuenta si el ejecutable vive dentro del
        proyecto (dist/, release/, build/ o nombre de artefacto conocido).
        """
        exe = self._exe_of(pid)
        if not exe:
            return False
        name = Path(exe).name.lower()
        if name in ARIA_ARTIFACT_NAMES:
            try:
                Path(exe).resolve().relative_to(PROJECT_ROOT)
                return True
            except (ValueError, OSError):
                return name in ARIA_ARTIFACT_NAMES and "aria" in name
        try:
            rel = Path(exe).resolve().relative_to(PROJECT_ROOT)
        except (ValueError, OSError):
            return False
        return rel.parts and rel.parts[0].lower() in ARIA_ARTIFACT_DIRS

    def is_aria_owned(self, pid: int) -> bool:
        """True si el proceso es hijo de ARIA (arbol de procesos) o fue registrado."""
        if pid in self._registered:
            return True
        if pid == self.root_pid:
            return True
        if self.is_aria_artifact(pid):
            return True
        proc = self._proc(pid)
        if proc is None:
            return False
        try:
            parent = proc.parent()
        except Exception:
            return False
        seen = set()
        while parent is not None:
            if parent.pid == self.root_pid:
                return True
            if parent.pid in seen:
                return False
            seen.add(parent.pid)
            try:
                parent = parent.parent()
            except Exception:
                return False
        return False

    def register_child(self, pid: int, name: str = "", reason: str = "") -> None:
        """Registra un proceso creado por ARIA como terminable."""
        self._registered[int(pid)] = {
            "pid": int(pid),
            "name": name,
            "reason": reason,
            "registered_at": time.time(),
        }
        logger.info(f"ProcessGuard: proceso ARIA registrado pid={pid} name={name}")

    def unregister_child(self, pid: int) -> None:
        self._registered.pop(int(pid), None)

    @property
    def registered(self) -> Dict[int, Dict[str, Any]]:
        return dict(self._registered)

    # ── Politica ──────────────────────────────────────────────────────────
    @staticmethod
    def is_hard_protected(name: str) -> bool:
        return (name or "").strip().lower() in HARD_PROTECTED

    @staticmethod
    def is_user_process(name: str) -> bool:
        return (name or "").strip().lower() in USER_PROCESS_NAMES

    def check(self, pid: int) -> GuardVerdict:
        """Consulta si un PID puede ser terminado."""
        try:
            pid = int(pid)
        except (TypeError, ValueError):
            return GuardVerdict(False, "PID invalido", "invalid_pid")

        if pid <= 0:
            return GuardVerdict(False, "PID invalido", "invalid_pid", pid=pid)
        if pid == self.root_pid:
            return GuardVerdict(
                False, "No se puede terminar el propio proceso de ARIA", "self", pid=pid)

        if pid in self._registered:
            name = self._registered[pid].get("name") or self._name_of(pid) or ""
            if self.is_hard_protected(name):
                return GuardVerdict(
                    False, f"Proceso critico protegido: {name}", "hard_protected",
                    pid=pid, name=name, owned=True)
            return GuardVerdict(
                True, "Proceso creado por ARIA", "owned", pid=pid, name=name, owned=True)

        proc = self._proc(pid)
        if proc is None:
            return GuardVerdict(
                False, "El proceso no existe o no es accesible", "not_found", pid=pid)
        try:
            name = (proc.name() or "").strip()
        except Exception:
            name = ""

        if self.is_hard_protected(name):
            return GuardVerdict(
                False, f"Proceso critico del sistema protegido: {name}", "hard_protected",
                pid=pid, name=name)

        win = self.window_for(pid)
        visible = win is not None
        title = win.get("title") if win else None

        owned = self.is_aria_owned(pid)
        if not owned:
            if visible:
                return GuardVerdict(
                    False,
                    f"Proceso del usuario con ventana abierta: {name} ({title or 'sin titulo'}). "
                    "ARIA no cierra ventanas del usuario.",
                    "user_window", pid=pid, name=name, owned=False,
                    visible_window=True, window_title=title)
            if self.is_user_process(name):
                return GuardVerdict(
                    False,
                    f"Proceso de la sesion del usuario protegido: {name}",
                    "user_process", pid=pid, name=name)
            return GuardVerdict(
                False,
                f"Proceso no creado por ARIA: {name} (pid {pid}). "
                "ARIA solo termina procesos que ella misma lanzo.",
                "not_owned", pid=pid, name=name)

        # Es hijo de ARIA: se permite. Si tiene ventana visible es una ventana
        # que ARIA abrio (Playwright, visor de PDF, etc.), no una del usuario.
        return GuardVerdict(
            True, "Proceso hijo de ARIA", "owned", pid=pid, name=name, owned=True,
            visible_window=visible, window_title=title)

    def _name_of(self, pid: int) -> str:
        proc = self._proc(pid)
        if proc is None:
            return ""
        try:
            return (proc.name() or "").strip()
        except Exception:
            return ""

    # ── Terminacion ───────────────────────────────────────────────────────
    def safe_terminate(
        self,
        pid: int,
        reason: str = "",
        timeout: float = 5.0,
    ) -> Dict[str, Any]:
        """Termina un proceso solo si la politica lo permite."""
        verdict = self.check(pid)
        if not verdict.allowed:
            logger.warning(
                f"ProcessGuard: terminacion DENEGADA pid={pid} "
                f"({verdict.code}): {verdict.reason}")
            return {
                "status": "denied",
                "terminated": False,
                "reason": verdict.reason,
                "code": verdict.code,
                "pid": verdict.pid,
                "name": verdict.name,
            }

        proc = self._proc(int(pid))
        if proc is None:
            return {
                "status": "error", "terminated": False,
                "reason": "El proceso no existe o no es accesible",
                "code": "not_found", "pid": pid,
            }

        try:
            proc.terminate()
            gone, alive = psutil_wait(proc, timeout)
        except Exception as exc:
            logger.error(f"ProcessGuard: error al terminar pid={pid}: {exc}")
            return {
                "status": "error", "terminated": False,
                "reason": str(exc), "code": "terminate_failed", "pid": pid,
            }

        if alive:
            try:
                proc.kill()
            except Exception as exc:
                logger.error(f"ProcessGuard: kill forzado fallo pid={pid}: {exc}")

        self.unregister_child(int(pid))
        logger.info(
            f"ProcessGuard: proceso terminado pid={pid} name={verdict.name} "
            f"motivo={reason or 'sin motivo'}")
        return {
            "status": "ok",
            "terminated": True,
            "pid": int(pid),
            "name": verdict.name,
            "reason": reason or "sin motivo",
            "code": verdict.code,
        }

    def safe_terminate_by_name(self, name: str, reason: str = "") -> Dict[str, Any]:
        """Prohibido por diseno: matar por nombre afecta a procesos no vistos."""
        logger.warning(
            f"ProcessGuard: terminacion por nombre RECHAZada ({name}). "
            "Se requiere un PID explicito.")
        return {
            "status": "denied",
            "terminated": False,
            "code": "name_kill_forbidden",
            "reason": (
                "Terminar por nombre esta prohibido: puede afectar procesos que "
                "el usuario no ve. Usa el PID explicito del proceso objetivo."
            ),
            "name": name,
        }

    # ── Comandos de shell ────────────────────────────────────────────────
    def guard_command(self, command: str) -> Optional[Dict[str, Any]]:
        """Revisa un comando de shell. Devuelve None si es seguro."""
        if not command:
            return None
        low = command.lower()

        for token, label in DANGEROUS_COMMAND_PATTERNS:
            if token in low:
                targets = self._targets_from_command(command)
                if not targets:
                    return {
                        "allowed": False,
                        "code": "mass_kill_forbidden",
                        "reason": (
                            f"'{label}' sin objetivo explicito esta prohibido: "
                            "ARIA no puede terminar procesos en bloque."
                        ),
                        "command": command,
                    }
                for target in targets:
                    verdict = self.check(target)
                    if not verdict.allowed:
                        return {
                            "allowed": False,
                            "code": verdict.code,
                            "reason": (
                                f"'{label}' sobre pid {target} ({verdict.name}) denegado: "
                                f"{verdict.reason}"
                            ),
                            "command": command,
                            "pid": target,
                        }
                return {
                    "allowed": False,
                    "code": "use_process_guard",
                    "reason": (
                        f"'{label}' esta prohibido en ARIA. Usa el ProcessGuard "
                        "(skill process_terminate) con el PID explicito."
                    ),
                    "command": command,
                }
        return None

    def _targets_from_command(self, command: str) -> List[int]:
        """Extrae PIDs explicitos de un comando (solo /PID y Stop-Process -Id)."""
        import re
        pids: List[int] = []
        for match in re.finditer(r"/PID\s+(\d+)", command, re.IGNORECASE):
            pids.append(int(match.group(1)))
        for match in re.finditer(r"-Id\s+(\d+)", command, re.IGNORECASE):
            pids.append(int(match.group(1)))
        for match in re.finditer(r"\bkill\s+(-9\s+)?(\d+)", command, re.IGNORECASE):
            pids.append(int(match.group(2)))
        return pids

    # ── Reporte ──────────────────────────────────────────────────────────
    def snapshot(self, limit: int = 40) -> Dict[str, Any]:
        """Estado del guard + procesos protegidos visibles."""
        protected: List[Dict[str, Any]] = []
        try:
            import psutil
            for proc in psutil.process_iter(["pid", "name"]):
                try:
                    name = (proc.info.get("name") or "").strip()
                except Exception:
                    continue
                if self.is_hard_protected(name) or self.is_user_process(name):
                    win = self.window_for(proc.info["pid"])
                    protected.append({
                        "pid": proc.info["pid"],
                        "name": name,
                        "hard_protected": self.is_hard_protected(name),
                        "visible_window": win is not None,
                        "window_title": win.get("title") if win else None,
                        "owned": proc.info["pid"] in self._registered,
                    })
                    if len(protected) >= limit:
                        break
        except Exception as exc:
            logger.debug(f"ProcessGuard: no se pudo listar procesos: {exc}")

        return {
            "root_pid": self.root_pid,
            "registered_children": len(self._registered),
            "hard_protected_count": len(HARD_PROTECTED),
            "user_process_count": len(USER_PROCESS_NAMES),
            "aria_managed": sorted(ARIA_MANAGED),
            "protected_processes": protected,
            "policy": (
                "ARIA solo termina procesos que ella misma creo. "
                "Terminar por nombre esta prohibido."
            ),
        }

    def describe(self) -> Dict[str, Any]:
        return {
            "policy": (
                "ARIA solo puede terminar procesos que ella misma haya creado. "
                "Nunca cierra ventanas ni navegadores del usuario."
            ),
            "hard_protected": sorted(HARD_PROTECTED),
            "user_process_names": sorted(USER_PROCESS_NAMES),
            "aria_managed": sorted(ARIA_MANAGED),
            "name_kill_allowed": False,
        }


def psutil_wait(proc, timeout: float = 5.0):
    """Espera a que un proceso muera. Devuelve (gone, alive)."""
    try:
        import psutil
        gone, alive = psutil.wait_procs([proc], timeout=timeout)
        return bool(gone), bool(alive)
    except Exception:
        return True, False


_GUARD: Optional[ProcessGuard] = None


def get_guard() -> ProcessGuard:
    """Instancia unica del guard."""
    global _GUARD
    if _GUARD is None:
        _GUARD = ProcessGuard()
    return _GUARD
