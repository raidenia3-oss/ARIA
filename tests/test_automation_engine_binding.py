"""Regression guard for the `/api/chat` AttributeError.

`backend/automation/__init__.py` re-exports the rules singleton as
`automation_engine`. A second module with the same leaf name,
`backend/automation/automation_engine.py`, used to exist: importing it rebound
the package attribute over the singleton. `main.py` imports `aura_daemon`
(line 99) before the singleton (line 130), and `aura_daemon` imported that
submodule, so `main.py` deterministically received the workflow module and
`await automation_engine.check_and_execute(...)` raised AttributeError on every
POST to `/api/chat`.

The fix renames the workflow engine. These tests assert the binding cannot
regress, and they run in a subprocess because the original bug was purely a
function of import order.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _run_probe(body: str) -> str:
    """Run `body` in a clean interpreter rooted at the repository."""
    completed = subprocess.run(
        [sys.executable, "-c", body],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    assert completed.returncode == 0, (
        f"probe failed ({completed.returncode})\n"
        f"stdout:\n{completed.stdout}\n"
        f"stderr:\n{completed.stderr}"
    )
    return completed.stdout.strip()


def test_importing_the_consumers_does_not_shadow_the_rules_singleton() -> None:
    """Reproduce main.py's import order: consumers first, singleton second."""
    out = _run_probe(
        "import backend.daemon.aura_daemon\n"
        "import backend.api.public_api_routes\n"
        "from backend.automation import automation_engine\n"
        "print(type(automation_engine).__name__)\n"
        "print(hasattr(automation_engine, 'check_and_execute'))\n"
    )
    name, has_method = out.splitlines()[-2:]
    assert name == "AutomationEngine", (
        "el atributo del paquete `automation_engine` apunta a otra clase: "
        f"{name}"
    )
    assert has_method == "True", (
        "el singleton no expone check_and_execute; /api/chat lanzaria AttributeError"
    )


def test_the_obsolete_module_path_no_longer_exists() -> None:
    out = _run_probe(
        "import importlib.util\n"
        "print(importlib.util.find_spec('backend.automation.automation_engine'))\n"
    )
    assert out.splitlines()[-1] == "None", (
        "backend.automation.automation_engine sigue existiendo y puede volver a "
        "pisar el atributo del paquete"
    )


def test_both_engines_stay_distinct_and_keep_their_own_api() -> None:
    out = _run_probe(
        "from backend.automation import automation_engine\n"
        "from backend.automation.workflow_engine import workflow_engine\n"
        "print(type(automation_engine) is type(workflow_engine))\n"
        "print(hasattr(automation_engine, 'add_rule'), "
        "hasattr(automation_engine, 'schedule_task'))\n"
        "print(hasattr(workflow_engine, 'schedule_task'), "
        "hasattr(workflow_engine, 'add_rule'))\n"
    )
    same, rules_api, workflow_api = out.splitlines()[-3:]
    assert same == "False", "las dos clases se fusionaron; se perderia una API"
    assert rules_api == "True False", (
        "el motor de reglas debe tener add_rule y no schedule_task"
    )
    assert workflow_api == "True False", (
        "el motor de workflows debe tener schedule_task y no add_rule"
    )


@pytest.mark.parametrize(
    "module_path",
    ["backend/api/public_api_routes.py", "backend/daemon/aura_daemon.py"],
)
def test_consumers_import_the_workflow_engine_not_the_package_singleton(
    module_path: str,
) -> None:
    """These two deliberately need the workflow engine, not the rules engine."""
    source = (ROOT / module_path).read_text(encoding="utf-8")
    assert "backend.automation.workflow_engine" in source, (
        f"{module_path} deberia importar backend.automation.workflow_engine"
    )
    assert "backend.automation.automation_engine" not in source, (
        f"{module_path} todavia referencia el path obsoleto"
    )