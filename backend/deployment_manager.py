"""Deployment manager for AURA - Module 30.

Generacion automatica de Dockerfile y docker-compose.yml, validacion de
variables de entorno y probes de liveness/readiness para produccion.
"""

from __future__ import annotations

import os
import shutil
import socket
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


MODULE_FILES: List[str] = [
    "backend/main.py",
    "backend/query_router.py",
    "backend/narrative_engine.py",
    "backend/narrative_routes.py",
    "backend/mobile_automation_manager.py",
    "backend/mobile_automation_routes.py",
    "backend/self_learning_manager.py",
    "backend/self_learning_routes.py",
    "backend/fanfic_routes.py",
    "backend/analytics_engine.py",
    "backend/cost_manager.py",
    "backend/analytics_routes.py",
    "backend/localization_manager.py",
    "backend/localization_routes.py",
    "backend/security_manager.py",
    "backend/security_routes.py",
    "backend/device_orchestrator.py",
    "backend/device_routes.py",
    "backend/model_manager.py",
    "backend/model_trainer.py",
    "backend/finetuning_routes.py",
    "backend/monitoring_manager.py",
    "backend/monitoring_routes.py",
    "backend/voice_manager.py",
    "backend/voice_routes.py",
    "backend/marketplace_manager.py",
    "backend/marketplace_routes.py",
    "backend/tenant_manager.py",
    "backend/tenant_routes.py",
    "backend/disaster_recovery.py",
    "backend/disaster_routes.py",
    "backend/continuous_improvement.py",
    "backend/spatial_gesture_engine.py",
    "backend/jarvis_interface.py",
    "backend/spatial_routes.py",
    "backend/event_bus.py",
    "backend/webhook_manager.py",
    "backend/integration_routes.py",
    "backend/autonomous_learner.py",
    "backend/self_optimization_engine.py",
    "backend/learning_routes.py",
    "backend/system_unifier.py",
    "backend/unification_routes.py",
    "backend/local_llm_engine.py",
    "backend/character_persona_manager.py",
    "backend/local_network_gateway.py",
    "backend/local_ai_routes.py",
    "backend/plugin_manager.py",
    "backend/webrtc_stream_engine.py",
    "backend/plugin_webrtc_routes.py",
]

REQUIRED_ENV_VARS: List[str] = [
    "DATABASE_URL",
    "JWT_SECRET",
    "JWT_SECRET_ADMIN",
    "BRIDGE_SECRET",
]

OPTIONAL_ENV_VARS: List[str] = [
    "GEMINI_API_KEY",
    "GROQ_API_KEY",
    "OPENROUTER_API_KEY",
    "HF_TOKEN",
    "OLLAMA_HOST",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
]


@dataclass
class HealthCheck:
    name: str
    status: str
    latency_ms: Optional[float] = None
    error: Optional[str] = None
    checked_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


@dataclass
class ReadinessReport:
    ready: bool
    checks: List[HealthCheck]
    missing_env: List[str]
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


@dataclass
class ProbeResult:
    probe: str
    passed: bool
    latency_ms: float
    detail: str = ""


