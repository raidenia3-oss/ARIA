"""Production routes for AURA - Module 30.

Endpoints REST para probes de liveness/readiness, generacion de especificaciones
Docker/K8s, disparo del pipeline CI/CD interno y reporte maestro del sistema.
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from backend.audit_logger import AuditEvent, AuditEventType, AuditLogger
from backend.deployment_manager import DeploymentManager
from backend.cicd_orchestrator import PipelineOrchestrator

router = APIRouter(prefix="/api/production", tags=["production"])
deployment_manager = DeploymentManager()
audit_logger = AuditLogger()
pipeline_orchestrator = PipelineOrchestrator()


@router.get("/readiness")
async def production_readiness() -> Dict[str, Any]:
    report = deployment_manager.readiness()
    audit_logger.log(AuditEvent(
        event_id=f"readiness-{int(__import__('time').time() * 1000)}",
        event_type=AuditEventType.DEPLOYMENT,
        actor="system",
        action="readiness_check",
        resource="production",
        result="ready" if report.ready else "not_ready",
    ))
    return {
        "ready": report.ready,
        "missing_env": report.missing_env,
        "checks": [c.__dict__ for c in report.checks],
        "timestamp": report.timestamp,
    }


@router.get("/health-check")
async def production_health_check() -> Dict[str, Any]:
    checks = deployment_manager.health_checks()
    return {
        "status": "ok" if all(c.status == "ok" for c in checks) else "degraded",
        "checks": [c.__dict__ for c in checks],
        "timestamp": __import__('datetime').datetime.utcnow().isoformat() + "Z",
    }


@router.get("/deploy-status")
async def production_deploy_status() -> Dict[str, Any]:
    return deployment_manager.deploy_status()


@router.get("/audit-logs")
async def production_audit_logs(limit: int = 100) -> Dict[str, Any]:
    events = audit_logger.history(limit=limit)
    return {"count": len(events), "events": [e.__dict__ for e in events]}


@router.post("/audit-logs/export")
async def production_audit_export(payload: Dict[str, Any]) -> Dict[str, Any]:
    event_type = payload.get("event_type")
    fmt = str(payload.get("format", "json")).lower()
    event_enum = None
    if event_type:
        try:
            event_enum = AuditEventType(str(event_type))
        except ValueError:
            event_enum = None
    if fmt == "csv":
        path = audit_logger.export_csv(event_type=event_enum)
    else:
        path = audit_logger.export_events(event_type=event_enum)
    return {"path": path, "format": fmt}


@router.get("/health")
async def production_health() -> Dict[str, Any]:
    probe_results = deployment_manager.run_health_probes()
    audit_logger.log(AuditEvent(
        event_id=f"health-{int(__import__('time').time() * 1000)}",
        event_type=AuditEventType.HEALTH_CHECK,
        actor="system",
        action="health_probe",
        resource="production",
        result="passed" if probe_results["all_passed"] else "failed",
    ))
    return {
        "status": "healthy" if probe_results["all_passed"] else "degraded",
        "liveness": probe_results["results"]["liveness"],
        "readiness": probe_results["results"]["readiness"],
        "startup": probe_results["results"]["startup"],
        "all_passed": probe_results["all_passed"],
        "timestamp": probe_results["timestamp"],
    }


@router.get("/deploy-spec")
async def get_deploy_spec(
    port: int = 8000,
    jwt_secret: str = "changeme",
    jwt_admin_secret: str = "changeme_admin",
    db_password: str = "aura_secure",
    bridge_secret: str = "bridge_secure",
) -> Dict[str, Any]:
    dockerfile = deployment_manager.generate_dockerfile(port=port)
    compose = deployment_manager.generate_compose(
        port=port,
        jwt_secret=jwt_secret,
        jwt_admin_secret=jwt_admin_secret,
        db_password=db_password,
        bridge_secret=bridge_secret,
    )
    env_template = deployment_manager.generate_env_template()
    return {
        "dockerfile": dockerfile,
        "docker_compose": compose,
        "env_template": env_template,
    }


@router.post("/deploy-spec")
async def create_deploy_spec(payload: Dict[str, Any]) -> Dict[str, Any]:
    port = int(payload.get("port", 8000))
    jwt_secret = str(payload.get("jwt_secret", "changeme"))
    jwt_admin_secret = str(payload.get("jwt_admin_secret", "changeme_admin"))
    db_password = str(payload.get("db_password", "aura_secure"))
    bridge_secret = str(payload.get("bridge_secret", "bridge_secure"))
    output_dir = payload.get("output_dir", ".")
    save = payload.get("save", False)
    extra_env = payload.get("extra_env")

    result: Dict[str, Any] = {
        "dockerfile": deployment_manager.generate_dockerfile(port=port),
        "docker_compose": deployment_manager.generate_compose(
            port=port,
            jwt_secret=jwt_secret,
            jwt_admin_secret=jwt_admin_secret,
            db_password=db_password,
            bridge_secret=bridge_secret,
            extra_env=extra_env,
        ),
        "env_template": deployment_manager.generate_env_template(),
    }

    if save:
        try:
            paths = deployment_manager.docker_generator.save_configs(
                output_dir=output_dir, port=port
            )
            result["saved_paths"] = paths
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Failed to save configs: {exc}")

    audit_logger.log(AuditEvent(
        event_id=f"deploy-spec-{int(__import__('time').time() * 1000)}",
        event_type=AuditEventType.DEPLOYMENT,
        actor="system",
        action="generate_deploy_spec",
        resource="docker_configs",
        result="success" if not save else f"saved_to_{output_dir}",
    ))
    return result


@router.post("/pipeline/run")
async def run_pipeline(payload: Dict[str, Any] = None) -> Dict[str, Any]:
    payload = payload or {}
    stages = payload.get("stages", ["lint", "test", "build", "deploy"])
    result = pipeline_orchestrator.run_pipeline(stages=stages)
    audit_logger.log(AuditEvent(
        event_id=f"pipeline-{int(__import__('time').time() * 1000)}",
        event_type=AuditEventType.DEPLOYMENT,
        actor="system",
        action="ci_cd_pipeline_run",
        resource="production",
        result=result["overall_status"],
    ))
    return result


@router.get("/system-report")
async def system_report() -> Dict[str, Any]:
    report = pipeline_orchestrator.system_report()
    audit_logger.log(AuditEvent(
        event_id=f"sysreport-{int(__import__('time').time() * 1000)}",
        event_type=AuditEventType.SYSTEM,
        actor="system",
        action="master_system_report",
        resource="all_modules",
        result="generated",
    ))
    return report


@router.get("/pipeline/status")
async def pipeline_status() -> Dict[str, Any]:
    return pipeline_orchestrator.get_status()
