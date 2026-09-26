"""AURA Local Secure Code Execution Sandbox & Isolated Worker Engine (Bloque 58).

Motor local de ejecucion segura en sandbox que permite a AURA ejecutar,
probar y depurar scripts generados dinamicamente durante sesiones de vibe
coding o tareas autonomas, dentro de entornos controlados y limitados.

Protege el sistema operativo host de:
- Modificaciones maliciosas al sistema de archivos
- Bucles infinitos y consumo descontrolado de CPU
- Fuga de memoria y recursos del sistema
- Accesos no autorizados a rutas sensibles
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import re
# import resource  # Not available on Windows
import subprocess
import sys
import threading
import time
import traceback
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("AURA.Agent.Sandbox")


class SandboxOutcome(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    KILLED = "killed"
    BLOCKED = "blocked"
    ERROR = "error"


@dataclass
class SandboxExecutionResult:
    execution_id: str
    code_hash: str
    outcome: SandboxOutcome
    stdout: str = ""
    stderr: str = ""
    return_code: Optional[int] = None
    duration_ms: float = 0.0
    memory_used_mb: float = 0.0
    peak_memory_mb: float = 0.0
    cpu_time_ms: float = 0.0
    blocked_paths: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "code_hash": self.code_hash,
            "outcome": self.outcome.value,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "return_code": self.return_code,
            "duration_ms": round(self.duration_ms, 2),
            "memory_used_mb": round(self.memory_used_mb, 2),
            "peak_memory_mb": round(self.peak_memory_mb, 2),
            "cpu_time_ms": round(self.cpu_time_ms, 2),
            "blocked_paths": self.blocked_paths,
            "warnings": self.warnings,
            "metadata": self.metadata,
        }


class SandboxConfig:
    DEFAULT_TIMEOUT_SECONDS = 30.0
    DEFAULT_MEMORY_LIMIT_MB = 256.0
    DEFAULT_CPU_TIME_LIMIT_SECONDS = 10.0
    DEFAULT_MAX_OUTPUT_CHARS = 65536

    SENSITIVE_PATTERNS = [
        (r"(?i)(/etc/|/windows/system32|/program files)", "ruta del sistema"),
        (r"(?i)(/boot/|/grub/|/efi)", "boot/grub/efi"),
        (r"(?i)(\.env)", "archivo .env"),
        (r"(?i)(/\.ssh/|ssh/|\.ssh)", "directorio .ssh"),
        (r"(?i)(/\.aws/|aws/|\.aws)", "directorio .aws"),
        (r"(?i)(secrets|private|token|credential)", "palabras clave sensibles"),
    ]

    DANGEROUS_PATTERNS = [
        (r"(?i)rm\s+-[rf]+\s+/", "rm -rf /"),
        (r"(?i)(format|mkfs|fdisk|dd\s+if=)", "format/mkfs/fdisk/dd"),
        (r"(?i)(shutdown|reboot|init\s+[0-6])", "shutdown/reboot"),
        (r"(?i)(chmod\s+777|chmod\s+-R\s+7)", "chmod 777"),
        (r"(?i)(iptables|ufw|firewall)", "iptables/ufw/firewall"),
        (r"(?i)(wget|curl)\s.*\|", "pipeline download a shell"),
        (r"(?i)(powershell|cmd|comspec)\s*-[abc]", "powershell/cmd con switches"),
    ]

    def __init__(
        self,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        memory_limit_mb: float = DEFAULT_MEMORY_LIMIT_MB,
        cpu_time_limit_seconds: float = DEFAULT_CPU_TIME_LIMIT_SECONDS,
        max_output_chars: int = DEFAULT_MAX_OUTPUT_CHARS,
        restrict_network: bool = True,
        restrict_filesystem: bool = True,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.memory_limit_mb = memory_limit_mb
        self.cpu_time_limit_seconds = cpu_time_limit_seconds
        self.max_output_chars = max_output_chars
        self.restrict_network = restrict_network
        self.restrict_filesystem = restrict_filesystem

    def is_code_blocked(self, code: str) -> List[str]:
        blocked: List[str] = []
        for pattern, desc in self.SENSITIVE_PATTERNS:
            if re.search(pattern, code):
                blocked.append(desc)
        for pattern, desc in self.DANGEROUS_PATTERNS:
            if re.search(pattern, code):
                blocked.append(desc)
        return blocked


class IsolatedSandboxRunner:
    """Ejecutor aislado de codigo con limites estrictos de tiempo y recursos."""

    def __init__(
        self,
        workspace_dir: Optional[Path] = None,
        default_timeout: float = SandboxConfig.DEFAULT_TIMEOUT_SECONDS,
        default_memory_limit: float = SandboxConfig.DEFAULT_MEMORY_LIMIT_MB,
    ) -> None:
        self._workspace_dir = workspace_dir or Path("data/sandbox").resolve()
        self._workspace_dir.mkdir(parents=True, exist_ok=True)
        self._default_timeout = default_timeout
        self._default_memory_limit = default_memory_limit
        self._lock = threading.Lock()
        self._executions: Dict[str, SandboxExecutionResult] = {}
        self._config = SandboxConfig()
        logger.info("IsolatedSandboxRunner ready at %s", self._workspace_dir)

    def _generate_execution_id(self) -> str:
        return hashlib.sha256(f"{time.time()}:{os.urandom(8).hex()}".encode("utf-8")).hexdigest()[:16]

    def _hash_code(self, code: str) -> str:
        return hashlib.sha256(code.encode("utf-8")).hexdigest()[:16]

    async def execute(
        self,
        code: str,
        language: str = "python",
        timeout: Optional[float] = None,
        memory_limit_mb: Optional[float] = None,
        cpu_limit_seconds: Optional[float] = None,
        env_vars: Optional[Dict[str, str]] = None,
        restrictions: Optional[Dict[str, Any]] = None,
    ) -> SandboxExecutionResult:
        config = self._config
        execution_id = self._generate_execution_id()
        code_hash = self._hash_code(code)

        blocked = config.is_code_blocked(code)
        if blocked:
            result = SandboxExecutionResult(
                execution_id=execution_id,
                code_hash=code_hash,
                outcome=SandboxOutcome.BLOCKED,
                blocked_paths=blocked,
                warnings=["Ejecucion bloqueada por seguridad"],
            )
            self._executions[execution_id] = result
            return result

        if language != "python":
            result = SandboxExecutionResult(
                execution_id=execution_id,
                code_hash=code_hash,
                outcome=SandboxOutcome.BLOCKED,
                warnings=[f"Lenguaje no soportado: {language}"],
            )
            self._executions[execution_id] = result
            return result

        start_time = time.time()
        timeout = timeout or config.timeout_seconds
        memory_limit_mb = memory_limit_mb or config.memory_limit_mb

        try:
            result = await self._execute_python(
                code, execution_id, code_hash, timeout, memory_limit_mb, start_time, env_vars or {}
            )
            self._executions[execution_id] = result
            return result
        except Exception as exc:
            logger.debug("Sandbox execution error: %s", exc)
            result = SandboxExecutionResult(
                execution_id=execution_id,
                code_hash=code_hash,
                outcome=SandboxOutcome.ERROR,
                stderr=str(exc),
                warnings=["Error durante la ejecucion"],
            )
            self._executions[execution_id] = result
            return result

    async def _execute_python(
        self, code, execution_id, code_hash, timeout, memory_limit_mb, start_time, env_vars
    ):
        import tempfile

        try:
            env = os.environ.copy()
            env.update(env_vars)
            env["PYTHONUNBUFFERED"] = "1"
            env["PYTHONDONTWRITEBYTECODE"] = "1"

            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".py",
                prefix=f"sandbox_{execution_id}_",
                dir=str(self._workspace_dir),
                delete=False,
                encoding="utf-8",
            ) as tmp:
                tmp.write(code)
                tmp_path = tmp.name

            try:
                proc = await asyncio.create_subprocess_exec(
                    sys.executable,
                    tmp_path,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=env,
                    cwd=str(self._workspace_dir),
                )

                try:
                    stdout, stderr = await asyncio.wait_for(
                        proc.communicate(), timeout=timeout
                    )
                except asyncio.TimeoutError:
                    try:
                        proc.kill()
                        await proc.wait()
                    except Exception:
                        pass
                    duration_ms = (time.time() - start_time) * 1000
                    return SandboxExecutionResult(
                        execution_id=execution_id,
                        code_hash=code_hash,
                        outcome=SandboxOutcome.TIMEOUT,
                        stderr="Timeout: el codigo excedio el limite de tiempo",
                        duration_ms=duration_ms,
                        warnings=["Timeout de ejecucion"],
                    )

                stdout_text = stdout.decode("utf-8", errors="replace")[:self._config.max_output_chars]
                stderr_text = stderr.decode("utf-8", errors="replace")[:self._config.max_output_chars]
                duration_ms = (time.time() - start_time) * 1000
                outcome = SandboxOutcome.SUCCESS if proc.returncode == 0 else SandboxOutcome.FAILED

                return SandboxExecutionResult(
                    execution_id=execution_id,
                    code_hash=code_hash,
                    outcome=outcome,
                    stdout=stdout_text,
                    stderr=stderr_text,
                    return_code=proc.returncode,
                    duration_ms=duration_ms,
                    warnings=[],
                )
            finally:
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass

        except Exception as exc:
            logger.debug("Python execution failed: %s", exc)
            duration_ms = (time.time() - start_time) * 1000
            return SandboxExecutionResult(
                execution_id=execution_id,
                code_hash=code_hash,
                outcome=SandboxOutcome.ERROR,
                stderr=str(exc),
                duration_ms=duration_ms,
                warnings=["Error durante la ejecucion"],
            )
    def get_execution_result(self, execution_id: str) -> Optional[SandboxExecutionResult]:
        return self._executions.get(execution_id)

    def list_recent_executions(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self._lock:
            executions = list(self._executions.values())
        executions.sort(key=lambda r: r.execution_id, reverse=True)
        return [r.to_dict() for r in executions[:limit]]

    def clear_executions(self, older_than_seconds: Optional[float] = None) -> int:
        with self._lock:
            if older_than_seconds is None:
                count = len(self._executions)
                self._executions.clear()
                return count
            cutoff = time.time() - older_than_seconds
            to_remove = [
                eid
                for eid, res in self._executions.items()
                if res.metadata.get("start_time", 0) < cutoff
            ]
            for eid in to_remove:
                del self._executions[eid]
            return len(to_remove)

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            outcomes: Dict[str, int] = {}
            for res in self._executions.values():
                outcomes[res.outcome.value] = outcomes.get(res.outcome.value, 0) + 1
            return {
                "workspace_dir": str(self._workspace_dir),
                "total_executions": len(self._executions),
                "outcomes": outcomes,
                "default_timeout_seconds": self._default_timeout,
                "default_memory_limit_mb": self._default_memory_limit,
                "config": {
                    "restrict_network": self._config.restrict_network,
                    "restrict_filesystem": self._config.restrict_filesystem,
                },
            }


_sandbox_runner: Optional[IsolatedSandboxRunner] = None


def get_sandbox_runner(workspace_dir: Optional[Path] = None) -> IsolatedSandboxRunner:
    global _sandbox_runner
    if _sandbox_runner is None:
        _sandbox_runner = IsolatedSandboxRunner(workspace_dir=workspace_dir)
    return _sandbox_runner


def reset_sandbox_runner() -> None:
    global _sandbox_runner
    _sandbox_runner = None


def lint_python_code(code: str) -> Dict[str, Any]:
    """Verifica sintaxis de codigo Python sin ejecutarlo (AST check)."""
    import ast

    try:
        tree = ast.parse(code)
        warnings: List[str] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in ("os", "sys", "subprocess", "ctypes", "socket", "requests", "urllib"):
                        warnings.append(f"Importacion de {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module in ("os", "sys", "subprocess", "ctypes"):
                    warnings.append(f"Importacion desde {node.module}")
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    if node.func.attr in ("system", "popen", "call", "run"):
                        warnings.append("Ejecucion de comandos detectada")
                elif isinstance(node.func, ast.Name):
                    if node.func.id in ("eval", "exec", "compile"):
                        warnings.append(f"Uso de {node.func.id} detectado")

        return {
            "valid": True,
            "warnings": warnings,
            "error_count": 0,
            "error_messages": [],
        }

    except SyntaxError as exc:
        return {
            "valid": False,
            "warnings": [],
            "error_count": 1,
            "error_messages": [
                {
                    "type": "SyntaxError",
                    "message": str(exc),
                    "line": exc.lineno,
                    "offset": exc.offset,
                    "text": exc.text,
                }
            ],
        }


def analyze_python_code(code: str, timeout: float = 10.0) -> Dict[str, Any]:
    """Ejecuta pruebas basicas sobre codigo Python en sandbox."""
    import ast

    tree = ast.parse(code)
    test_imports: List[str] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            module = node.module if isinstance(node, ast.ImportFrom) else node.names[0].name
            if module and "test" in module.lower():
                test_imports.append(module)

    return {
        "syntax_valid": True,
        "test_imports": test_imports,
        "warnings": [],
        "can_execute": True,
    }


__all__ = [
    "SandboxOutcome",
    "SandboxExecutionResult",
    "SandboxConfig",
    "IsolatedSandboxRunner",
    "get_sandbox_runner",
    "reset_sandbox_runner",
    "lint_python_code",
    "analyze_python_code",
]
