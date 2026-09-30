"""Persistent state for the setup engine.

Three responsibilities, all backed by one JSON file (`.aura/setup_state.json`):

1. Idempotency - a step that already succeeded with the same fingerprint is not
   re-run. The fingerprint covers the inputs that would change the outcome, so
   changing `requirements.txt` invalidates the install step automatically.
2. Rollback bookkeeping - every mutation records how to undo it. If a later
   step fails, the orchestrator can unwind in reverse order.
3. Audit trail - the last run's report is kept so `--diagnose` and the
   autonomous loop can see what happened without re-running anything.

The file is written atomically (temp + replace) so a crash mid-write can never
leave a half-parsed state file behind.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

STATE_VERSION = 1
DEFAULT_STATE_DIR = Path(".aura")
DEFAULT_STATE_FILE = DEFAULT_STATE_DIR / "setup_state.json"


def fingerprint(*parts: Any) -> str:
    """Stable hash of the inputs a step depends on.

    Used for idempotency: same inputs -> same hash -> step is skipped.
    """
    payload = json.dumps(parts, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def file_fingerprint(path: Path) -> str:
    """Hash a file's contents, or ``"missing"`` when it does not exist.

    Content hash (not mtime) so touching a file does not invalidate a step but
    actually editing it does.
    """
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    except (OSError, ValueError):
        return "missing"


@dataclass
class StepRecord:
    """What the journal remembers about one step."""

    name: str
    fingerprint: str
    status: str
    message: str = ""
    at: float = field(default_factory=time.time)
    undo: dict[str, Any] = field(default_factory=dict)
    #: A WARN whose cause is permanent (an unavailable wheel, a broken source
    #: file) will not fix itself. Re-running it on every invocation would make
    #: setup slow and change nothing, so it is recorded as settled.
    permanent: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "fingerprint": self.fingerprint,
            "status": self.status,
            "message": self.message,
            "at": self.at,
            "undo": self.undo,
            "permanent": self.permanent,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "StepRecord":
        return cls(
            name=str(raw.get("name", "")),
            fingerprint=str(raw.get("fingerprint", "")),
            status=str(raw.get("status", "unknown")),
            message=str(raw.get("message", "")),
            at=float(raw.get("at", 0.0)),
            undo=dict(raw.get("undo") or {}),
            permanent=bool(raw.get("permanent", False)),
        )


class Journal:
    """Idempotency + rollback + audit trail, persisted as JSON."""

    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path) if path else DEFAULT_STATE_FILE
        self._steps: dict[str, StepRecord] = {}
        self._last_run: dict[str, Any] = {}
        self._loaded_from: str = "empty"
        self._load()

    # ------------------------------------------------------------------ load

    def _load(self) -> None:
        if not self.path.exists():
            self._loaded_from = "new"
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            # A corrupt state file must never block setup; start clean and say so.
            self._loaded_from = f"corrupt ({exc.__class__.__name__})"
            return
        if not isinstance(raw, dict):
            self._loaded_from = "corrupt (not an object)"
            return
        if int(raw.get("version", 0)) != STATE_VERSION:
            self._loaded_from = "version-mismatch"
            return
        for entry in raw.get("steps", []):
            if isinstance(entry, dict):
                record = StepRecord.from_dict(entry)
                self._steps[record.name] = record
        self._last_run = raw.get("last_run") or {}
        self._loaded_from = "loaded"

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": STATE_VERSION,
            "updated_at": time.time(),
            "steps": [record.to_dict() for record in self._steps.values()],
            "last_run": self._last_run,
        }
        handle, tmp_name = tempfile.mkstemp(
            dir=str(self.path.parent), prefix=".setup_state-", suffix=".tmp"
        )
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2, default=str)
            os.replace(tmp_name, self.path)
        except BaseException:
            # Never leave the temp file behind if the atomic swap failed.
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise

    # ----------------------------------------------------------- idempotency

    def is_satisfied(self, name: str, print_: str) -> bool:
        """True when this exact work already succeeded.

        A recorded FAILED never counts as satisfied, so retries are free. A
        permanent WARN does count: its cause is known to be unfixable by
        re-running, and repeating a multi-minute build on every boot is worse
        than reporting it.
        """
        record = self._steps.get(name)
        if not record or record.fingerprint != print_:
            return False
        if record.status == "ok":
            return True
        return record.status == "warn" and record.permanent

    def record(
        self,
        name: str,
        print_: str,
        status: str,
        message: str = "",
        undo: dict[str, Any] | None = None,
        permanent: bool = False,
    ) -> None:
        self._steps[name] = StepRecord(
            name=name,
            fingerprint=print_,
            status=status,
            message=message[:500],
            undo=undo or {},
            permanent=permanent,
        )
        self._save()

    def forget(self, name: str) -> None:
        if self._steps.pop(name, None) is not None:
            self._save()

    def record_of(self, name: str) -> StepRecord | None:
        """The stored record for a step, or None. Read-only accessor."""
        return self._steps.get(name)

    def clear(self) -> None:
        self._steps.clear()
        self._last_run = {}
        self._save()

    # --------------------------------------------------------------- undoing

    def undo_for(self, name: str) -> dict[str, Any]:
        record = self._steps.get(name)
        return dict(record.undo) if record else {}

    # ----------------------------------------------------------------- audit

    def store_run(self, report: dict[str, Any]) -> None:
        self._last_run = report
        self._save()

    @property
    def last_run(self) -> dict[str, Any]:
        return dict(self._last_run)

    @property
    def source(self) -> str:
        return self._loaded_from

    def completed_steps(self) -> list[str]:
        return [name for name, rec in self._steps.items() if rec.status == "ok"]

    def settled_steps(self) -> list[str]:
        """Steps that will not be re-run: succeeded, or a permanent warning."""
        return [
            name
            for name, rec in self._steps.items()
            if rec.status == "ok" or (rec.status == "warn" and rec.permanent)
        ]
