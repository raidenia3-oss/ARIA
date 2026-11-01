#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ARIA OS - CLI del Process Guard.

Via sancionada para inspeccionar y terminar procesos. Todo lo que hace pasa
por `ARIA_APP/backend/process_guard.py`, asi que aplica la misma politica:

    ARIA solo termina procesos que ella misma haya creado.

Nunca uses `taskkill /IM` ni `Stop-Process -Name`: matarian procesos del
usuario que no se ven (el incidente del 2026-10-19 cerro ~28 ventanas de
Chrome del usuario).

Uso:
    python scripts/aria_process_guard.py status
    python scripts/aria_process_guard.py list [--name chrome] [--limit 20]
    python scripts/aria_process_guard.py check <pid>
    python scripts/aria_process_guard.py terminate <pid> --reason "motivo"
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARIA_APP = ROOT / "ARIA_APP"
sys.path.insert(0, str(ARIA_APP))

from backend.process_guard import get_guard  # noqa: E402


def _print(payload) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def cmd_status(_args) -> int:
    guard = get_guard()
    _print({"policy": guard.describe(), "snapshot": guard.snapshot()})
    return 0


def cmd_list(args) -> int:
    try:
        import psutil
    except Exception as exc:
        _print({"status": "error", "error": f"psutil no disponible: {exc}"})
        return 1

    guard = get_guard()
    name_filter = (args.name or "").lower()
    rows = []
    for proc in psutil.process_iter(["pid", "name", "exe"]):
        try:
            name = (proc.info.get("name") or "").strip()
            if name_filter and name_filter not in name.lower():
                continue
            verdict = guard.check(proc.info["pid"])
            rows.append({
                "pid": proc.info["pid"],
                "name": name,
                "terminable": verdict.allowed,
                "code": verdict.code,
                "reason": verdict.reason,
                "visible_window": verdict.visible_window,
                "window_title": verdict.window_title,
            })
        except Exception:
            continue
    _print({
        "status": "ok",
        "count": len(rows),
        "processes": rows[: args.limit],
        "note": "terminable=false significa que el guard lo prohibe.",
    })
    return 0


def cmd_check(args) -> int:
    guard = get_guard()
    verdict = guard.check(args.pid)
    _print(verdict.to_dict())
    return 0 if verdict.allowed else 2


def cmd_terminate(args) -> int:
    guard = get_guard()
    result = guard.safe_terminate(args.pid, reason=args.reason)
    _print(result)
    return 0 if result.get("terminated") else 2


def main() -> int:
    parser = argparse.ArgumentParser(
        description="CLI del Process Guard de ARIA OS")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="Politica y estado del guard").set_defaults(func=cmd_status)

    p_list = sub.add_parser("list", help="Lista procesos con su veredicto")
    p_list.add_argument("--name", default="", help="Filtro por nombre de imagen")
    p_list.add_argument("--limit", type=int, default=40)
    p_list.set_defaults(func=cmd_list)

    p_check = sub.add_parser("check", help="Consulta si un PID se puede terminar")
    p_check.add_argument("pid", type=int)
    p_check.set_defaults(func=cmd_check)

    p_term = sub.add_parser("terminate", help="Termina un PID si el guard lo permite")
    p_term.add_argument("pid", type=int)
    p_term.add_argument("--reason", default="")
    p_term.set_defaults(func=cmd_terminate)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
