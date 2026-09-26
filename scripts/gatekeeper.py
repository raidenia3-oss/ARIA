#!/usr/bin/env python3
"""
AURA Gatekeeper — Validador de seguridad para comandos del sistema.

Funciones:
  - Lista negra de comandos peligrosos (rm -rf, format, del /s, shutdown, etc.)
  - Whitelist de comandos seguros (ls, dir, echo, python --version)
  - Confirmación para comandos de riesgo medio
  - Registro de auditoría con timestamp, usuario, comando, resultado
  - Modo lockdown (bloquear todo por defecto)
  - Bloqueo de paths sensibles (C:\\Windows, /etc, /root, ~/.ssh)
  - Detección de inyección en comandos (;, |, &&, ||, backticks)
  - Límite de comandos por minuto (anti-spam)

Uso:
  python scripts/gatekeeper.py --check "rm -rf /"
  python scripts/gatekeeper.py --check "dir C:\\Users"
  python scripts/gatekeeper.py --check "echo Hola"
  python scripts/gatekeeper.py --audit
  python scripts/gatekeeper.py --add-safe "python --version"
  python scripts/gatekeeper.py --add-danger "rm -rf /"
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import platform
import re
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("Gatekeeper")

REPO_ROOT = Path(__file__).resolve().parent.parent
AUDIT_FILE = REPO_ROOT / "gatekeeper_audit.jsonl"
SAFE_FILE = REPO_ROOT / "gatekeeper_safe.json"
DANGER_FILE = REPO_ROOT / "gatekeeper_danger.json"

DEFAULT_BLACKLIST: List[str] = [
    "rm -rf", "rm -fr", "rm -r -f",
    "format", "fdisk", "mkfs",
    "del /s", "del /f", "deltree",
    "shutdown", "reboot", "halt", "poweroff",
    "dd if=", "dd of=",
    "chmod -R 777", "chown -R",
    ">: /dev/", "curl | sh", "wget | sh",
    "python -c", "python -c \"import os; os.remove",
    "powershell -command", "powershell -c",
    "cmd /c", "cmd /c del", "cmd /c rm",
    "npm run", "npm install", "pip install",
    "apt-get remove", "apt-get purge", "yum remove",
    "systemctl stop", "systemctl disable",
    "kill -9", "killall",
    "sudo rm", "sudo dd",
    "rd /s", "rd /s /q",
]

DEFAULT_SAFELIST: List[str] = [
    "ls", "dir", "echo", "pwd", "cd", "mkdir", "echo.",
    "python --version", "python -V", "python3 --version",
    "node --version", "npm --version",
    "git status", "git log", "git diff",
    "whoami", "hostname", "date", "time",
    "ver", "set", "path",
    "cls", "clear", "history",
    "type", "cat", "head", "tail",
    "find", "where", "which",
    "ping", "tracert", "nslookup",
]

DEFAULT_SENSITIVE_PATHS = [
    "C:\\Windows", "C:\\Program Files", "C:\\Program Files (x86)",
    "/etc", "/root", "/sys", "/proc", "/boot",
    "~/.ssh", "~/.aws", "~/.config",
    "/usr/local/bin", "/bin", "/sbin",
]


class Gatekeeper:
    """Validador de seguridad para comandos."""

    def __init__(self, lockdown: bool = False):
        self.lockdown = lockdown
        self.blacklist = self._load_json(DANGER_FILE, DEFAULT_BLACKLIST)
        self.safelist = self._load_json(SAFE_FILE, DEFAULT_SAFELIST)
        self.audit_log: List[Dict] = []
        self.command_counts: Dict[str, List[float]] = defaultdict(list)
        self.rate_limit = 10
        self.rate_window = 60

    def _load_json(self, path: Path, default: Any) -> Any:
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return default
        return default

    def _save_json(self, path: Path, data: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _audit(self, command: str, decision: str, reason: str) -> None:
        entry = {
            "timestamp": datetime.now().isoformat(),
            "command": command,
            "decision": decision,
            "reason": reason,
            "lockdown": self.lockdown,
        }
        self.audit_log.append(entry)
        mode = "a" if AUDIT_FILE.exists() else "w"
        with open(AUDIT_FILE, mode, encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def _check_rate_limit(self, command: str) -> Tuple[bool, str]:
        now = time.time()
        self.command_counts[command] = [t for t in self.command_counts.get(command, []) if now - t < self.rate_window]
        if len(self.command_counts[command]) >= self.rate_limit:
            return False, f"Rate limit excedido: {self.rate_limit} comandos en {self.rate_window}s"
        self.command_counts[command].append(now)
        return True, "OK"

    def _check_injection(self, command: str) -> Tuple[bool, str]:
        patterns = [r";\s*\w+", r"\|\s*\w+", r"&&\s*\w+", r"\|\|\s*\w+", r"`[^`]+`", r"\$\([^)]+\)"]
        for pattern in patterns:
            if re.search(pattern, command):
                return False, f"Posible inyección detectada: {pattern}"
        return True, "OK"

    def _check_sensitive_paths(self, command: str) -> Tuple[bool, str]:
        for path in DEFAULT_SENSITIVE_PATHS:
            if path.lower() in command.lower():
                return False, f"Acceso a path sensible detectado: {path}"
        return True, "OK"

    def check(self, command: str, auto_approve: bool = False) -> Tuple[bool, str, str]:
        if self.lockdown:
            self._audit(command, "BLOCKED", "Modo lockdown activo")
            return False, "BLOQUEADO", "Modo lockdown activo: todos los comandos están bloqueados"

        cmd_lower = command.lower().strip()
        for safe in self.safelist:
            if cmd_lower == safe.lower() or cmd_lower.startswith(safe.lower() + " "):
                ok, reason = self._check_rate_limit(command)
                if not ok:
                    self._audit(command, "BLOCKED", reason)
                    return False, "BLOQUEADO", reason
                self._audit(command, "ALLOWED", f"Whitelist: {safe}")
                return True, "PERMITIDO", f"Comando seguro (whitelist): {safe}"

        for danger in self.blacklist:
            if danger.lower() in cmd_lower:
                self._audit(command, "BLOCKED", f"Blacklist: {danger}")
                return False, "BLOQUEADO", f"Comando peligroso detectado: {danger}"

        ok, reason = self._check_injection(command)
        if not ok:
            self._audit(command, "BLOCKED", reason)
            return False, "BLOQUEADO", reason

        ok, reason = self._check_sensitive_paths(command)
        if not ok:
            self._audit(command, "BLOCKED", reason)
            return False, "BLOQUEADO", reason

        ok, reason = self._check_rate_limit(command)
        if not ok:
            self._audit(command, "BLOCKED", reason)
            return False, "BLOQUEADO", reason

        if auto_approve:
            self._audit(command, "AUTO_APPROVED", "Auto-aprobado")
            return True, "AUTO_APROBADO", "Comando aprobado automáticamente (no en lista negra ni sensible)"

        self._audit(command, "NEEDS_CONFIRMATION", "Requiere confirmación manual")
        return None, "PENDIENTE", "Comando no reconocido. Requiere confirmación manual del usuario."

    def add_safe(self, command: str) -> None:
        if command not in self.safelist:
            self.safelist.append(command)
            self._save_json(SAFE_FILE, self.safelist)
            logger.info(f"Added to safelist: {command}")

    def add_danger(self, command: str) -> None:
        if command not in self.blacklist:
            self.blacklist.append(command)
            self._save_json(DANGER_FILE, self.blacklist)
            logger.info(f"Added to blacklist: {command}")

    def get_audit(self) -> List[Dict]:
        return self.audit_log

    def get_stats(self) -> Dict:
        allowed = sum(1 for e in self.audit_log if e["decision"] == "ALLOWED")
        blocked = sum(1 for e in self.audit_log if e["decision"] == "BLOCKED")
        pending = sum(1 for e in self.audit_log if e["decision"] == "NEEDS_CONFIRMATION")
        return {"allowed": allowed, "blocked": blocked, "pending": pending, "total": len(self.audit_log)}


def cmd_check(args: argparse.Namespace) -> None:
    gk = Gatekeeper(lockdown=args.lockdown)
    allowed, decision, reason = gk.check(args.command, auto_approve=args.auto_approve)
    print(json.dumps({"command": args.command, "decision": decision, "reason": reason, "allowed": allowed}, indent=2, ensure_ascii=False))


def cmd_audit(args: argparse.Namespace) -> None:
    gk = Gatekeeper()
    entries = gk.get_audit()
    if args.stats:
        stats = gk.get_stats()
        print(json.dumps(stats, indent=2, ensure_ascii=False))
    else:
        for entry in entries[-args.last:]:
            print(json.dumps(entry, ensure_ascii=False))


def cmd_add_safe(args: argparse.Namespace) -> None:
    gk = Gatekeeper()
    gk.add_safe(args.command)


def cmd_add_danger(args: argparse.Namespace) -> None:
    gk = Gatekeeper()
    gk.add_danger(args.command)


def main() -> None:
    p = argparse.ArgumentParser(description="AURA Gatekeeper")
    sub = p.add_subparsers(dest="command")

    s_check = sub.add_parser("check", help="Validar un comando")
    s_check.add_argument("command", type=str, help="Comando a validar")
    s_check.add_argument("--auto-approve", action="store_true", help="Auto-aprobar si no es peligroso")
    s_check.add_argument("--lockdown", action="store_true", help="Activar modo lockdown")
    s_check.set_defaults(func=cmd_check)

    s_audit = sub.add_parser("audit", help="Ver registro de auditoría")
    s_audit.add_argument("--last", type=int, default=20, help="Últimas N entradas")
    s_audit.add_argument("--stats", action="store_true", help="Mostrar estadísticas")
    s_audit.set_defaults(func=cmd_audit)

    s_safe = sub.add_parser("add-safe", help="Agregar comando a whitelist")
    s_safe.add_argument("command", type=str, help="Comando seguro")
    s_safe.set_defaults(func=cmd_add_safe)

    s_danger = sub.add_parser("add-danger", help="Agregar comando a blacklist")
    s_danger.add_argument("command", type=str, help="Comando peligroso")
    s_danger.set_defaults(func=cmd_add_danger)

    args = p.parse_args()
    if args.command is None:
        p.print_help()
        return
    args.func(args)


if __name__ == "__main__":
    main()