class DockerConfigGenerator:
    """Genera Dockerfile y docker-compose.yml en caliente para despliegue."""

    DOCKERFILE_TEMPLATE = """FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/

EXPOSE {port}

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \\
    CMD python -c "import requests; requests.get('http://localhost:{port}/health')"

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "{port}"]
"""

    COMPOSE_TEMPLATE = """version: '3.8'

services:
  aura-api:
    build: .
    container_name: aura-backend
    ports:
      - "{port}:80"
    environment:
      - DATABASE_URL=postgresql://aura:{db_password}@db:5432/aura
      - JWT_SECRET={jwt_secret}
      - JWT_SECRET_ADMIN={jwt_admin_secret}
      - BRIDGE_SECRET={bridge_secret}
{env_overrides}
    depends_on:
      - db
      - redis
    restart: unless-stopped

  db:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: aura
      POSTGRES_USER: aura
      POSTGRES_PASSWORD: {db_password}
    volumes:
      - db_data:/var/lib/postgresql/data
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    restart: unless-stopped

volumes:
  db_data:
"""

    def __init__(self) -> None:
        self.last_dockerfile: Optional[str] = None
        self.last_compose: Optional[str] = None

    def generate_dockerfile(self, port: int = 8000, base_image: str = "python:3.11-slim") -> str:
        content = self.DOCKERFILE_TEMPLATE.format(port=port)
        content = content.replace("python:3.11-slim", base_image)
        self.last_dockerfile = content
        return content

    def generate_compose(
        self,
        port: int = 8000,
        jwt_secret: str = "changeme",
        jwt_admin_secret: str = "changeme_admin",
        db_password: str = "aura_secure",
        bridge_secret: str = "bridge_secure",
        extra_env: Optional[Dict[str, str]] = None,
    ) -> str:
        env_lines: List[str] = []
        for key in OPTIONAL_ENV_VARS:
            env_lines.append(f"      - {key}={os.getenv(key, 'optional')}")
        if extra_env:
            for k, v in extra_env.items():
                env_lines.append(f"      - {k}={v}")
        env_str = "\n".join(env_lines) if env_lines else ""

        content = self.COMPOSE_TEMPLATE.format(
            port=port,
            db_password=db_password,
            jwt_secret=jwt_secret,
            jwt_admin_secret=jwt_admin_secret,
            bridge_secret=bridge_secret,
            env_overrides=f"      # Optional environment variables\n{env_str}" if env_str else "",
        )
        self.last_compose = content
        return content

    def save_configs(self, output_dir: str = ".", port: int = 8000) -> Dict[str, str]:
        os.makedirs(output_dir, exist_ok=True)
        dockerfile_path = os.path.join(output_dir, "Dockerfile")
        compose_path = os.path.join(output_dir, "docker-compose.yml")
        with open(dockerfile_path, "w") as f:
            f.write(self.generate_dockerfile(port=port))
        with open(compose_path, "w") as f:
            f.write(self.generate_compose(port=port))
        return {"dockerfile": dockerfile_path, "docker_compose": compose_path}

    def last_specs(self) -> Dict[str, Optional[str]]:
        return {"dockerfile": self.last_dockerfile, "docker_compose": self.last_compose}


class EnvironmentValidator:
    """Valida variables de entorno requeridas y genera plantillas."""

    def __init__(self) -> None:
        self.required_vars: List[str] = list(REQUIRED_ENV_VARS)
        self.optional_vars: List[str] = list(OPTIONAL_ENV_VARS)

    def validate(self) -> Dict[str, Any]:
        missing = [v for v in self.required_vars if not os.getenv(v)]
        present = [v for v in self.required_vars if os.getenv(v)]
        optional_present = [v for v in self.optional_vars if os.getenv(v)]
        return {
            "valid": len(missing) == 0,
            "required_present_count": len(present),
            "required_missing": missing,
            "optional_present": optional_present,
            "optional_missing": [v for v in self.optional_vars if not os.getenv(v)],
        }

    def generate_template(self) -> str:
        lines: List[str] = ["# AURA Environment Configuration", ""]
        lines.append("# === Required ===")
        for var in self.required_vars:
            lines.append(f"{var}=")
        lines.append("\n# === Optional ===")
        for var in self.optional_vars:
            lines.append(f"{var}=")
        return "\n".join(lines)

    def missing_required(self) -> List[str]:
        return [v for v in self.required_vars if not os.getenv(v)]


class HealthCheckProbe:
    """Probes de liveness, readiness y startup para produccion."""

    def __init__(self) -> None:
        self._checks: List[HealthCheck] = []

    def liveness(self) -> ProbeResult:
        start = time.time()
        try:
            _ = socket.gethostname()
            passed = True
            detail = "process responding"
        except Exception as exc:
            passed = False
            detail = str(exc)
        return ProbeResult(
            probe="liveness",
            passed=passed,
            latency_ms=round((time.time() - start) * 1000, 2),
            detail=detail,
        )

    def readiness(self) -> ProbeResult:
        start = time.time()
        try:
            disk = shutil.disk_usage(os.getcwd())
            disk_percent = disk.used / disk.total * 100
            missing_env = [v for v in REQUIRED_ENV_VARS if not os.getenv(v)]
            passed = disk_percent < 95 and len(missing_env) == 0
            detail = f"disk={round(disk_percent, 1)}%, missing_env={missing_env}"
        except Exception as exc:
            passed = False
            detail = str(exc)
        return ProbeResult(
            probe="readiness",
            passed=passed,
            latency_ms=round((time.time() - start) * 1000, 2),
            detail=detail,
        )

    def startup(self) -> ProbeResult:
        start = time.time()
        try:
            import backend
            passed = True
            detail = "backend module importable"
        except Exception as exc:
            passed = False
            detail = str(exc)
        return ProbeResult(
            probe="startup",
            passed=passed,
            latency_ms=round((time.time() - start) * 1000, 2),
            detail=detail,
        )

    def run_all(self) -> Dict[str, Any]:
        results = {
            "liveness": self.liveness().__dict__,
            "readiness": self.readiness().__dict__,
            "startup": self.startup().__dict__,
        }
        all_passed = all(r["passed"] for r in results.values())
        return {
            "all_passed": all_passed,
            "results": results,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }


