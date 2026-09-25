"""ARIA Safety Filter — blocks dangerous OS commands executed by AI."""

from __future__ import annotations

import re
from typing import List, Dict, Optional, Tuple


BLOCKED_PATTERNS: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"\bformat\s+b:", re.IGNORECASE), "Formatear disco prohibido"),
    (re.compile(r"\bformat\s+/", re.IGNORECASE), "Formatear disco prohibido"),
    (re.compile(r"\bdel\s+/f\s+/s", re.IGNORECASE), "Eliminación recursiva prohibida"),
    (re.compile(r"\brm\s+-rf\b", re.IGNORECASE), "rm -rf prohibido"),
    (re.compile(r"\bdelete\s+.*\b(C:\|D:\|E:\|F:\|G:\|H:\|Windows|System32|SysWOW64)", re.IGNORECASE), "Eliminación de sistema protegida"),
    (re.compile(r"\bformat\b.*\b(all|quick|fs=)", re.IGNORECASE), "Formateo de disco prohibido"),
    (re.compile(r"\bchkdsk\b", re.IGNORECASE), "chkdsk requiere confirmación"),
    (re.compile(r"\bdiskpart\b", re.IGNORECASE), "diskpart requiere confirmación"),
    (re.compile(r"\bshutdown\b", re.IGNORECASE), "Apagado requiere confirmación"),
    (re.compile(r"\breboot\b", re.IGNORECASE), "Reinicio requiere confirmación"),
    (re.compile(r"\bmsconfig\b", re.IGNORECASE), "Configuración del sistema protegida"),
    (re.compile(r"\bregedit\b", re.IGNORECASE), "Registro de Windows protegido"),
    (re.compile(r"\bgpedit\b", re.IGNORECASE), "Política de grupo protegida"),
    (re.compile(r"\b services\.msc\b", re.IGNORECASE), "Servicios del sistema protegidos"),
    (re.compile(r"\btaskkill\s+/f\b", re.IGNORECASE), "Kill de proceso requiere confirmación"),
    (re.compile(r"\bicacls\b", re.IGNORECASE), "Permisos del sistema protegidos"),
    (re.compile(r"\bcacls\b", re.IGNORECASE), "Permisos del sistema protegidos"),
    (re.compile(r"\bnet\s+user\b", re.IGNORECASE), "Gestión de usuarios protegida"),
    (re.compile(r"\bnet\s+localgroup\b", re.IGNORECASE), "Gestión de grupos protegida"),
    (re.compile(r"\bpowercfg\b", re.IGNORECASE), "Configuración de energía protegida"),
    (re.compile(r"\bdefrag\b", re.IGNORECASE), "Desfragmentación requiere confirmación"),
    (re.compile(r"\bcipher\b", re.IGNORECASE), "Cipher requiere confirmación"),
    (re.compile(r"\bcertutil\b", re.IGNORECASE), "Certutil requiere confirmación"),
    (re.compile(r"\bwbadmin\b", re.IGNORECASE), "Backup requiere confirmación"),
    (re.compile(r"\brobocopy\b", re.IGNORECASE), "Robocopy requiere confirmación"),
    (re.compile(r"\bxcopy\s+/", re.IGNORECASE), "xcopy con flags requiere confirmación"),
    (re.compile(r"\bcopy\s+.*\/Y", re.IGNORECASE), "Copy sin confirmación requiere confirmación"),
]

SUGGESTED_ACTIONS: Dict[str, List[str]] = {
    "delete": ["Usa skill:files.write con contenido vacío para 'limpiar' un archivo", "Especifica exactamente qué archivo eliminar"],
    "format": ["Especifica la partición exacta", "Confirma que tienes backup de los datos"],
    "shutdown": ["Usa shutdown /s /t 60 para programar reinicio en 60s", "Especifica el motivo del reinicio"],
    "kill": ["Especifica el PID exacto del proceso", "Confirma que el proceso no es crítico"],
    "net": ["Confirma que tienes permisos de administrador", "Especifica exactamente qué usuario o grupo"],
}


class SafetyViolation:
    def __init__(self, command: str, reason: str, suggestions: List[str] = None):
        self.command = command
        self.reason = reason
        self.suggestions = suggestions or []

    def to_dict(self) -> Dict[str, str]:
        return {
            "command": self.command,
            "reason": self.reason,
            "suggestions": self.suggestions,
            "blocked": True,
        }


def safety_check(command: str) -> Optional[SafetyViolation]:
    """Checks a shell/system command against the safety blocklist.

    Returns None if safe, or SafetyViolation if blocked.
    """
    for pattern, reason in BLOCKED_PATTERNS:
        if pattern.search(command):
            suggestion_key = reason.lower().split(" ")[0]
            suggestions = SUGGESTED_ACTIONS.get(suggestion_key, ["Confirma que entiendes las consecuencias"])
            return SafetyViolation(command=command, reason=reason, suggestions=suggestions)
    return None


def safety_check_with_feedback(command: str) -> Dict[str, str]:
    """Returns a dict always, with 'safe' or 'blocked' status."""
    violation = safety_check(command)
    if violation:
        return violation.to_dict()
    return {"safe": True, "command": command}


def get_blocked_patterns_count() -> int:
    return len(BLOCKED_PATTERNS)
