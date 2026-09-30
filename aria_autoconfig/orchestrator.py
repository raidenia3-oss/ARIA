"""Setup orchestrator.

Walks the declared step list in order, applying retry, idempotency and
self-healing uniformly. The orchestrator owns no ARIA-specific logic: it does
not know what pip or cargo are, only that a step returns a `StepResult`.

The step list is the design. Adding a step means appending one entry to
`build_steps()`; there is no second place to update.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Callable

from .configurator import Configurator
from .detector import EnvironmentDetector
from .initializer import REQUIRED_DIRS, Initializer
from .installer import Installer
from .journal import Journal, file_fingerprint, fingerprint
from .model import Environment, Status, StepReport, StepResult, Tier
from .report import Reporter
from .secrets_manager import SecretsManager
from .selfheal import RepairAction, RetryPolicy, SelfHealer
from .validator import Validator

StepFn = Callable[[], StepResult]

REPORT_PATH = Path(".aura") / "setup_report.json"

# Tiers run in this order; a failure only blocks if the tier is CORE.
TIER_ORDER: tuple[str, ...] = (Tier.CORE.value, Tier.RUNTIME.value, Tier.OPTIONAL.value)

# The default run stops before OPTIONAL. That tier installs large native wheels
# (PySide6, aiortc, opencv) totalling hundreds of megabytes, and none of them
# are needed for ARIA to run. They stay opt-in via `--tier optional`, which
# keeps the default promise true: one command, and it finishes.
DEFAULT_TIERS: tuple[str, ...] = (Tier.CORE.value, Tier.RUNTIME.value)


class Orchestrator:
    """Runs the setup pipeline and produces a report."""

    def __init__(
        self,
        env: Environment,
        project_root: Path,
        reporter: Reporter | None = None,
        dry_run: bool = False,
        journal: Journal | None = None,
    ) -> None:
        self.env = env
        self.root = Path(project_root)
        self.reporter = reporter or Reporter()
        self.dry_run = dry_run

        self.detector = EnvironmentDetector(self.root)
        self.journal = journal or Journal(self.root / ".aura" / "setup_state.json")
        self.installer = Installer(self.detector, dry_run=dry_run)
        self.configurator = Configurator(self.root, dry_run=dry_run)
        self.secrets = SecretsManager(self.root, dry_run=dry_run)
        self.initializer = Initializer(self.root, dry_run=dry_run)
        self.validator = Validator(self.detector, dry_run=dry_run)
        self.healer = SelfHealer(self.root, dry_run=dry_run)

        self.retry = RetryPolicy(
            attempts=3,
            on_attempt=lambda attempt, total, reason: self.reporter.hint(f"{reason} (attempt {attempt}/{total})"),
        )

    # ------------------------------------------------------------------ plan

    def build_steps(self, tiers: list[str] | None = None) -> list[tuple[str, Tier, str, StepFn]]:
        """The declarative step list: (name, tier, idem-fingerprint, action).

        The fingerprint is what makes a second run cheap: it is derived from
        the inputs a step actually depends on, so editing `requirements.txt`
        invalidates only the install step.
        """
        if tiers:
            selected = set(tiers)
        else:
            # OPTIONAL is opt-in: it pulls hundreds of megabytes of native
            # wheels that ARIA does not need to run.
            selected = set(DEFAULT_TIERS)
        steps: list[tuple[str, Tier, str, StepFn]] = []

        requirements = [file_fingerprint(p) for p in self.detector.find_requirements_files()]
        manifests = [file_fingerprint(p) for p in self.detector.find_cargo_manifests()]

        if Tier.CORE.value in selected:
            steps.append(
                (
                    "detect_environment",
                    Tier.CORE,
                    fingerprint("detect", self.env.os_name, self.env.python_version),
                    self._step_detect,
                )
            )
            steps.append(
                (
                    "install_core",
                    Tier.CORE,
                    fingerprint("core", requirements),
                    lambda: self.installer.install_python(Tier.CORE.value),
                )
            )
            steps.append(
                (
                    "setup_directories",
                    Tier.CORE,
                    fingerprint("dirs", REQUIRED_DIRS),
                    self.initializer.setup_directories,
                )
            )
            steps.append(
                (
                    "setup_databases",
                    Tier.CORE,
                    fingerprint("db", file_fingerprint(self.root / "aura.db")),
                    self.initializer.setup_databases,
                )
            )
            steps.append(
                (
                    "setup_environment",
                    Tier.CORE,
                    fingerprint("env", self._env_state()),
                    self.configurator.setup_environment,
                )
            )
            steps.append(
                (
                    "ensure_gitignore",
                    Tier.CORE,
                    fingerprint("gitignore", file_fingerprint(self.root / ".gitignore")),
                    self.configurator.ensure_gitignore,
                )
            )

        if Tier.RUNTIME.value in selected:
            steps.append(
                (
                    "install_runtime",
                    Tier.RUNTIME,
                    fingerprint("runtime", requirements),
                    lambda: self.installer.install_python(Tier.RUNTIME.value),
                )
            )
            steps.append(
                (
                    "install_requirements",
                    Tier.RUNTIME,
                    fingerprint("reqs", requirements),
                    self.installer.install_requirements_files,
                )
            )
            steps.append(
                (
                    "build_rust",
                    Tier.RUNTIME,
                    fingerprint("rust", manifests),
                    self.installer.build_rust,
                )
            )
            steps.append(
                (
                    "setup_legacy_databases",
                    Tier.RUNTIME,
                    fingerprint("legacy", file_fingerprint(self.root / "data" / "aura.db")),
                    self.initializer.setup_legacy_databases,
                )
            )

        if Tier.OPTIONAL.value in selected:
            steps.append(
                (
                    "install_optional",
                    Tier.OPTIONAL,
                    fingerprint("optional", requirements),
                    lambda: self.installer.install_python(Tier.OPTIONAL.value),
                )
            )
            steps.append(
                (
                    "setup_secrets",
                    Tier.OPTIONAL,
                    fingerprint("secrets", self._secret_state()),
                    self.secrets.setup_secrets,
                )
            )
            steps.append(
                (
                    "security_audit",
                    Tier.OPTIONAL,
                    fingerprint("audit", self._secret_state()),
                    self.secrets.security_audit,
                )
            )

        return steps

    def _env_state(self) -> str:
        return fingerprint(*[file_fingerprint(p) for p in self.detector.find_env_files()])

    def _secret_state(self) -> str:
        """Fingerprint of secret *presence* only - never their values."""
        return fingerprint(*[(s.name, s.present) for s in self.secrets.audit()])

    # -------------------------------------------------------------- detection

    def _step_detect(self) -> StepResult:
        """Surface missing tools. Never fatal: a missing Rust build is a WARN."""
        missing = list(self.env.missing_tools)
        if not missing:
            return StepResult.ok("all optional tools present", tools=self._tool_versions())
        messages = []
        for tool in missing:
            result = self.installer.install_tool(tool)
            if result.details.get("hint"):
                messages.append(f"{tool}: {result.details['hint']}")
        return StepResult.warn(
            f"{len(missing)} tool(s) not installed",
            missing=missing,
            hints=messages,
        )

    def _tool_versions(self) -> dict[str, str]:
        return {
            "git": self.env.git_version,
            "cargo": self.env.cargo_version,
            "node": self.env.node_version,
            "ollama": ", ".join(self.env.ollama_models[:2]) if self.env.ollama_models else "no models",
        }

    # ------------------------------------------------------------- execution

    def run_full_setup(self, tiers: list[str] | None = None) -> dict:
        """Execute every step, then validate. Returns the run report."""
        self.reporter.header(
            "ARIA Auto-Configuration",
            f"{self.env.os_name} | Python {self.env.python_version} | {self.root}",
        )
        if self.dry_run:
            self.reporter.hint("dry-run: no changes will be written")

        started = time.time()
        reports: list[StepReport] = []
        steps = self.build_steps(tiers)

        for name, tier, print_, action in steps:
            report = self._execute(name, tier, print_, action)
            reports.append(report)
            self.reporter.step(report)
            self._echo_details(report)

            if report.status is Status.FAILED and tier.blocking:
                # A missing core piece makes later steps meaningless; stop and
                # let the operator fix the root cause first.
                self.reporter.hint(f"{name} is required - stopping before dependent steps")
                break

        report = self._finalize(reports, started)
        self.reporter.summary(report)
        self.reporter.write_report(report, self.root / REPORT_PATH)
        self.journal.store_run(report)
        try:
            self.initializer.record_run(report)
        except Exception:  # noqa: BLE001 - audit write must not break the run
            pass
        return report

    def _execute(self, name: str, tier: Tier, print_: str, action: StepFn) -> StepReport:
        """One step: idempotency check, retry, then self-heal if still failing."""
        if self.journal.is_satisfied(name, print_):
            record = self.journal.record_of(name)
            if record is not None and record.status == "warn":
                # Settled as permanently unsatisfiable. Reporting the original
                # reason keeps the warning visible without redoing the work.
                return StepReport(name, tier, Status.WARN, record.message, details={"settled": True})
            return StepReport(name, tier, Status.SKIPPED, "already configured (unchanged)")

        step_started = time.time()
        result, attempts = self.retry.run(name, action)

        # Self-healing: a step that exhausted its retries may be repairable.
        if result.status is Status.FAILED and not self.dry_run:
            for repair in self.healer.repairs_for(name, result)[:2]:
                outcome = repair.attempt()
                if outcome.status.is_terminal_ok and outcome.status is not Status.FAILED:
                    result = StepResult(
                        Status.WARN,
                        f"recovered via repair '{repair.name}': {result.message}",
                        {**result.details, "repair": repair.name},
                    )
                    break

        self.journal.record(
            name,
            print_,
            result.status.value,
            result.message,
            undo=self._undo_payload(name),
            permanent=result.permanent,
        )
        return StepReport(
            name=name,
            tier=tier,
            status=result.status,
            message=result.message,
            attempts=attempts,
            duration_s=time.time() - step_started,
            details=result.details,
        )

    def _undo_payload(self, name: str) -> dict:
        """What a rollback would need to undo this step."""
        if name in {"setup_environment", "ensure_gitignore"}:
            return {"kind": "file_backup", "path": str(self.root / ".gitignore")}
        if name == "setup_databases":
            return {"kind": "db_create_only", "path": str(self.root / "aura.db")}
        if name.startswith("install"):
            return {"kind": "pip_install", "reversible": False}
        return {}

    def _echo_details(self, report: StepReport) -> None:
        for key in ("missing", "hints", "created", "packages", "files", "results", "issues", "missing_secrets"):
            if key in report.details:
                value = report.details[key]
                if isinstance(value, list) and len(value) > 6:
                    self.reporter.detail(key, value[:6] + [f"... +{len(value) - 6} more"])
                else:
                    self.reporter.detail(key, value)
        if report.status is Status.WARN and report.details.get("hint"):
            self.reporter.hint(str(report.details["hint"]))

    # ------------------------------------------------------------ validation

    def validate(self, tiers: list[str] | None = None) -> dict:
        """Run the checks without changing anything."""
        self.reporter.header("ARIA Validation", f"{self.root}")
        self.reporter.rule("checks")

        results = self.validator.validate_all(tiers)
        reports: list[StepReport] = []
        for name, result in results.items():
            reports.append(
                StepReport(name, Tier.OPTIONAL, result.status, result.message, details=result.details)
            )
            self.reporter.step(reports[-1])

        problems = [r for r in reports if r.status is Status.FAILED]
        report = {
            "mode": "validate",
            "success": not problems,
            "environment": self.env.to_dict(),
            "ports": self.validator.scan_ports(),
            "steps": [r.to_dict() for r in reports],
            "duration_s": 0.0,
        }
        self.reporter.summary(report)
        return report

    def diagnose(self) -> dict:
        """Explain the current state: what ran, what is pending, what is wrong."""
        self.reporter.header("ARIA Diagnostics", f"{self.root}")
        self.reporter.rule("journal")
        self.reporter.detail("state file", str(self.journal.path))
        self.reporter.detail("loaded", self.journal.source)
        completed = self.journal.completed_steps()
        self.reporter.detail("completed", completed or "none")

        self.reporter.rule("last run")
        last = self.journal.last_run
        if last:
            self.reporter.detail("finished", last.get("finished_at", "unknown"))
            self.reporter.detail("success", last.get("success"))
            self.reporter.detail("duration_s", last.get("duration_s"))
        else:
            self.reporter.detail("last run", "none recorded")

        self.reporter.rule("secrets")
        for status in self.secrets.audit():
            mark = "present" if status.present else "MISSING"
            self.reporter.write(
                f"  {status.name.ljust(24)} {mark.ljust(8)} {self.reporter.paint(status.how, 'dim')}"
            )
        pending = self.secrets.pending_requests()
        if pending:
            self.reporter.hint(f"{len(pending)} secret(s) requested and still pending")

        self.reporter.rule("services")
        for name, port in self.validator.scan_ports().items():
            mark = "up" if port else "down"
            self.reporter.write(f"  {name.ljust(20)} {mark.ljust(6)}")

        return {
            "mode": "diagnose",
            "journal": self.journal.last_run,
            "environment": self.env.to_dict(),
            "secrets": [s.to_dict() for s in self.secrets.audit()],
            "ports": self.validator.scan_ports(),
            "completed_steps": completed,
        }

    # ---------------------------------------------------------------- report

    def _finalize(self, reports: list[StepReport], started: float) -> dict:
        validation = self.validator.validate_all()
        validation_reports = [
            StepReport(name, Tier.OPTIONAL, result.status, result.message, details=result.details)
            for name, result in validation.items()
        ]

        self.reporter.rule("validation")
        for report in validation_reports:
            self.reporter.step(report)

        core_failed = [
            r for r in reports if r.tier.blocking and r.status is Status.FAILED
        ]
        check_failed = [r for r in validation_reports if r.status is Status.FAILED]

        # Credential exposure is the one non-core failure that must not be
        # filed as "complete": a leaked token is unrecoverable once pushed.
        exposure = [
            r for r in validation_reports if r.name == "credentials" and r.status is Status.FAILED
        ]

        return {
            "mode": "setup",
            "success": not core_failed and not check_failed and not exposure,
            "finished_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "duration_s": round(time.time() - started, 2),
            "environment": self.env.to_dict(),
            "dry_run": self.dry_run,
            "steps": [r.to_dict() for r in reports],
            "validation": [r.to_dict() for r in validation_reports],
            "ports": self.validator.scan_ports(),
            "blocked_by": [r.name for r in core_failed] or [r.name for r in check_failed] or [r.name for r in exposure],
        }

    # --------------------------------------------------------------- rollback

    def rollback(self, steps: list[str] | None = None) -> list[StepReport]:
        """Undo recorded steps in reverse order.

        Only steps whose action is genuinely reversible are undone. A pip
        install is reported as irreversible rather than pretended away.
        """
        self.reporter.header("ARIA Rollback", "undoing the most recent recorded changes")
        names = steps or list(self.journal.completed_steps())
        reports: list[StepReport] = []

        for name in reversed(names):
            undo = self.journal.undo_for(name)
            kind = undo.get("kind", "none")
            if kind in {"pip_install"}:
                result = StepResult.warn(
                    f"{name} installed packages; not automatically reversible",
                    hint="remove the package manually if needed",
                )
                status = Status.WARN
            elif kind == "file_backup":
                result = StepResult.skip("no backup captured during this run")
                status = Status.SKIPPED
            else:
                result = StepResult.skip(f"nothing to undo for {name}")
                status = Status.SKIPPED
            self.journal.forget(name)
            reports.append(StepReport(name, Tier.OPTIONAL, status, result.message, details=result.details))
            self.reporter.step(reports[-1])

        return reports