class DeploymentManager:
    """Verifica preparacion para produccion y genera especificaciones de despliegue."""

    def __init__(self) -> None:
        self.last_report: Optional[ReadinessReport] = None
        self.docker_generator = DockerConfigGenerator()
        self.health_probe = HealthCheckProbe()
        self.env_validator = EnvironmentValidator()

    def readiness(self) -> ReadinessReport:
        checks: List[HealthCheck] = []
        missing_env = self.env_validator.missing_required()

        checks.append(HealthCheck(
            name="env_vars",
            status="ok" if not missing_env else "error",
            error=", ".join(missing_env) if missing_env else None,
        ))

        checks.append(HealthCheck(
            name="disk_space",
            status="ok",
            latency_ms=round(self._disk_check(), 2),
        ))
        checks.append(HealthCheck(name="python_runtime", status="ok"))
        checks.append(HealthCheck(
            name="backend_imports",
            status="ok",
            latency_ms=round(self._import_check(), 2),
        ))

        probe_results = self.health_probe.run_all()
        for probe_name, result in probe_results["results"].items():
            checks.append(HealthCheck(
                name=f"probe_{probe_name}",
                status="ok" if result["passed"] else "error",
                latency_ms=result["latency_ms"],
                error=None if result["passed"] else result["detail"],
            ))

        ready = all(c.status == "ok" for c in checks) and not missing_env
        report = ReadinessReport(ready=ready, checks=checks, missing_env=missing_env)
        self.last_report = report
        return report

    def health_checks(self) -> List[HealthCheck]:
        if self.last_report is None:
            self.readiness()
        return list(self.last_report.checks) if self.last_report else []

    def deploy_status(self) -> Dict[str, Any]:
        probe_status = self.health_probe.run_all()
        env_status = self.env_validator.validate()
        return {
            "status": "ready" if (self.last_report and self.last_report.ready) else "not_ready",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "checks": [c.__dict__ for c in self.health_checks()],
            "probes": probe_status,
            "environment": env_status,
        }

    def generate_dockerfile(self, port: int = 8000, base_image: str = "python:3.11-slim") -> str:
        return self.docker_generator.generate_dockerfile(port=port, base_image=base_image)

    def generate_compose(
        self,
        port: int = 8000,
        jwt_secret: str = "changeme",
        jwt_admin_secret: str = "changeme_admin",
        db_password: str = "aura_secure",
        bridge_secret: str = "bridge_secure",
        extra_env: Optional[Dict[str, str]] = None,
    ) -> str:
        return self.docker_generator.generate_compose(
            port=port,
            jwt_secret=jwt_secret,
            jwt_admin_secret=jwt_admin_secret,
            db_password=db_password,
            bridge_secret=bridge_secret,
            extra_env=extra_env,
        )

    def generate_env_template(self) -> str:
        return self.env_validator.generate_template()

    def run_health_probes(self) -> Dict[str, Any]:
        return self.health_probe.run_all()

    def _missing_env(self) -> List[str]:
        return self.env_validator.missing_required()

    def _disk_check(self) -> float:
        try:
            usage = shutil.disk_usage(os.getcwd())
            return usage.used / usage.total * 100
        except Exception:
            return 0.0

    def _import_check(self) -> float:
        start = time.time()
        try:
            import backend.main
        except Exception:
            pass
        return (time.time() - start) * 1000
