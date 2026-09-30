"""ARIA auto-configuration engine.

Zero-touch setup: one command detects the host, installs what is missing,
creates configuration, initialises state and validates the result.

    from aria_autoconfig import Orchestrator, EnvironmentDetector

    env = EnvironmentDetector().detect()
    report = Orchestrator(env, Path.cwd()).run_full_setup()

Design contract, enforced by the modules in this package:
  * Idempotent - a second run changes nothing and costs seconds, not minutes.
  * Declarative - steps are declared, so validate/diagnose need no second path.
  * Non-blocking - an optional failure warns; only CORE can stop a run.
  * Honest - a check that cannot run reports SKIPPED with the reason, never OK.
"""

from __future__ import annotations

from .configurator import Configurator
from .detector import EnvironmentDetector, env_value_looks_real, read_env_keys
from .initializer import Initializer
from .installer import Installer
from .journal import Journal
from .model import Environment, Status, StepReport, StepResult, Tier
from .orchestrator import Orchestrator
from .report import Reporter
from .secrets_manager import SecretsManager
from .selfheal import RetryPolicy, SelfHealer
from .validator import Validator

__version__ = "1.0.0"

__all__ = [
    "Configurator",
    "Environment",
    "EnvironmentDetector",
    "Initializer",
    "Installer",
    "Journal",
    "Orchestrator",
    "Reporter",
    "RetryPolicy",
    "SecretsManager",
    "SelfHealer",
    "Status",
    "StepReport",
    "StepResult",
    "Tier",
    "Validator",
    "__version__",
    "ensure_configured",
]


def ensure_configured(project_root=None, auto_install: bool = True) -> bool:
    """True when ARIA is ready to run, running setup first if it is not.

    This is the entry point `aria_autonomous.py` calls on boot, so a missing
    dependency never turns into a crash loop: the agent configures itself, then
    continues. Failures return False instead of raising, because the caller is
    a long-running loop that should log and retry rather than die.
    """
    from pathlib import Path

    root = Path(project_root) if project_root else Path(__file__).resolve().parent.parent
    if _is_ready(root):
        return True
    if not auto_install:
        return False
    try:
        env = EnvironmentDetector(root).detect()
        report = Orchestrator(env, root).run_full_setup()
        return bool(report.get("success"))
    except Exception:  # noqa: BLE001 - setup failure must not crash the caller
        return False


def _is_ready(root: Path) -> bool:
    """Cheap readiness probe: the state file says setup already succeeded."""
    state = root / ".aura" / "setup_state.json"
    if not state.is_file():
        return False
    try:
        from .journal import Journal

        journal = Journal(state)
        last = journal.last_run
        return bool(last.get("success")) and not journal.source.startswith("corrupt")
    except Exception:  # noqa: BLE001
        return False
