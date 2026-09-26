"""
AURA_Core/tools/cli_agent_wrapper.py
Wrappers autónomos de CLI para ejecución silenciosa de agentes/bots sin UI.
Diseñado para auto-curación, mantenimiento y operaciones headless.
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("AURA_CLI_Wrapper")


@dataclass
class CLIResult:
    ok: bool
    returncode: int
    stdout: str
    stderr: str
    elapsed_s: float
    command: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _run_shell(
    command: str,
    *,
    cwd: Optional[str] = None,
    timeout: int = 600,
    shell: bool = True,
    check: bool = False,
) -> CLIResult:
    """
    Ejecuta un comando de shell de forma silenciosa y captura salida.
    No abre ventanas UI. Usa CREATE_NO_WINDOW en Windows cuando es posible.
    """
    creationflags = 0
    if sys.platform == "win32":
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)

    start = time.time()
    try:
        proc = subprocess.run(
            command,
            shell=shell,
            cwd=cwd,
            timeout=timeout,
            capture_output=True,
            text=True,
            creationflags=creationflags,
            check=False,
        )
        elapsed = round(time.time() - start, 3)
        return CLIResult(
            ok=proc.returncode == 0,
            returncode=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
            elapsed_s=elapsed,
            command=command,
        )
    except Exception as exc:
        elapsed = round(time.time() - start, 3)
        return CLIResult(
            ok=False,
            returncode=-1,
            stdout="",
            stderr=str(exc),
            elapsed_s=elapsed,
            command=command,
        )


class CLIAgentWrapper:
    """
    Interfaz de alto nivel para invocar bots/scripts de AURA de forma headless.
    Salida estructurada JSON-friendly para indexación por KnowledgeGraph.
    """

    def __init__(self, root: Optional[str] = None):
        self.root = Path(root or Path(__file__).resolve().parents[2])

    def run(
        self,
        name: str,
        command: str,
        *,
        cwd: Optional[str] = None,
        timeout: int = 600,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Ejecuta un comando y devuelve resultado indexable.
        """
        res = _run_shell(command, cwd=cwd or str(self.root), timeout=timeout)
        payload: Dict[str, Any] = {
            "agent": name,
            "command": command,
            "ok": res.ok,
            "returncode": res.returncode,
            "stdout": res.stdout,
            "stderr": res.stderr,
            "elapsed_s": res.elapsed_s,
        }
        if metadata:
            payload["metadata"] = metadata
        logger.info("%s => ok=%s rc=%s", name, res.ok, res.returncode)
        return payload

    def start_rollercoin_bot(self, *, timeout: int = 900) -> Dict[str, Any]:
        """
        Inicia el bot de RollerCoin de forma silenciosa.
        Usa el entrypoint del módulo AME_Core/rollercoin.
        """
        script = self.root / "AME_Core" / "rollercoin" / "main_v2.py"
        python_exe = sys.executable
        cmd = f'"{python_exe}" "{script}" --headless'
        return self.run(
            "rollercoin_bot",
            cmd,
            timeout=timeout,
            metadata={"module": "AME_Core.rollercoin.main_v2", "headless": True},
        )

    def health_check(self, *, timeout: int = 120) -> Dict[str, Any]:
        """
        Ejecuta health check del sistema.
        """
        script = self.root / "AURA_Core" / "check_health.py"
        python_exe = sys.executable
        cmd = f'"{python_exe}" "{script}"'
        return self.run(
            "health_check",
            cmd,
            timeout=timeout,
            metadata={"module": "AURA_Core.check_health"},
        )

    def start_shadow_core(self, *, timeout: int = 900) -> Dict[str, Any]:
        """
        Inicia Shadow-Core de forma silenciosa.
        """
        script = self.root / "Shadow-Core" / "start_shadow.py"
        python_exe = sys.executable
        cmd = f'"{python_exe}" "{script}"'
        return self.run(
            "shadow_core",
            cmd,
            timeout=timeout,
            metadata={"module": "Shadow-Core.start_shadow"},
        )

    def healer_tick(self, *, timeout: int = 300) -> Dict[str, Any]:
        """
        Ejecuta un tick del healer autónomo.
        """
        script = self.root / "AURA_Core" / "automation" / "healer.py"
        python_exe = sys.executable
        cmd = f'"{python_exe}" "{script}"'
        return self.run(
            "healer",
            cmd,
            timeout=timeout,
            metadata={"module": "AURA_Core.automation.healer"},
        )

    def custom(
        self,
        command: str,
        *,
        cwd: Optional[str] = None,
        timeout: int = 600,
        agent: str = "custom_cli",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Ejecuta un comando arbitrario de forma headless.
        Ideal para auto-curación dinámica.
        """
        return self.run(
            agent,
            command,
            cwd=cwd,
            timeout=timeout,
            metadata=metadata or {},
        )


def main(argv: Optional[List[str]] = None) -> int:
    """
    CLI entrypoint para invocar comandos predefinidos.

    Uso:
      python -m AURA_Core.tools.cli_agent_wrapper <comando> [opciones]

    Comandos:
      rollercoin   - Inicia bot de RollerCoin en modo headless.
      shadow       - Arranca Shadow-Core.
      health       - Health check del sistema.
      healer       - Tick del healer autónomo.
      custom       - Ejecuta comando arbitrario (pasar --cmd).
    """
    argv = argv or sys.argv[1:]
    wrapper = CLIAgentWrapper()

    cmd = (argv[0] if argv else "help").lower()
    if cmd in ("help", "-h", "--help"):
        print(main.__doc__)
        return 0

    if cmd == "rollercoin":
        res = wrapper.start_rollercoin_bot()
    elif cmd == "shadow":
        res = wrapper.start_shadow_core()
    elif cmd == "health":
        res = wrapper.health_check()
    elif cmd == "healer":
        res = wrapper.healer_tick()
    elif cmd == "custom":
        if "--cmd" not in argv:
            print("Uso: custom --cmd 'comando' [--timeout 600] [--agent nombre]")
            return 2
        idx = argv.index("--cmd")
        command = argv[idx + 1]
        timeout = 600
        agent = "custom_cli"
        if "--timeout" in argv:
            t_idx = argv.index("--timeout")
            try:
                timeout = int(argv[t_idx + 1])
            except Exception:
                pass
        if "--agent" in argv:
            a_idx = argv.index("--agent")
            agent = argv[a_idx + 1] or agent
        res = wrapper.custom(command, timeout=timeout, agent=agent)
    else:
        print(f"Comando desconocido: {cmd}")
        print(main.__doc__)
        return 2

    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
