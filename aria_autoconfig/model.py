"""Data model shared by every auto-configuration step.

The engine is declarative: each step declares what it needs, what it does and
how to verify itself. The orchestrator never hardcodes a step, it only walks
the declared list, which is what makes `--validate` and `--reset` possible
without a second code path.

States follow the same contract as the rest of the system:
    PENDING -> SKIPPED | OK | WARN | FAILED | ROLLED_BACK
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Status(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    OK = "ok"
    WARN = "warn"
    FAILED = "failed"
    SKIPPED = "skipped"
    ROLLED_BACK = "rolled_back"

    @property
    def is_terminal_ok(self) -> bool:
        return self in (Status.OK, Status.WARN, Status.SKIPPED)

    @property
    def is_problem(self) -> bool:
        return self in (Status.FAILED, Status.ROLLED_BACK)


class Tier(str, Enum):
    """How badly a missing piece hurts.

    CORE   - without it ARIA cannot run at all.
    RUNTIME- needed for the interactive/orb experience.
    OPTIONAL- nice to have; failure must never block setup.
    """

    CORE = "core"
    RUNTIME = "runtime"
    OPTIONAL = "optional"

    @property
    def blocking(self) -> bool:
        return self is Tier.CORE


@dataclass
class StepResult:
    """Outcome of a single step."""

    status: Status = Status.PENDING
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    duration_s: float = 0.0
    #: True when the outcome cannot change by running the step again. Used to
    #: settle a step in the journal so a repeated setup run does not repeat a
    #: multi-minute build that will fail the same way.
    permanent: bool = False

    @classmethod
    def ok(cls, message: str = "", **details: Any) -> "StepResult":
        return cls(Status.OK, message, details)

    @classmethod
    def warn(cls, message: str, permanent: bool = False, **details: Any) -> "StepResult":
        return cls(Status.WARN, message, details, permanent=permanent)

    @classmethod
    def fail(cls, message: str, permanent: bool = False, **details: Any) -> "StepResult":
        return cls(Status.FAILED, message, details, permanent=permanent)

    @classmethod
    def skip(cls, message: str = "", **details: Any) -> "StepResult":
        return cls(Status.SKIPPED, message, details)


@dataclass
class StepReport:
    """A step result plus the identity needed for retry and reporting."""

    name: str
    tier: Tier
    status: Status
    message: str = ""
    attempts: int = 1
    duration_s: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)
    at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "tier": self.tier.value,
            "status": self.status.value,
            "message": self.message,
            "attempts": self.attempts,
            "duration_s": round(self.duration_s, 3),
            "details": self.details,
            "at": self.at,
        }


@dataclass
class Environment:
    """Everything the detector learned about the host, in one serializable blob."""

    os_name: str = ""
    os_release: str = ""
    arch: str = ""
    python_version: str = ""
    python_executable: str = ""
    venv_path: str = ""
    in_venv: bool = False
    git_installed: bool = False
    git_version: str = ""
    cargo_installed: bool = False
    cargo_version: str = ""
    node_installed: bool = False
    node_version: str = ""
    ollama_installed: bool = False
    ollama_running: bool = False
    ollama_models: list[str] = field(default_factory=list)
    gh_cli_installed: bool = False
    gh_authenticated: bool = False
    mcode_installed: bool = False
    node_available: bool = False
    services: dict[str, bool] = field(default_factory=dict)
    project_root: str = ""
    missing_tools: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "os": f"{self.os_name} {self.os_release}".strip(),
            "arch": self.arch,
            "python": self.python_version,
            "python_executable": self.python_executable,
            "in_venv": self.in_venv,
            "git": self.git_version or self.git_installed,
            "cargo": self.cargo_version or self.cargo_installed,
            "node": self.node_version or self.node_installed,
            "ollama_running": self.ollama_running,
            "ollama_models": self.ollama_models,
            "gh_authenticated": self.gh_authenticated,
            "services": self.services,
            "missing_tools": self.missing_tools,
        }
