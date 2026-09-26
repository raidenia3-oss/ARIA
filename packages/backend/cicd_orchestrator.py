"""CI/CD Orchestrator for AURA - Module 30.

Ejecucion automatizada de pruebas unitarias/integracion de los 30 modulos,
verificacion de esquemas de migracion y generacion de reportes de
preparacion para despliegue.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
import py_compile
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from backend.deployment_manager import DeploymentManager, MODULE_FILES


class TestStatus(Enum):
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass
class TestSuiteResult:
    suite_name: str
    status: TestStatus
    passed: int = 0
    failed: int = 0
    duration_ms: float = 0.0
    errors: List[str] = field(default_factory=list)


@dataclass
class MigrationStatus:
    current_revision: Optional[str]
    head_revision: Optional[str]
    up_to_date: bool
    pending_files: List[str] = field(default_factory=list)


class AutomatedTestSuiteRunner:
    """Ejecuta pruebas unitarias/integracion de los 30 modulos de AURA."""

    def __init__(self, module_files: Optional[List[str]] = None) -> None:
        self.module_files: List[str] = module_files or list(MODULE_FILES)
        self.results: List[TestSuiteResult] = []
        self.start_time: str = ""

    def run_compilation_check(self, module_files: Optional[List[str]] = None) -> TestSuiteResult:
        files = module_files or self.module_files
        errors: List[str] = []
        passed = 0
        failed = 0
        start = time.time()

        for filepath in files:
            if not os.path.exists(filepath):
                errors.append(f"{filepath}: file not found (skipped)")
                continue
            try:
                py_compile.compile(filepath, doraise=True)
                passed += 1
            except py_compile.PyCompileError as exc:
                failed += 1
                errors.append(f"{filepath}: {exc}")

        duration = round((time.time() - start) * 1000, 2)
        status = TestStatus.PASSED if failed == 0 else (TestStatus.ERROR if passed > 0 else TestStatus.FAILED)

        result = TestSuiteResult(
            suite_name="compilation_check",
            status=status,
            passed=passed,
            failed=failed,
            duration_ms=duration,
            errors=errors,
        )
        self.results.append(result)
        return result

    def run_unit_tests(self, module_name: str) -> TestSuiteResult:
        start = time.time()
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "pytest", f"--pyargs", f"backend.{module_name}", "-q", "--tb=short"],
                capture_output=True,
                text=True,
                timeout=120,
            )
            passed = len(proc.stdout.strip().splitlines()) if proc.returncode == 0 else 0
            failed = proc.returncode
            status = TestStatus.PASSED if proc.returncode == 0 else TestStatus.FAILED
            errors = [] if proc.returncode == 0 else [proc.stderr.strip()]
        except FileNotFoundError:
            status = TestStatus.SKIPPED
            passed = 0
            failed = 0
            errors = ["pytest not installed"]
        except subprocess.TimeoutExpired:
            status = TestStatus.ERROR
            passed = 0
            failed = 1
            errors = ["test timeout"]

        duration = round((time.time() - start) * 1000, 2)
        result = TestSuiteResult(
            suite_name=f"unit_test_{module_name}",
            status=status,
            passed=passed,
            failed=failed,
            duration_ms=duration,
            errors=errors,
        )
        self.results.append(result)
        return result

    def run_all(self) -> Dict[str, Any]:
        self.start_time = datetime.utcnow().isoformat() + "Z"
        self.results.clear()

        compilation = self.run_compilation_check()

        test_suite_results: List[Dict[str, Any]] = []
        for filepath in self.module_files:
            if not os.path.exists(filepath):
                test_suite_results.append({"module": filepath, "status": "skipped", "reason": "file not found"})
                continue
            module_name = os.path.splitext(os.path.basename(filepath))[0]
            result = self.run_unit_tests(module_name)
            test_suite_results.append({
                "module": filepath,
                "suite": result.suite_name,
                "status": result.status.value,
                "passed": result.passed,
                "failed": result.failed,
                "duration_ms": result.duration_ms,
            })

        total_passed = sum(r.passed for r in self.results)
        total_failed = sum(r.failed for r in self.results)
        total_errors = sum(len(r.errors) for r in self.results)
        total_duration = sum(r.duration_ms for r in self.results)

        return {
            "started_at": self.start_time,
            "completed_at": datetime.utcnow().isoformat() + "Z",
            "compilation": compilation.__dict__,
            "unit_tests": test_suite_results,
            "summary": {
                "total_suites": len(self.results),
                "total_passed": total_passed,
                "total_failed": total_failed,
                "total_errors": total_errors,
                "total_duration_ms": round(total_duration, 2),
            },
        }

    def generate_report(self, results: Optional[Dict[str, Any]] = None) -> str:
        data = results or {"results": [r.__dict__ for r in self.results]}
        lines: List[str] = ["# AURA CI/CD Test Report", f"Generated: {datetime.utcnow().isoformat()}Z", ""]
        if "summary" in data:
            summary = data["summary"]
            lines.append(f"Total suites: {summary['total_suites']}")
            lines.append(f"Passed: {summary['total_passed']}")
            lines.append(f"Failed: {summary['total_failed']}")
            lines.append(f"Errors: {summary['total_errors']}")
            lines.append(f"Duration: {summary['total_duration_ms']}ms")
            lines.append("")
            comp = data.get("compilation", {})
            lines.append(f"Compilation: {comp.get('status', 'n/a')} | passed={comp.get('passed', 0)} failed={comp.get('failed', 0)}")
            lines.append("")
            lines.append("## Module Test Results")
            for item in data.get("unit_tests", []):
                lines.append(f"  - {item['module']}: {item['status']}")
        else:
            for r in self.results:
                lines.append(f"  {r.suite_name}: {r.status.value} (passed={r.passed}, failed={r.failed})")
                for err in r.errors:
                    lines.append(f"    ERROR: {err}")
        return "\n".join(lines)


class MigrationChecker:
    """Verifica esquemas de migracion de base de datos usando Alembic."""

    def __init__(self, alembic_ini: str = "alembic.ini") -> None:
        self.alembic_ini = alembic_ini
        self._current_revision: Optional[str] = None
        self._head_revision: Optional[str] = None

    def check_status(self) -> MigrationStatus:
        current = self._get_current_revision()
        head = self._get_head_revision()
        pending = self._get_pending_migrations()
        up_to_date = (current == head) if (current and head) else False
        status = MigrationStatus(
            current_revision=current,
            head_revision=head,
            up_to_date=up_to_date,
            pending_files=pending,
        )
        self._current_revision = current
        self._head_revision = head
        return status

    def generate_migration(self, name: str = "auto_migration") -> Dict[str, Any]:
        try:
            proc = subprocess.run(
                ["alembic", "revision", "--autogenerate", "-m", name],
                capture_output=True,
                text=True,
                timeout=60,
            )
            success = proc.returncode == 0
            return {
                "success": success,
                "command": "alembic revision --autogenerate",
                "stdout": proc.stdout.strip(),
                "stderr": proc.stderr.strip(),
            }
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            return {
                "success": False,
                "command": "alembic revision",
                "error": str(exc),
            }

    def rollback(self) -> Dict[str, Any]:
        try:
            proc = subprocess.run(
                ["alembic", "downgrade", "-1"],
                capture_output=True,
                text=True,
                timeout=60,
            )
            return {
                "success": proc.returncode == 0,
                "stdout": proc.stdout.strip(),
                "stderr": proc.stderr.strip(),
            }
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            return {"success": False, "error": str(exc)}

    def _get_current_revision(self) -> Optional[str]:
        try:
            proc = subprocess.run(
                ["alembic", "current"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if proc.returncode == 0:
                line = proc.stdout.strip().splitlines()
                return line[0] if line else None
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return None

    def _get_head_revision(self) -> Optional[str]:
        try:
            proc = subprocess.run(
                ["alembic", "heads"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if proc.returncode == 0:
                line = proc.stdout.strip().splitlines()
                return line[0] if line else None
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return None

    def _get_pending_migrations(self) -> List[str]:
        try:
            proc = subprocess.run(
                ["alembic", "history", "--reverse"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if proc.returncode == 0:
                return [l.strip() for l in proc.stdout.strip().splitlines() if l.strip()]
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return []


class PipelineOrchestrator:
    """Orquesta el pipeline CI/CD interno de AURA: lint, test, build, deploy."""

    STAGE_NAMES = ["lint", "test", "build", "deploy"]

    def __init__(self) -> None:
        self.test_runner = AutomatedTestSuiteRunner()
        self.deployment_manager = DeploymentManager()
        self.migration_checker = MigrationChecker()
        self.pipeline_status: Dict[str, Any] = {}
        self.start_time: str = ""

    def lint_stage(self) -> Dict[str, Any]:
        start = time.time()
        result = self.test_runner.run_compilation_check()
        duration = round((time.time() - start) * 1000, 2)
        return {
            "stage": "lint",
            "passed": result.status == TestStatus.PASSED,
            "status": result.status.value,
            "passed_count": result.passed,
            "failed_count": result.failed,
            "errors": result.errors,
            "duration_ms": duration,
        }

    def test_stage(self) -> Dict[str, Any]:
        start = time.time()
        report = self.test_runner.run_all()
        duration = round((time.time() - start) * 1000, 2)
        return {
            "stage": "test",
            "passed": report["summary"]["total_errors"] == 0 and report["summary"]["total_failed"] == 0,
            "status": "passed" if report["summary"]["total_errors"] == 0 else "failed",
            "summary": report["summary"],
            "compilation": report.get("compilation", {}),
            "duration_ms": duration,
        }

    def build_stage(self) -> Dict[str, Any]:
        start = time.time()
        try:
            dockerfile = self.deployment_manager.generate_dockerfile()
            compose = self.deployment_manager.generate_compose()
            duration = round((time.time() - start) * 1000, 2)
            return {
                "stage": "build",
                "passed": True,
                "status": "passed",
                "dockerfile_preview": dockerfile[:200],
                "compose_preview": compose[:200],
                "duration_ms": duration,
            }
        except Exception as exc:
            duration = round((time.time() - start) * 1000, 2)
            return {
                "stage": "build",
                "passed": False,
                "status": "error",
                "error": str(exc),
                "duration_ms": duration,
            }

    def deploy_stage(self) -> Dict[str, Any]:
        start = time.time()
        readiness = self.deployment_manager.readiness()
        migration_status = self.migration_checker.check_status()
        duration = round((time.time() - start) * 1000, 2)
        return {
            "stage": "deploy",
            "passed": readiness.ready and migration_status.up_to_date,
            "status": "ready" if readiness.ready else "not_ready",
            "readiness_ready": readiness.ready,
            "missing_env": readiness.missing_env,
            "migration_up_to_date": migration_status.up_to_date,
            "migration_current": migration_status.current_revision,
            "migration_head": migration_status.head_revision,
            "duration_ms": duration,
        }

    def run_pipeline(self, stages: Optional[List[str]] = None) -> Dict[str, Any]:
        self.start_time = datetime.utcnow().isoformat() + "Z"
        stages = stages or list(self.STAGE_NAMES)
        self.pipeline_status = {"started_at": self.start_time, "stages": []}

        stage_methods = {
            "lint": self.lint_stage,
            "test": self.test_stage,
            "build": self.build_stage,
            "deploy": self.deploy_stage,
        }

        all_passed = True
        timestamp = datetime.utcnow().isoformat() + "Z"

        for stage in stages:
            method = stage_methods.get(stage)
            if method is None:
                result = {"stage": stage, "passed": False, "error": "unknown stage"}
            else:
                try:
                    result = method()
                except Exception as exc:
                    result = {"stage": stage, "passed": False, "error": str(exc)}
            self.pipeline_status["stages"].append(result)
            if not result.get("passed", False):
                all_passed = False
                self.pipeline_status["completed_at"] = datetime.utcnow().isoformat() + "Z"
                self.pipeline_status["overall_status"] = "failed"
                self.pipeline_status["failed_stage"] = stage
                return self.pipeline_status

        self.pipeline_status["completed_at"] = datetime.utcnow().isoformat() + "Z"
        self.pipeline_status["overall_status"] = "passed" if all_passed else "failed"
        self.pipeline_status["report"] = self.test_runner.generate_report()
        return self.pipeline_status

    def get_status(self) -> Dict[str, Any]:
        if not self.pipeline_status:
            return {"status": "not_run", "message": "Pipeline has not been executed yet"}
        return self.pipeline_status

    def system_report(self) -> Dict[str, Any]:
        """Genera reporte maestro consolidado de los 30 modulos."""
        start = time.time()
        deployment = self.deployment_manager
        readiness = deployment.readiness()
        probes = deployment.run_health_probes()
        env = deployment.env_validator.validate()
        migration = self.migration_checker.check_status()

        module_status: List[Dict[str, Any]] = []
        for filepath in MODULE_FILES:
            exists = os.path.exists(filepath)
            module_name = os.path.splitext(os.path.basename(filepath))[0]
            compiles = False
            if exists:
                try:
                    py_compile.compile(filepath, doraise=True)
                    compiles = True
                except py_compile.PyCompileError:
                    compiles = False
            module_status.append({
                "file": filepath,
                "module": module_name,
                "exists": exists,
                "compiles": compiles,
            })

        total_modules = len(MODULE_FILES)
        existing_modules = sum(1 for m in module_status if m["exists"])
        compiled_modules = sum(1 for m in module_status if m["compiles"])
        duration = round((time.time() - start) * 1000, 2)

        return {
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "system_name": "AURA - Autonomous Unified Reasoning Architecture",
            "total_modules": total_modules,
            "existing_modules": existing_modules,
            "compiled_modules": compiled_modules,
            "readiness": {
                "ready": readiness.ready,
                "missing_env": readiness.missing_env,
                "checks": [c.__dict__ for c in readiness.checks],
            },
            "probes": probes,
            "environment": env,
            "migration": {
                "current_revision": migration.current_revision,
                "head_revision": migration.head_revision,
                "up_to_date": migration.up_to_date,
            },
            "modules": module_status,
            "duration_ms": duration,
        }
