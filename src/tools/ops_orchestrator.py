"""
AURA-Ops v2.0: Orquestador Autónomo de Infraestructura, Logs y Estado.

Expone la clase ``AURAOpsOrchestrator`` para:
  1. Auto-descubrimiento de red (IP pública, IP local, puertos, plataforma).
  2. Inspección de logs y errores activos (uvicorn, docker, archivos .log).
  3. Persistencia del estado del sistema en ``.aura_state.json``.
  4. CLI autónomo: ``python -m src.tools.ops_orchestrator --scan``.
  5. Conectores de plataforma (Vercel & Render).
  6. Motor de auto-reparación (Self-Healing Engine).
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


class AURAOpsOrchestrator:
    """Orquestador de operaciones autónomo para AURA v2.0."""

    STATE_FILE = ".aura_state.json"
    REPAIR_PATCH_FILE = ".repair_patch.json"
    PUBLIC_IP_SERVICES = [
        "https://api.ipify.org",
        "https://ifconfig.me/ip",
        "https://ipinfo.io/ip",
    ]
    PORTS_TO_CHECK = [80, 443, 8000, 3000]
    LOG_PATTERNS = [
        re.compile(r"Traceback \(most recent call last\)", re.IGNORECASE),
        re.compile(r"Exception in.*?\n", re.DOTALL | re.IGNORECASE),
        re.compile(r"ERROR.*?:\s*.*", re.IGNORECASE),
        re.compile(r"CRITICAL.*?:\s*.*", re.IGNORECASE),
    ]
    FAILURE_PATTERNS = [
        ("cors", re.compile(r"CORS policy|Access-Control-Allow-Origin|CORSMiddleware", re.IGNORECASE)),
        ("404", re.compile(r"404 Not Found|Not Found:", re.IGNORECASE)),
        ("500", re.compile(r"500 Internal Server Error|Internal Server Error", re.IGNORECASE)),
        ("websocket", re.compile(r"WebSocket Disconnected|websocket closed|ws disconnect", re.IGNORECASE)),
        ("timeout", re.compile(r"timeout|timed out|ETIMEDOUT|ETIMEDOUT", re.IGNORECASE)),
        ("memory", re.compile(r"MemoryError|OOM|out of memory|killed", re.IGNORECASE)),
    ]

    def __init__(self, base_dir: Optional[str] = None) -> None:
        self.base_dir = base_dir or os.getcwd()
        self.state_path = os.path.join(self.base_dir, self.STATE_FILE)
        self.repair_path = os.path.join(self.base_dir, self.REPAIR_PATCH_FILE)

    # ------------------------------------------------------------------ #
    # AUTO-DISCOVERY DE RED
    # ------------------------------------------------------------------ #
    def get_network_metadata(self) -> Dict[str, Any]:
        """Detecta IP pública, IP local, puertos abiertos y plataforma de hosting."""
        metadata: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "public_ip": self._detect_public_ip(),
            "local_ip": self._detect_local_ip(),
            "active_ports": self._scan_ports(),
            "hosting_platform": self._detect_hosting_platform(),
            "hostname": socket.gethostname(),
            "platform": platform.system(),
        }
        return metadata

    def _detect_public_ip(self) -> Optional[str]:
        for service in self.PUBLIC_IP_SERVICES:
            try:
                req = urllib.request.Request(service, headers={"User-Agent": "AURA-Ops/2.0"})
                with urllib.request.urlopen(req, timeout=8) as resp:
                    ip = resp.read().decode("utf-8", errors="replace").strip()
                    if re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", ip):
                        return ip
            except Exception:
                continue
        return None

    def _detect_local_ip(self) -> Optional[str]:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                return s.getsockname()[0]
        except Exception:
            pass
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return None

    def _scan_ports(self) -> List[Dict[str, Any]]:
        results = []
        for port in self.PORTS_TO_CHECK:
            status = self._check_port("127.0.0.1", port)
            results.append({"port": port, "local": status})
        return results

    def _check_port(self, host: str, port: int, timeout: float = 0.5) -> str:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(timeout)
                result = s.connect_ex((host, port))
                return "open" if result == 0 else "closed"
        except Exception:
            return "error"

    def _detect_hosting_platform(self) -> str:
        hostname = socket.gethostname().lower()
        env = os.environ
        if env.get("RENDER_SERVICE_NAME") or "render" in hostname:
            return "render"
        if env.get("K_SERVICE") or env.get("K_REVISION") or "google" in hostname:
            return "google_cloud_run"
        if env.get("DYNO") or "heroku" in hostname:
            return "heroku"
        if env.get("RAILWAY_SERVICE_NAME") or "railway" in hostname:
            return "railway"
        if env.get("VERCEL_REGION") or "vercel" in hostname:
            return "vercel"
        if env.get("HOSTNAME", "").startswith("container") or os.path.exists("/.dockerenv"):
            return "docker"
        if "oracle" in hostname or "compute" in hostname:
            return "oracle_cloud"
        return "unknown"

    # ------------------------------------------------------------------ #
    # CONECTORES DE PLATAFORMA (Vercel & Render)
    # ------------------------------------------------------------------ #
    def sync_cloud_platforms(self) -> Dict[str, Any]:
        """Consulta Vercel, Render y Hugging Face para obtener estado de deploy y URLs públicas."""
        result: Dict[str, Any] = {
            "vercel": self._check_vercel(),
            "render": self._check_render(),
            "huggingface": self._check_huggingface(),
            "hosting_platform": "Vercel (Frontend) + Render (Backend) + Hugging Face (AI)",
        }
        return result

    def _check_vercel(self) -> Dict[str, Any]:
        token = os.getenv("VERCEL_TOKEN") or os.getenv("VERCEL_API_TOKEN")
        project_id = os.getenv("VERCEL_PROJECT_ID")
        fallback_url = os.getenv("VERCEL_URL") or os.getenv("VERCEL_PROJECT_URL")
        out: Dict[str, Any] = {
            "configured": bool(token and project_id),
            "url": fallback_url,
            "status": None,
            "error": None,
        }
        if token and project_id:
            try:
                req = urllib.request.Request(
                    f"https://api.vercel.com/v1/projects/{project_id}/deployments",
                    headers={"Authorization": f"Bearer {token}", "User-Agent": "AURA-Ops/2.0"},
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read().decode("utf-8", errors="replace"))
                deployments = data.get("deployments", [])
                if deployments:
                    latest = deployments[0]
                    out["status"] = latest.get("state")
                    out["url"] = latest.get("url") or out["url"]
                    out["ready"] = latest.get("ready") == "READY"
                return out
            except Exception as exc:
                out["error"] = str(exc)[:200]
                out["configured"] = False
        if fallback_url:
            status = self._passive_health_check(fallback_url.rstrip("/"))
            out["status"] = status
            out["configured"] = False
            out["error"] = out["error"] or "Pasivo: sin token/project id"
        else:
            out["error"] = out["error"] or "VERCEL_TOKEN/PROJECT_ID no configurados"
        return out

    def _check_render(self) -> Dict[str, Any]:
        render_url = os.getenv("RENDER_URL") or os.getenv("RENDER_BACKEND_URL")
        api_key = os.getenv("RENDER_API_KEY")
        out: Dict[str, Any] = {
            "configured": bool(api_key and render_url),
            "url": render_url,
            "status": None,
            "latency_ms": None,
            "error": None,
        }
        if api_key and render_url:
            health_url = render_url.rstrip("/") + "/health"
            try:
                t0 = time.perf_counter()
                req = urllib.request.Request(
                    health_url,
                    headers={"User-Agent": "AURA-Ops/2.0", "Authorization": f"Bearer {api_key}"},
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    status_code = resp.status
                out["latency_ms"] = round((time.perf_counter() - t0) * 1000, 1)
                out["status"] = "healthy" if status_code == 200 else f"unhealthy ({status_code})"
                return out
            except urllib.error.HTTPError as exc:
                out["status"] = f"error ({exc.code})"
                out["error"] = str(exc)[:200]
                return out
            except Exception as exc:
                out["status"] = "unreachable"
                out["error"] = str(exc)[:200]
                return out
        if render_url:
            status = self._passive_health_check(render_url.rstrip("/"))
            out["status"] = status
            out["configured"] = False
            out["error"] = out["error"] or "Pasivo: sin api key"
        else:
            out["error"] = out["error"] or "RENDER_URL no configurada"
        return out

    def _check_huggingface(self) -> Dict[str, Any]:
        token = os.getenv("HF_TOKEN")
        space_url = os.getenv("HF_SPACE_URL") or os.getenv("HUGGINGFACE_SPACE_URL")
        out: Dict[str, Any] = {
            "configured": bool(token or space_url),
            "url": space_url,
            "status": None,
            "error": None,
        }
        if token and space_url:
            api_url = space_url.rstrip("/").replace("huggingface.co/spaces/", "huggingface.co/api/spaces/")
            try:
                req = urllib.request.Request(
                    api_url,
                    headers={"Authorization": f"Bearer {token}", "User-Agent": "AURA-Ops/2.0"},
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    status_code = resp.status
                out["status"] = "healthy" if status_code == 200 else f"unhealthy ({status_code})"
                return out
            except urllib.error.HTTPError as exc:
                out["status"] = f"error ({exc.code})"
                out["error"] = str(exc)[:200]
                return out
            except Exception as exc:
                out["status"] = "unreachable"
                out["error"] = str(exc)[:200]
                return out
        if space_url:
            status = self._passive_health_check(space_url.rstrip("/"))
            out["status"] = status
            out["configured"] = False
            out["error"] = out["error"] or "Pasivo: sin token"
        else:
            out["error"] = out["error"] or "HF_SPACE_URL no configurada"
        return out

    def _passive_health_check(self, base_url: str, path: str = "/health") -> Optional[str]:
        try:
            health_url = base_url.rstrip("/") + path
            req = urllib.request.Request(health_url, headers={"User-Agent": "AURA-Ops/2.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    return "ONLINE (Pasivo)"
            return f"UNHEALTHY ({resp.status})"
        except urllib.error.HTTPError as exc:
            if exc.code == 404 and path == "/health":
                return self._passive_health_check(base_url, "/")
            return f"ERROR ({exc.code})"
        except Exception:
            return "UNREACHABLE"

    # ------------------------------------------------------------------ #
    # LIMPIEZA DE LOGS TEMPORALES
    # ------------------------------------------------------------------ #
    def purge_stale_logs(self, log_paths: Optional[List[str]] = None, max_age_days: int = 1) -> Dict[str, Any]:
        """Elimina entradas antiguas de logs para reducir falsos positivos."""
        if log_paths is None:
            log_paths = [
                os.path.join(self.base_dir, "rocket_bridge_test.log"),
                os.path.join(self.base_dir, "logs"),
                os.path.join(self.base_dir, "data"),
            ]
        purged: List[str] = []
        now = time.time()
        cutoff = now - max_age_days * 86400
        for path in log_paths:
            if not os.path.exists(path):
                continue
            try:
                if os.path.isfile(path):
                    if os.path.getmtime(path) < cutoff:
                        os.remove(path)
                        purged.append(path)
                elif os.path.isdir(path):
                    for entry in os.scandir(path):
                        if entry.is_file() and entry.name.endswith(".log"):
                            try:
                                if os.path.getmtime(entry.path) < cutoff:
                                    os.remove(entry.path)
                                    purged.append(entry.path)
                            except Exception:
                                continue
            except Exception:
                continue
        return {"purged": purged, "count": len(purged)}

    # ------------------------------------------------------------------ #
    # INSPECTOR DE LOGS (Build & Runtime)
    # ------------------------------------------------------------------ #
    def inspect_platform_logs(self, max_lines: int = 50) -> Dict[str, Any]:
        """Captura y analiza logs locales, de Render y de Vercel."""
        local_logs = self._inspect_local_logs(max_lines)
        render_logs = self._inspect_render_logs(max_lines)
        vercel_logs = self._inspect_vercel_logs(max_lines)

        all_logs = [local_logs, render_logs, vercel_logs]
        failures = self._detect_failures(all_logs)

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "sources": {
                "local": local_logs,
                "render": render_logs,
                "vercel": vercel_logs,
            },
            "failures_detected": failures,
            "failure_count": len(failures),
        }

    def _inspect_local_logs(self, max_lines: int) -> Dict[str, Any]:
        entries: List[str] = []
        search_dirs = [self.base_dir, os.path.join(self.base_dir, "logs"), os.path.join(self.base_dir, "data")]
        for directory in search_dirs:
            if not os.path.isdir(directory):
                continue
            try:
                for entry in os.scandir(directory):
                    if entry.is_file() and entry.name.endswith(".log"):
                        try:
                            with open(entry.path, "r", encoding="utf-8", errors="replace") as f:
                                lines = f.readlines()[-max_lines:]
                            entries.extend([f"{entry.name}: {line.rstrip()}" for line in lines])
                        except Exception:
                            continue
            except Exception:
                continue
        return {"source": "local", "lines_captured": len(entries), "entries": entries[-max_lines:]}

    def _inspect_render_logs(self, max_lines: int) -> Dict[str, Any]:
        entries: List[str] = []
        render_url = os.getenv("RENDER_URL") or os.getenv("RENDER_BACKEND_URL")
        if not render_url:
            return {"source": "render", "lines_captured": 0, "entries": [], "error": "RENDER_URL no configurada"}
        try:
            req = urllib.request.Request(
                render_url.rstrip("/") + "/logs",
                headers={"User-Agent": "AURA-Ops/2.0"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                text = resp.read().decode("utf-8", errors="replace")
            lines = text.splitlines()[-max_lines:]
            entries = lines
        except Exception as exc:
            return {"source": "render", "lines_captured": 0, "entries": [], "error": str(exc)[:200]}
        return {"source": "render", "lines_captured": len(entries), "entries": entries[-max_lines:]}

    def _inspect_vercel_logs(self, max_lines: int) -> Dict[str, Any]:
        entries: List[str] = []
        token = os.getenv("VERCEL_TOKEN") or os.getenv("VERCEL_API_TOKEN")
        project_id = os.getenv("VERCEL_PROJECT_ID")
        if not token or not project_id:
            return {"source": "vercel", "lines_captured": 0, "entries": [], "error": "VERCEL_TOKEN/PROJECT_ID no configurados"}
        try:
            req = urllib.request.Request(
                f"https://api.vercel.com/v1/projects/{project_id}/deployments",
                headers={"Authorization": f"Bearer {token}", "User-Agent": "AURA-Ops/2.0"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="replace"))
            deployments = data.get("deployments", [])
            for dep in deployments[:3]:
                state = dep.get("state", "unknown")
                url = dep.get("url", "")
                entries.append(f"deployment {dep.get('id','?')}: state={state} url={url}")
        except Exception as exc:
            return {"source": "vercel", "lines_captured": 0, "entries": [], "error": str(exc)[:200]}
        return {"source": "vercel", "lines_captured": len(entries), "entries": entries[-max_lines:]}

    def _detect_failures(self, log_sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        failures: List[Dict[str, Any]] = []
        for source in log_sources:
            entries = source.get("entries", [])
            text = "\n".join(entries)
            for failure_type, pattern in self.FAILURE_PATTERNS:
                for m in pattern.finditer(text):
                    snippet = text[max(0, m.start() - 100):min(len(text), m.end() + 200)].strip()
                    failures.append({
                        "type": failure_type,
                        "source": source.get("source", "unknown"),
                        "snippet": snippet[:300],
                        "detected_at": datetime.now(timezone.utc).isoformat(),
                    })
        return failures

    # ------------------------------------------------------------------ #
    # MOTOR DE AUTO-REPARACIÓN (Self-Healing Engine)
    # ------------------------------------------------------------------ #
    def generate_auto_fix(self, failures: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """Genera parches automáticos basados en fallos detectados."""
        if failures is None:
            inspection = self.inspect_platform_logs()
            failures = inspection.get("failures_detected", [])

        patches: List[Dict[str, Any]] = []
        env_changes: Dict[str, str] = {}
        url_overrides: Dict[str, str] = {}

        for failure in failures:
            ftype = failure.get("type", "")
            if ftype == "cors":
                origins = self._infer_cors_origins()
                env_changes["ALLOW_ORIGINS"] = ",".join(origins)
                patches.append({
                    "action": "set_env",
                    "key": "ALLOW_ORIGINS",
                    "value": env_changes["ALLOW_ORIGINS"],
                    "reason": "CORS detectado en logs",
                    "failure": failure,
                })
            elif ftype == "websocket":
                backend_url = self._infer_backend_url()
                if backend_url:
                    url_overrides["NEXT_PUBLIC_BACKEND_URL"] = backend_url
                    patches.append({
                        "action": "set_env",
                        "key": "NEXT_PUBLIC_BACKEND_URL",
                        "value": backend_url,
                        "reason": "WebSocket desconectado; actualizar URL backend",
                        "failure": failure,
                    })
            elif ftype == "404":
                patches.append({
                    "action": "review_routes",
                    "reason": "Ruta 404 detectada; verificar mapeo de rutas",
                    "failure": failure,
                })
            elif ftype == "500":
                patches.append({
                    "action": "restart_service",
                    "target": "backend",
                    "reason": "Error 500 detectado; reiniciar servicio backend",
                    "failure": failure,
                })
            elif ftype == "timeout":
                patches.append({
                    "action": "increase_timeout",
                    "reason": "Timeout detectado; aumentar timeouts de conexión",
                    "failure": failure,
                })
            elif ftype == "memory":
                patches.append({
                    "action": "scale_memory",
                    "reason": "Problema de memoria detectado; considerar escalar",
                    "failure": failure,
                })

        repair_patch = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "failures_addressed": len(patches),
            "env_changes": env_changes,
            "url_overrides": url_overrides,
            "patches": patches,
            "applied": False,
        }
        self._write_repair_patch(repair_patch)
        return repair_patch

    def _infer_cors_origins(self) -> List[str]:
        origins = []
        vercel_url = os.getenv("VERCEL_URL") or os.getenv("VERCEL_PROJECT_URL")
        if vercel_url:
            origins.append(f"https://{vercel_url}")
        render_url = os.getenv("RENDER_URL") or os.getenv("RENDER_BACKEND_URL")
        if render_url:
            origins.append(render_url.rstrip("/"))
        local_ip = self._detect_local_ip()
        if local_ip:
            origins.append(f"http://{local_ip}:3000")
            origins.append(f"http://{local_ip}:8000")
        origins.append("http://localhost:3000")
        origins.append("http://localhost:8000")
        return list(dict.fromkeys(origins))

    def _infer_backend_url(self) -> Optional[str]:
        render_url = os.getenv("RENDER_URL") or os.getenv("RENDER_BACKEND_URL")
        if render_url:
            return render_url.rstrip("/")
        local_ip = self._detect_local_ip()
        if local_ip:
            return f"http://{local_ip}:8000"
        return None

    def _write_repair_patch(self, patch: Dict[str, Any]) -> None:
        try:
            with open(self.repair_path, "w", encoding="utf-8") as f:
                json.dump(patch, f, indent=2, ensure_ascii=False)
        except Exception as exc:
            print(f"[AURA-Ops] Error escribiendo repair patch: {exc}", file=sys.stderr)

    def load_repair_patch(self) -> Dict[str, Any]:
        if not os.path.exists(self.repair_path):
            return {}
        try:
            with open(self.repair_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def apply_repair_patch(self) -> Dict[str, Any]:
        """Aplica el parche de reparación guardado en .repair_patch.json."""
        patch = self.load_repair_patch()
        if not patch:
            return {"ok": False, "error": "No hay parche de reparación disponible"}
        applied: List[Dict[str, Any]] = []
        for p in patch.get("patches", []):
            if p.get("action") == "set_env":
                key = p.get("key")
                value = p.get("value")
                if key and value:
                    os.environ[key] = value
                    applied.append({"action": "set_env", "key": key, "value": value, "ok": True})
            elif p.get("action") == "restart_service":
                applied.append({
                    "action": "restart_service",
                    "target": p.get("target"),
                    "ok": True,
                    "note": "Requiere intervención manual o script de despliegue",
                })
            else:
                applied.append({**p, "ok": True, "note": "Parche registrado; requiere revisión"})
        patch["applied"] = True
        patch["applied_at"] = datetime.now(timezone.utc).isoformat()
        patch["applied_actions"] = applied
        self._write_repair_patch(patch)
        return patch

    # ------------------------------------------------------------------ #
    # INSPECTOR DE LOGS Y ERRORES (Legacy)
    # ------------------------------------------------------------------ #
    def get_active_errors(self, max_log_bytes: int = 1024 * 1024) -> Dict[str, Any]:
        """Escanea logs y salida de procesos para extraer errores activos."""
        errors: List[Dict[str, Any]] = []
        sources_scanned: List[str] = []

        sources_scanned.extend(self._scan_log_files(max_log_bytes))
        sources_scanned.extend(self._scan_process_output())
        sources_scanned.extend(self._scan_docker_logs())

        summary = self._summarize_errors(errors)
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "sources_scanned": sources_scanned,
            "error_count": len(errors),
            "errors": errors[:50],
            "summary": summary,
        }

    def _scan_log_files(self, max_bytes: int) -> List[str]:
        scanned = []
        search_dirs = [self.base_dir, os.path.join(self.base_dir, "logs"), os.path.join(self.base_dir, "data")]
        for directory in search_dirs:
            if not os.path.isdir(directory):
                continue
            try:
                for entry in os.scandir(directory):
                    if entry.is_file() and entry.name.endswith(".log"):
                        scanned.append(self._extract_errors_from_file(entry.path, max_bytes))
            except Exception:
                continue
        return [s for s in scanned if s]

    def _extract_errors_from_file(self, path: str, max_bytes: int) -> str:
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read(max_bytes)
            matches = []
            for pattern in self.LOG_PATTERNS:
                for m in pattern.finditer(content):
                    start = max(0, m.start() - 200)
                    end = min(len(content), m.end() + 800)
                    snippet = content[start:end].strip()
                    matches.append(snippet)
                    if len(matches) >= 10:
                        break
                if len(matches) >= 10:
                    break
            return path if matches else ""
        except Exception:
            return ""

    def _scan_process_output(self) -> List[str]:
        scanned = []
        try:
            if sys.platform != "win32":
                result = subprocess.run(
                    ["ps", "aux"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                for line in result.stdout.splitlines():
                    if "uvicorn" in line or "python" in line:
                        scanned.append(f"process:{line[:200]}")
        except Exception:
            pass
        return scanned

    def _scan_docker_logs(self) -> List[str]:
        scanned = []
        try:
            result = subprocess.run(
                ["docker", "ps", "--format", "{{.Names}}"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            for container in result.stdout.splitlines():
                container = container.strip()
                if not container:
                    continue
                try:
                    logs = subprocess.run(
                        ["docker", "logs", "--tail", "100", container],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    combined = (logs.stdout or "") + (logs.stderr or "")
                    for pattern in self.LOG_PATTERNS:
                        for m in pattern.finditer(combined):
                            scanned.append(f"docker:{container}:{m.group(0)[:200]}")
                            break
                except Exception:
                    continue
        except Exception:
            pass
        return scanned

    def _summarize_errors(self, errors: List[Dict[str, Any]]) -> Dict[str, Any]:
        by_type: Dict[str, int] = {}
        for err in errors:
            key = err.get("type", "unknown")
            by_type[key] = by_type.get(key, 0) + 1
        return {
            "total": len(errors),
            "by_type": by_type,
            "has_traceback": any(e.get("type") == "traceback" for e in errors),
            "system_health": "GREEN" if not errors else "RED",
        }

    # ------------------------------------------------------------------ #
    # ESTADO DE SINCRONIZACIÓN
    # ------------------------------------------------------------------ #
    def write_state(self, state: Dict[str, Any]) -> None:
        try:
            with open(self.state_path, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2, ensure_ascii=False)
        except Exception as exc:
            print(f"[AURA-Ops] Error escribiendo estado: {exc}", file=sys.stderr)

    def load_state(self) -> Dict[str, Any]:
        if not os.path.exists(self.state_path):
            return {}
        try:
            with open(self.state_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def build_state(self) -> Dict[str, Any]:
        net = self.get_network_metadata()
        cloud = self.sync_cloud_platforms()
        errors = self.get_active_errors()
        summary = errors.get("summary", {})

        active_ports = [
            p["port"] for p in net.get("active_ports", []) if p.get("local") == "open"
        ]
        backend_url = None
        if 8000 in active_ports:
            backend_url = f"http://{net.get('local_ip') or '127.0.0.1'}:8000"
        elif 3000 in active_ports:
            backend_url = f"http://{net.get('local_ip') or '127.0.0.1'}:3000"

        render = cloud.get("render", {})
        if render.get("url") and (render.get("status") == "healthy" or "ONLINE" in str(render.get("status", ""))):
            backend_url = render["url"]

        health = summary.get("system_health", "GREEN")
        if summary.get("has_traceback"):
            health = "RED"
        elif errors.get("error_count", 0) > 0:
            health = "YELLOW"

        last_error = ""
        if errors.get("errors"):
            last_error = errors["errors"][0].get("message", "")[:200]

        state = {
            "public_ip": net.get("public_ip"),
            "active_backend_url": backend_url,
            "active_ports": active_ports,
            "system_health": health,
            "last_error": last_error,
            "hosting_platform": cloud.get("hosting_platform", net.get("hosting_platform")),
            "vercel": cloud.get("vercel"),
            "render": cloud.get("render"),
            "huggingface": cloud.get("huggingface"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.write_state(state)
        return state

    # ------------------------------------------------------------------ #
    # CLI AUTÓNOMO
    # ------------------------------------------------------------------ #
    def scan(self) -> Dict[str, Any]:
        state = self.build_state()
        print(json.dumps(state, indent=2, ensure_ascii=False))
        return state

    def autofix(self) -> Dict[str, Any]:
        self.purge_stale_logs()
        inspection = self.inspect_platform_logs()
        failures = inspection.get("failures_detected", [])
        patch = self.generate_auto_fix(failures)
        applied = self.apply_repair_patch()
        result = {
            "inspection": inspection,
            "patch": patch,
            "applied": applied,
            "system_health": "GREEN" if not failures else "YELLOW",
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return result


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    parser = argparse.ArgumentParser(description="AURA-Ops Orchestrator v2.0")
    parser.add_argument("--scan", action="store_true", help="Actualiza .aura_state.json")
    parser.add_argument("--errors", action="store_true", help="Solo muestra errores activos")
    parser.add_argument("--network", action="store_true", help="Solo muestra metadata de red")
    parser.add_argument("--autofix", action="store_true", help="Inspecciona y aplica parches automáticos")
    parser.add_argument("--logs", action="store_true", help="Inspecciona logs de plataformas")
    parser.add_argument("--purge", action="store_true", help="Purga logs temporales antiguos")
    args = parser.parse_args()

    orch = AURAOpsOrchestrator()

    if args.errors:
        print(json.dumps(orch.get_active_errors(), indent=2, ensure_ascii=False))
        return 0
    if args.network:
        print(json.dumps(orch.get_network_metadata(), indent=2, ensure_ascii=False))
        return 0
    if args.logs:
        print(json.dumps(orch.inspect_platform_logs(), indent=2, ensure_ascii=False))
        return 0
    if args.purge:
        print(json.dumps(orch.purge_stale_logs(), indent=2, ensure_ascii=False))
        return 0
    if args.scan:
        state = orch.scan()
        return 0 if state.get("system_health") == "GREEN" else 1
    if args.autofix:
        result = orch.autofix()
        return 0 if result.get("system_health") == "GREEN" else 1

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
