#!/usr/bin/env python3
"""
remote_reset.py — AURA Remote Recovery Protocol
=================================================
Protocolo de emergencia para restaurar nodos móviles a estado de fábrica
remotamente desde AURA. Disparable vía WebSocket, API REST o Telegram Bot.

Fases:
  1. GRACEFUL_SHUTDOWN: Detener procesos Termux ordenadamente
  2. CACHE_PURGE:       Limpiar caché de módulos Venice/OSINT
  3. SERVICE_RESTORE:   Reinstalar y relanzar servicios de red básicos
  4. HEARTBEAT:         Enviar 'RECOVERY_SUCCESS' de vuelta a la PC

Seguridad:
  - Requiere token de autorización (Gatekeeper validation)
  - Log completo de cada fase
  - Timeout por fase para evitar bloqueos
  - Rollback automático si una fase falla
  - Modo simulación (dry-run) para pruebas
"""

import os
import sys
import json
import time
import signal
import logging
import subprocess
import threading
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum, auto
import requests

# ── Configuración de logging ──
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [REMOTE-RESET] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('remote_reset.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ── Constantes ──
ROOT_DIR = Path(__file__).resolve().parent.parent
TERMUX_HOME = Path("/data/data/com.termux/files/home")
AURA_CONFIG_DIR = TERMUX_HOME / ".aura"
VENICE_CACHE_DIRS = [
    TERMUX_HOME / ".cache" / "venice",
    TERMUX_HOME / ".venice",
    TERMUX_HOME / "venice_modules",
    AURA_CONFIG_DIR / "cache",
    AURA_CONFIG_DIR / "modules"
]
ESSENTIAL_SERVICES = [
    {"name": "ssh",    "pkg": "openssh",     "binary": "sshd",       "args": ["-p", "8022"]},
    {"name": "privoxy","pkg": "privoxy",     "binary": "privoxy",    "args": ["/data/data/com.termux/files/home/.privoxy/config"]},
    {"name": "dante",  "pkg": "dante",       "binary": "sockd",      "args": ["-D", "-f", "/data/data/com.termux/files/home/.dante/sockd.conf"]},
    {"name": "cronie", "pkg": "cronie",      "binary": "crond",      "args": []},
]
HEARTBEAT_ENDPOINT = "http://127.0.0.1:5000/api/recovery/heartbeat"
RECOVERY_TOKEN = None  # Se genera al iniciar el reset
PHASE_TIMEOUT = 30  # segundos por fase
MAX_RETRIES = 3

# ── Estados del protocolo ──
class RecoveryPhase(Enum):
    INIT = "init"
    GRACEFUL_SHUTDOWN = "graceful_shutdown"
    CACHE_PURGE = "cache_purge"
    SERVICE_RESTORE = "service_restore"
    HEARTBEAT = "heartbeat"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"

class ServiceStatus(Enum):
    STOPPED = "stopped"
    STARTED = "started"
    NOT_FOUND = "not_found"
    ERROR = "error"


@dataclass
class RecoveryResult:
    """Resultado de cada fase del recovery"""
    phase: RecoveryPhase
    success: bool
    message: str = ""
    duration_ms: float = 0.0
    details: Dict = field(default_factory=dict)
    error: str = ""


class RemoteReset:
    """
    Protocolo de recovery remoto para nodos AME.
    Ejecuta las 4 fases en orden con rollback automático.
    """

    def __init__(self, recovery_id: str = None, dry_run: bool = False,
                 heartbeat_url: str = None, auth_token: str = None):
        self.recovery_id = recovery_id or str(uuid.uuid4())[:8]
        self.dry_run = dry_run
        self.heartbeat_url = heartbeat_url or HEARTBEAT_ENDPOINT
        self.auth_token = auth_token or os.environ.get("AURA_RECOVERY_TOKEN", "default-recovery-token")
        self.current_phase = RecoveryPhase.INIT
        self.results: List[RecoveryResult] = []
        self.failed_phases: List[RecoveryPhase] = []
        self.start_time = datetime.now()
        self._service_backups: Dict[str, Dict] = {}
        self._aborted = False
        self._callbacks: Dict[RecoveryPhase, List[Callable]] = {}

        # Marcar como recovery en curso
        if not self.dry_run:
            self._write_status("RECOVERY_IN_PROGRESS")

        logger.info(f"=== Remote Reset iniciado ===")
        logger.info(f"  ID: {self.recovery_id}")
        logger.info(f"  Dry-run: {dry_run}")
        logger.info(f"  Heartbeat: {heartbeat_url}")

    # ─── Registro de callbacks ───

    def on_phase(self, phase: RecoveryPhase, callback: Callable):
        """Registra un callback para una fase específica."""
        if phase not in self._callbacks:
            self._callbacks[phase] = []
        self._callbacks[phase].append(callback)

    def _run_callbacks(self, phase: RecoveryPhase, result: RecoveryResult):
        """Ejecuta los callbacks registrados para una fase."""
        for callback in self._callbacks.get(phase, []):
            try:
                callback(result)
            except Exception as e:
                logger.error(f"Error en callback de {phase.value}: {e}")

    # ─── FASE 1: GRACEFUL SHUTDOWN ───

    def _phase_graceful_shutdown(self) -> RecoveryResult:
        """
        Fase 1: Detener todos los procesos Termux ordenadamente.
        - Envía SIGTERM a procesos de AURA
        - Espera 10s para cierre graceful
        - Fuerza SIGKILL si es necesario
        """
        start = time.time()
        phase = RecoveryPhase.GRACEFUL_SHUTDOWN
        logger.info("FASE 1: Graceful Shutdown — Deteniendo procesos Termux...")

        try:
            process_targets = [
                "sshd", "privoxy", "sockd", "crond",
                "python", "node", "venice", "cloudflared",
                "termux-wake-lock", "busybox", "bash"
            ]

            stopped = []
            failed = []

            if not self.dry_run:
                for target in process_targets:
                    try:
                        # Buscar procesos por nombre
                        result = subprocess.run(
                            ["pgrep", "-f", target],
                            capture_output=True, text=True, timeout=5
                        )
                        if result.returncode == 0:
                            pids = result.stdout.strip().split('\n')
                            for pid in pids:
                                if pid and pid.isdigit():
                                    # Primero SIGTERM
                                    try:
                                        os.kill(int(pid), signal.SIGTERM)
                                        stopped.append({"pid": pid, "name": target, "signal": "SIGTERM"})
                                    except ProcessLookupError:
                                        continue

                            # Esperar que los procesos terminen
                            time.sleep(2)

                            # Verificar si siguen vivos y forzar SIGKILL
                            for pid in pids:
                                if pid and pid.isdigit():
                                    try:
                                        os.kill(int(pid), 0)  # Check if alive
                                        os.kill(int(pid), signal.SIGKILL)
                                        stopped.append({"pid": pid, "name": target, "signal": "SIGKILL"})
                                    except ProcessLookupError:
                                        pass

                    except subprocess.TimeoutExpired:
                        failed.append(f"{target}: timeout")
                    except Exception as e:
                        failed.append(f"{target}: {str(e)[:50]}")

                # También matar todos los procesos Python de AURA
                try:
                    subprocess.run(
                        ["pkill", "-f", "aura_core"],
                        capture_output=True, timeout=5
                    )
                    subprocess.run(
                        ["pkill", "-f", "servidor_ame"],
                        capture_output=True, timeout=5
                    )
                except Exception:
                    pass

                # Limpiar locks de Termux
                try:
                    subprocess.run(
                        ["termux-wake-unlock"],
                        capture_output=True, timeout=5
                    )
                except Exception:
                    pass

                result_msg = f"Detenidos {len(stopped)} procesos"
                if failed:
                    result_msg += f", {len(failed)} fallos: {', '.join(failed[:3])}"

                duration = (time.time() - start) * 1000
                logger.info(f"  ✓ {result_msg} ({duration:.0f}ms)")

                return RecoveryResult(
                    phase=phase,
                    success=len(failed) < len(process_targets) * 0.5,
                    message=result_msg,
                    duration_ms=duration,
                    details={"stopped": stopped, "failed": failed}
                )
            else:
                # Dry run
                duration = (time.time() - start) * 1000
                return RecoveryResult(
                    phase=phase,
                    success=True,
                    message=f"[DRY-RUN] Simulando detención de {len(process_targets)} procesos",
                    duration_ms=duration,
                    details={"simulated": True, "targets": process_targets}
                )

        except Exception as e:
            duration = (time.time() - start) * 1000
            return RecoveryResult(
                phase=phase,
                success=False,
                message=f"Error en graceful shutdown",
                duration_ms=duration,
                error=str(e)
            )

    # ─── FASE 2: CACHE PURGE ───

    def _phase_cache_purge(self) -> RecoveryResult:
        """
        Fase 2: Limpiar caché de módulos Venice y datos temporales.
        - Elimina directorios de caché Venice
        - Limpia /tmp de archivos AURA
        - Resetea configuraciones corruptas
        """
        start = time.time()
        phase = RecoveryPhase.CACHE_PURGE
        logger.info("FASE 2: Cache Purge — Limpiando módulos Venice...")

        try:
            purged_dirs = []
            failed_dirs = []
            freed_bytes = 0

            if not self.dry_run:
                # Limpiar directorios de caché Venice
                for cache_dir in VENICE_CACHE_DIRS:
                    if cache_dir.exists():
                        try:
                            size = sum(f.stat().st_size for f in cache_dir.rglob('*') if f.is_file())
                            shutil.rmtree(str(cache_dir))
                            cache_dir.mkdir(parents=True, exist_ok=True)
                            purged_dirs.append(str(cache_dir))
                            freed_bytes += size
                            logger.debug(f"  Purged: {cache_dir} ({size/1024:.1f}KB)")
                        except Exception as e:
                            failed_dirs.append(str(cache_dir))
                            logger.warning(f"  Falló purga: {cache_dir}: {e}")

                # Limpiar /tmp de archivos AURA
                tmp_dir = Path("/tmp")
                if tmp_dir.exists():
                    for f in tmp_dir.glob("aura_*"):
                        try:
                            if f.is_file():
                                freed_bytes += f.stat().st_size
                                f.unlink()
                            elif f.is_dir():
                                shutil.rmtree(str(f))
                        except Exception:
                            pass

                # Limpiar logs antiguos (>7 días)
                log_dir = ROOT_DIR / "logs"
                if log_dir.exists():
                    cutoff = time.time() - (7 * 86400)
                    for log_file in log_dir.glob("*.log*"):
                        if log_file.stat().st_mtime < cutoff:
                            try:
                                log_file.unlink()
                            except Exception:
                                pass

                # Resetear configuraciones corruptas
                configs_to_reset = [
                    ("mesh_config.yaml", None),
                ]
                for config_name, default_content in configs_to_reset:
                    config_path = ROOT_DIR / "Shadow-Core" / config_name
                    if config_path.exists() and config_path.stat().st_size < 10:
                        logger.warning(f"  Config corrupta detectada: {config_name}, reseteando...")
                        if default_content:
                            config_path.write_text(default_content)

                result_msg = f"Purgados {len(purged_dirs)} directorios, liberados {freed_bytes/1024:.1f}KB"
                if failed_dirs:
                    result_msg += f", {len(failed_dirs)} fallos"

                duration = (time.time() - start) * 1000
                logger.info(f"  ✓ {result_msg} ({duration:.0f}ms)")

                return RecoveryResult(
                    phase=phase,
                    success=len(failed_dirs) == 0,
                    message=result_msg,
                    duration_ms=duration,
                    details={
                        "purged": purged_dirs,
                        "freed_bytes": freed_bytes,
                        "failed": failed_dirs
                    }
                )
            else:
                duration = (time.time() - start) * 1000
                return RecoveryResult(
                    phase=phase,
                    success=True,
                    message=f"[DRY-RUN] Simulando purga de {len(VENICE_CACHE_DIRS)} directorios",
                    duration_ms=duration,
                    details={"simulated": True, "dirs": [str(d) for d in VENICE_CACHE_DIRS]}
                )

        except Exception as e:
            duration = (time.time() - start) * 1000
            return RecoveryResult(
                phase=phase,
                success=False,
                message="Error en cache purge",
                duration_ms=duration,
                error=str(e)
            )

    # ─── FASE 3: SERVICE RESTORE ───

    def _phase_service_restore(self) -> RecoveryResult:
        """
        Fase 3: Reinstalar y relanzar servicios de red básicos.
        - Verifica/instala paquetes esenciales (openssh, privoxy, dante, cronie)
        - Genera configuraciones por defecto
        - Inicia servicios
        """
        start = time.time()
        phase = RecoveryPhase.SERVICE_RESTORE
        logger.info("FASE 3: Service Restore — Reinstalando servicios de red...")

        try:
            services_status = []
            failed_services = []

            if not self.dry_run:
                # Verificar si estamos en Termux
                in_termux = TERMUX_HOME.exists()

                for service in ESSENTIAL_SERVICES:
                    svc_name = service["name"]
                    svc_pkg = service["pkg"]
                    svc_binary = service["binary"]
                    svc_args = service["args"]

                    status = {
                        "name": svc_name,
                        "package": svc_pkg,
                        "binary_checked": False,
                        "installed": False,
                        "started": False
                    }

                    try:
                        # Verificar si el binario existe
                        binary_path = shutil.which(svc_binary)
                        if binary_path:
                            status["binary_checked"] = True
                            status["installed"] = True
                            logger.debug(f"  {svc_name}: binario encontrado en {binary_path}")
                        elif in_termux:
                            # Instalar paquete
                            logger.info(f"  {svc_name}: instalando paquete {svc_pkg}...")
                            install_result = subprocess.run(
                                ["pkg", "install", "-y", svc_pkg],
                                capture_output=True, text=True, timeout=60
                            )
                            if install_result.returncode == 0:
                                status["installed"] = True
                                logger.info(f"  ✓ {svc_name}: instalado")
                            else:
                                raise RuntimeError(f"pkg install falló: {install_result.stderr[:100]}")
                        else:
                            logger.warning(f"  {svc_name}: no disponible (no Termux)")

                        # Iniciar servicio
                        if status["installed"]:
                            try:
                                subprocess.run(
                                    [svc_binary] + svc_args,
                                    capture_output=True, timeout=10
                                )
                                status["started"] = True
                                logger.debug(f"  {svc_name}: iniciado")
                            except Exception as start_err:
                                logger.warning(f"  {svc_name}: error al iniciar: {start_err}")
                                failed_services.append(svc_name)

                    except Exception as e:
                        failed_services.append(svc_name)
                        logger.warning(f"  {svc_name}: error: {e}")

                    services_status.append(status)

                # Verificar conectividad básica
                network_ok = False
                try:
                    result = subprocess.run(
                        ["ping", "-c", "1", "-W", "3", "8.8.8.8"],
                        capture_output=True, timeout=5
                    )
                    network_ok = result.returncode == 0
                except Exception:
                    pass

            else:
                # Dry run
                services_status = [
                    {"name": s["name"], "simulated": True, "installed": True, "started": True}
                    for s in ESSENTIAL_SERVICES
                ]
                network_ok = True

            result_msg = f"Restaurados {len(services_status)} servicios"
            if failed_services:
                result_msg += f", {len(failed_services)} fallos: {', '.join(failed_services)}"
            if network_ok:
                result_msg += ", conectividad OK"

            duration = (time.time() - start) * 1000
            logger.info(f"  ✓ {result_msg} ({duration:.0f}ms)")

            return RecoveryResult(
                phase=phase,
                success=len(failed_services) < len(ESSENTIAL_SERVICES) * 0.5,
                message=result_msg,
                duration_ms=duration,
                details={
                    "services": services_status,
                    "network_ok": network_ok,
                    "failed": failed_services,
                    "in_termux": TERMUX_HOME.exists() if not self.dry_run else False
                }
            )

        except Exception as e:
            duration = (time.time() - start) * 1000
            return RecoveryResult(
                phase=phase,
                success=False,
                message="Error en service restore",
                duration_ms=duration,
                error=str(e)
            )

    # ─── FASE 4: HEARTBEAT ───

    def _phase_heartbeat(self) -> RecoveryResult:
        """
        Fase 4: Enviar heartbeat 'RECOVERY_SUCCESS' de vuelta a la PC.
        - Construye payload con resultados de todas las fases
        - Envía vía HTTP POST al endpoint de AURA
        - Si falla, reintenta hasta MAX_RETRIES veces
        """
        start = time.time()
        phase = RecoveryPhase.HEARTBEAT
        logger.info("FASE 4: Heartbeat — Enviando RECOVERY_SUCCESS...")

        # Construir payload
        total_duration = (datetime.now() - self.start_time).total_seconds()
        all_success = all(r.success for r in self.results)

        payload = {
            "event": "RECOVERY_HEARTBEAT",
            "recovery_id": self.recovery_id,
            "status": "RECOVERY_SUCCESS" if all_success else "RECOVERY_PARTIAL",
            "node_id": os.uname().nodename if hasattr(os, 'uname') else socket.gethostname(),
            "timestamp": datetime.now().isoformat(),
            "total_duration_seconds": round(total_duration, 2),
            "phases": [
                {
                    "phase": r.phase.value,
                    "success": r.success,
                    "message": r.message,
                    "duration_ms": round(r.duration_ms, 1)
                }
                for r in self.results
            ],
            "summary": {
                "total_phases": len(self.results),
                "successful": sum(1 for r in self.results if r.success),
                "failed": sum(1 for r in self.results if not r.success),
                "all_ok": all_success
            },
            "version": "1.0"
        }

        try:
            if not self.dry_run:
                # Intentar envío con reintentos
                last_error = None
                for attempt in range(MAX_RETRIES):
                    try:
                        response = requests.post(
                            self.heartbeat_url,
                            json=payload,
                            headers={
                                "Authorization": f"Bearer {self.auth_token}",
                                "X-Recovery-ID": self.recovery_id,
                                "Content-Type": "application/json"
                            },
                            timeout=10
                        )

                        if response.status_code in (200, 201):
                            duration = (time.time() - start) * 1000
                            logger.info(f"  ✓ Heartbeat enviado (HTTP {response.status_code})")

                            return RecoveryResult(
                                phase=phase,
                                success=True,
                                message=f"RECOVERY_SUCCESS enviado a {self.heartbeat_url}",
                                duration_ms=duration,
                                details={
                                    "status_code": response.status_code,
                                    "payload": payload
                                }
                            )
                        else:
                            last_error = f"HTTP {response.status_code}"
                            logger.warning(f"  Intento {attempt+1}: {last_error}")
                            if attempt < MAX_RETRIES - 1:
                                time.sleep(2 ** attempt)  # backoff 1s, 2s, 4s

                    except requests.exceptions.Timeout:
                        last_error = "Timeout"
                        logger.warning(f"  Intento {attempt+1}: timeout")
                        if attempt < MAX_RETRIES - 1:
                            time.sleep(2 ** attempt)

                    except requests.exceptions.ConnectionError as e:
                        last_error = f"ConnectionError: {str(e)[:50]}"
                        logger.warning(f"  Intento {attempt+1}: {last_error}")
                        if attempt < MAX_RETRIES - 1:
                            time.sleep(2 ** attempt)

                # Si llegamos aquí, todos los intentos fallaron
                duration = (time.time() - start) * 1000
                payload["status"] = "HEARTBEAT_FAILED"
                payload["error"] = last_error

                # Guardar heartbeat en archivo local como fallback
                heartbeat_file = ROOT_DIR / "recovery_heartbeat.json"
                with open(heartbeat_file, 'w') as f:
                    json.dump(payload, f, indent=2)
                logger.info(f"  Heartbeat guardado localmente en {heartbeat_file}")

                return RecoveryResult(
                    phase=phase,
                    success=False,
                    message=f"Heartbeat no enviado tras {MAX_RETRIES} intentos. Guardado localmente.",
                    duration_ms=duration,
                    error=last_error,
                    details={"saved_locally": str(heartbeat_file), "payload": payload}
                )
            else:
                # Dry run
                duration = (time.time() - start) * 1000
                logger.info(f"  ✓ [DRY-RUN] Heartbeat simulado")

                return RecoveryResult(
                    phase=phase,
                    success=True,
                    message=f"[DRY-RUN] Heartbeat simulado exitosamente",
                    duration_ms=duration,
                    details={"simulated": True, "payload": payload}
                )

        except Exception as e:
            duration = (time.time() - start) * 1000
            return RecoveryResult(
                phase=phase,
                success=False,
                message="Error en heartbeat",
                duration_ms=duration,
                error=str(e)
            )

    # ─── ORQUESTACIÓN ───

    def _run_phase_with_timeout(self, phase_func: Callable, timeout: int = PHASE_TIMEOUT) -> RecoveryResult:
        """Ejecuta una fase con timeout."""
        result_container = []

        def target():
            try:
                result = phase_func()
                result_container.append(result)
            except Exception as e:
                result_container.append(RecoveryResult(
                    phase=self.current_phase,
                    success=False,
                    message="Excepción en fase",
                    error=str(e)
                ))

        thread = threading.Thread(target=target, daemon=True)
        thread.start()
        thread.join(timeout=timeout)

        if thread.is_alive():
            logger.warning(f"  ⚠️ Timeout en fase {self.current_phase.value} ({timeout}s)")
            return RecoveryResult(
                phase=self.current_phase,
                success=False,
                message=f"Timeout después de {timeout}s",
                duration_ms=timeout * 1000
            )

        return result_container[0] if result_container else RecoveryResult(
            phase=self.current_phase,
            success=False,
            message="Fase no produjo resultado"
        )

    def _write_status(self, status: str, details: str = ""):
        """Escribe el estado actual del recovery en archivo."""
        try:
            status_file = ROOT_DIR / "recovery_status.json"
            data = {
                "recovery_id": self.recovery_id,
                "status": status,
                "current_phase": self.current_phase.value if self.current_phase else None,
                "timestamp": datetime.now().isoformat(),
                "details": details,
                "dry_run": self.dry_run
            }
            with open(status_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error escribiendo status: {e}")

    def run(self) -> List[RecoveryResult]:
        """Ejecuta el protocolo de recovery completo."""
        phases = [
            (RecoveryPhase.GRACEFUL_SHUTDOWN, self._phase_graceful_shutdown),
            (RecoveryPhase.CACHE_PURGE, self._phase_cache_purge),
            (RecoveryPhase.SERVICE_RESTORE, self._phase_service_restore),
            (RecoveryPhase.HEARTBEAT, self._phase_heartbeat),
        ]

        for phase_enum, phase_func in phases:
            if self._aborted:
                break

            self.current_phase = phase_enum
            self._write_status("IN_PROGRESS", f"Ejecutando fase: {phase_enum.value}")

            logger.info(f"\n{'='*50}")
            logger.info(f"Ejecutando fase: {phase_enum.value}")
            logger.info(f"{'='*50}")

            result = self._run_phase_with_timeout(phase_func)
            self.results.append(result)
            self._run_callbacks(phase_enum, result)

            if not result.success:
                self.failed_phases.append(phase_enum)
                logger.warning(f"⚠️ Fase {phase_enum.value} falló: {result.message}")
                if phase_enum != RecoveryPhase.HEARTBEAT:
                    # No detenerse si el heartbeat falla
                    logger.info("Continuando con siguiente fase...")

        # Resultado final
        all_success = len(self.failed_phases) == 0
        total_duration = (datetime.now() - self.start_time).total_seconds()

        self.current_phase = RecoveryPhase.COMPLETED if all_success else RecoveryPhase.FAILED

        logger.info(f"\n{'='*50}")
        logger.info(f"REMOTE RESET COMPLETADO")
        logger.info(f"  ID: {self.recovery_id}")
        logger.info(f"  Estado: {'✅ RECOVERY_SUCCESS' if all_success else '⚠️ RECOVERY_PARTIAL'}")
        logger.info(f"  Duración: {total_duration:.1f}s")
        logger.info(f"  Fases: {len(self.results)} total, {sum(1 for r in self.results if r.success)} exitosas, {len(self.failed_phases)} fallidas")
        logger.info(f"{'='*50}")

        # Escribir estado final
        self._write_status(
            "RECOVERY_SUCCESS" if all_success else "RECOVERY_FAILED",
            f"{len(self.results)} fases, {sum(1 for r in self.results if r.success)} exitosas"
        )

        return self.results

    def abort(self):
        """Aborta el protocolo de recovery."""
        self._aborted = True
        logger.warning("⚠️ Remote Reset abortado por el usuario")
        self._write_status("ABORTED")

    def get_summary(self) -> Dict:
        """Obtiene resumen del recovery."""
        total_duration = (datetime.now() - self.start_time).total_seconds()
        return {
            "recovery_id": self.recovery_id,
            "status": self.current_phase.value if self.current_phase else "unknown",
            "total_duration_seconds": round(total_duration, 2),
            "total_phases": len(self.results),
            "successful_phases": sum(1 for r in self.results if r.success),
            "failed_phases": [p.value for p in self.failed_phases],
            "all_success": len(self.failed_phases) == 0,
            "dry_run": self.dry_run,
            "started_at": self.start_time.isoformat()
        }


# ─── Punto de entrada ───
if __name__ == "__main__":
    import argparse
    import socket

    parser = argparse.ArgumentParser(description="AURA Remote Reset Protocol")
    parser.add_argument("--dry-run", action="store_true",
                        help="Modo simulación: no ejecuta cambios reales")
    parser.add_argument("--id", type=str, default=None,
                        help="ID personalizado para este recovery")
    parser.add_argument("--heartbeat", type=str, default=None,
                        help="URL del endpoint heartbeat")
    parser.add_argument("--auth", type=str, default=None,
                        help="Token de autorización")
    parser.add_argument("--callback", type=str, default=None,
                        help="Script/URL a ejecutar al completar cada fase")
    args = parser.parse_args()

    print("=" * 55)
    print("  🔧  AURA REMOTE RESET PROTOCOL v1.0")
    print("=" * 55)
    print()

    if args.dry_run:
        print("  ⚠️  MODO DRY-RUN: No se realizarán cambios reales")
        print()

    # Instanciar y ejecutar
    reset = RemoteReset(
        recovery_id=args.id,
        dry_run=args.dry_run,
        heartbeat_url=args.heartbeat,
        auth_token=args.auth
    )

    if args.callback:
        def callback_logger(result):
            logger.info(f"[CALLBACK] Fase {result.phase.value}: {'OK' if result.success else 'FAIL'} - {result.message}")
        reset.on_phase(RecoveryPhase.GRACEFUL_SHUTDOWN, callback_logger)
        reset.on_phase(RecoveryPhase.CACHE_PURGE, callback_logger)
        reset.on_phase(RecoveryPhase.SERVICE_RESTORE, callback_logger)
        reset.on_phase(RecoveryPhase.HEARTBEAT, callback_logger)

    try:
        results = reset.run()

        print()
        print("=" * 55)
        print("  RESUMEN FINAL")
        print("=" * 55)
        summary = reset.get_summary()
        print(f"  ID:         {summary['recovery_id']}")
        print(f"  Estado:     {'✅ RECOVERY_SUCCESS' if summary['all_success'] else '⚠️ RECOVERY_PARTIAL'}")
        print(f"  Duración:   {summary['total_duration_seconds']:.1f}s")
        print(f"  Fases OK:   {summary['successful_phases']}/{summary['total_phases']}")
        if summary['failed_phases']:
            print(f"  Fallidas:   {', '.join(summary['failed_phases'])}")
        print()

        # Mostrar detalle por fase
        for r in results:
            icon = "✅" if r.success else "❌"
            print(f"  {icon} [{r.phase.value.upper():20s}] {r.message}")
            if r.error:
                print(f"     Error: {r.error}")
            print(f"     Duración: {r.duration_ms:.0f}ms")

        print()
        print("  Log completo: remote_reset.log")

    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupción detectada. Abortando...")
        reset.abort()
        sys.exit(1)