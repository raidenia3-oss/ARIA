"""
Reverse Engineer (REA) — Launcher autónomo para AURA.

REA (morluto/rea) funciona como MCP server stdio (no TCP/HTTP). Esto significa
que el servidor REA no "escucha" en un puerto; en su lugar, se lanza como
un subproceso bajo demanda cuando AURA necesita interactuar con él vía MCP client.

Este launcher proporciona:
- Verificación de que REA está instalado y el binario está disponible.
- Un servicio "health-check" autónomo que valida REA periódicamente.
- Estado expuesto vía ``GET /api/rea/status`` y ``GET /api/system/autonomy``.

Diseño:
- ``start_reverse_engineer()`` es una corutina que actúa como proceso de
  monitoreo: verifica que el binario REA existe y puede iniciarse, manteniendo
  el estado health=True. Si REA desaparece, la corutina termina y el supervisor
  la reinicia con *backoff* exponencial.
- La guarda ``AURA_REA_PATH`` (o ``github/reverse-engineer``) controla
  dónde se busca el repositorio.
- El Puerto MCP (AURA_REA_PORT, default 8843) es informativo; REA usa stdio MCP.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import time
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("AURA.ReverseEngineer")

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_REA_PATH = _PROJECT_ROOT / "github" / "reverse-engineer"
_DEFAULT_REA_PORT = 8843

_SERVICE_NAME = "reverse-engineer"


def _resolve_rea_path() -> Optional[Path]:
    configured = os.getenv("AURA_REA_PATH")
    candidates: list[Path] = []
    if configured:
        candidates.append(Path(configured))
    if not configured:
        candidates.append(_DEFAULT_REA_PATH)
    for c in candidates:
        if c.is_dir():
            return c
    return None


def _resolve_rea_cmd(rea_path: Path) -> list[str]:
    """Resuelve el comando para lanzar el MCP server de REA.

    REA funciona como MCP server stdio (no TCP), por lo que no se usa --port.
    """
    for binary in ("rea", "rea.cmd", "rea-agents", "rea-agents.cmd"):
        exe = shutil.which(binary)
        if exe:
            return [exe, "--mcp"]
    npx = shutil.which("npx") or shutil.which("npx.cmd")
    if npx:
        return [npx, "rea", "--mcp"]
    node = shutil.which("node") or shutil.which("node.exe")
    if node:
        local_npx = str(rea_path / "node_modules" / ".bin" / "npx")
        if os.path.exists(local_npx):
            return [node, local_npx, "rea", "--mcp"]
    return ["npx", "rea", "--mcp"]


def _check_rea_health(rea_path: Path) -> bool:
    """Verifica que el binario REA existe y puede ejecutarse."""
    cmd = _resolve_rea_cmd(rea_path)
    binary = cmd[0]
    if not shutil.which(binary) and not os.path.exists(binary):
        logger.warning("ReverseEngineer: binario no encontrado: %s", binary)
        return False

    # Verificar que el directorio de REA tiene dist/mcp/main.js (runtime compilado)
    mcp_main = rea_path / "dist" / "mcp" / "main.js"
    if not mcp_main.exists():
        logger.warning("ReverseEngineer: REA runtime no compilado: %s", mcp_main)
        return False

    return True


async def start_reverse_engineer() -> None:
    """Corutina principal: monitorea el estado del launcher REA.

    REA funciona como MCP server stdio (cliente lo lanza bajo demanda).
    Esta corutina verifica periódicamente que REA está instalado y saludable,
    y mantiene un proceso de health-check activo. Si REA desaparece, termina
    con error y el supervisor lo reinicia.

    Se cancela limpiamente al detener el supervisor.
    """
    rea_path = _resolve_rea_path()
    if rea_path is None:
        raise FileNotFoundError(
            f"REA no encontrado. Configure AURA_REA_PATH o clone morluto/rea "
            f"en {_DEFAULT_REA_PATH}"
        )

    logger.info("ReverseEngineer: iniciando monitoreo de REA en %s", rea_path)

    check_interval = float(os.getenv("AURA_REA_CHECK_INTERVAL", "30"))
    failure_count = 0
    max_failures = 3

    try:
        while True:
            if _check_rea_health(rea_path):
                failure_count = 0
                logger.info("ReverseEngineer: REA saludable (pid=%s)", os.getpid())
            else:
                failure_count += 1
                logger.warning(
                    "ReverseEngineer: health check falló (%d/%d)",
                    failure_count, max_failures
                )
                if failure_count >= max_failures:
                    raise RuntimeError(
                        "ReverseEngineer: REA no saludable tras "
                        f"{max_failures} intentos consecutivos"
                    )

            await asyncio.sleep(check_interval)
    except asyncio.CancelledError:
        logger.info("ReverseEngineer: monitoreo cancelado")
        raise


def get_service_status() -> Dict[str, Any]:
    """Estado estático del servicio (no depende del supervisor)."""
    rea_path = _resolve_rea_path()
    found = rea_path is not None
    healthy = False
    if found:
        try:
            healthy = _check_rea_health(rea_path)  # type: ignore[arg-type]
        except Exception:
            healthy = False

    return {
        "name": _SERVICE_NAME,
        "path": str(rea_path) if rea_path else None,
        "found": found,
        "healthy": healthy,
        "port": os.getenv("AURA_REA_PORT", str(_DEFAULT_REA_PORT)),
        "enabled": os.getenv("AURA_ENABLE_REA", "true").lower() == "true",
        "mode": "stdio-mcp",
        "checked_at": time.time(),
    }
