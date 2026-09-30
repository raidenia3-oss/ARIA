"""Terminal reporting.

Plain text by default so it works in any console, JSON when the caller needs
to machine-read the result. No colours beyond a small ANSI set that is
disabled automatically when stdout is not a TTY.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, TextIO

from .model import Status, StepReport

_ANSI = {
    "reset": "\033[0m",
    "bold": "\033[1m",
    "dim": "\033[2m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "red": "\033[31m",
    "cyan": "\033[36m",
}

_STATUS_MARK = {
    Status.OK: ("OK", "green"),
    Status.WARN: ("WARN", "yellow"),
    Status.FAILED: ("FAIL", "red"),
    Status.SKIPPED: ("SKIP", "dim"),
    Status.ROLLED_BACK: ("ROLLBACK", "red"),
    Status.PENDING: ("PEND", "dim"),
    Status.RUNNING: ("RUN", "cyan"),
}


class Reporter:
    """Writes the setup narrative to a stream and keeps a machine-readable copy."""

    def __init__(self, stream: TextIO | None = None, quiet: bool = False) -> None:
        self.stream = stream or sys.stdout
        self.quiet = quiet
        self.color = self._supports_color(self.stream)

    @staticmethod
    def _supports_color(stream: TextIO) -> bool:
        if os.environ.get("NO_COLOR"):
            return False
        if os.environ.get("ARIA_FORCE_COLOR"):
            return True
        return bool(getattr(stream, "isatty", lambda: False)())

    # ------------------------------------------------------------- painting

    def paint(self, text: str, *styles: str) -> str:
        if not self.color or not styles:
            return text
        prefix = "".join(_ANSI.get(style, "") for style in styles)
        return f"{prefix}{text}{_ANSI['reset']}"

    def write(self, text: str = "") -> None:
        if self.quiet:
            return
        print(text, file=self.stream)

    def rule(self, title: str = "") -> None:
        if title:
            bar = "-" * max(0, 58 - len(title))
            self.write(f"  {self.paint(title, 'bold')} {self.paint(bar, 'dim')}")
        else:
            self.write("  " + self.paint("-" * 60, "dim"))

    def header(self, title: str, subtitle: str = "") -> None:
        self.write()
        self.write(self.paint("=" * 60, "cyan"))
        self.write(self.paint(f"  {title}", "bold", "cyan"))
        if subtitle:
            self.write(self.paint(f"  {subtitle}", "dim"))
        self.write(self.paint("=" * 60, "cyan"))

    def step(self, report: StepReport) -> None:
        """One line per step, aligned so results scan vertically."""
        if self.quiet:
            return
        label, colour = _STATUS_MARK.get(report.status, ("?", "dim"))
        name = report.name.ljust(24)
        retries = f" (x{report.attempts})" if report.attempts > 1 else ""
        line = f"  {self.paint(label.ljust(6), colour)} {name}{retries}"
        if report.message:
            line += f"  {self.paint(report.message, 'dim')}"
        self.write(line)

    def detail(self, key: str, value: Any) -> None:
        if self.quiet or value in (None, "", [], {}):
            return
        text = value if isinstance(value, str) else json.dumps(value, default=str)
        if len(text) > 400:
            text = text[:397] + "..."
        self.write(f"        {self.paint(key + ':', 'dim')} {text}")

    def hint(self, text: str) -> None:
        self.write(f"        {self.paint('-> ' + text, 'cyan')}")

    # -------------------------------------------------------------- summary

    def summary(self, report: dict[str, Any]) -> None:
        """Final block: counts, then the next action."""
        if self.quiet:
            return
        steps = report.get("steps", [])
        counts = {status: 0 for status in Status}
        for step in steps:
            counts[Status(step["status"])] = counts.get(Status(step["status"]), 0) + 1

        self.write()
        self.rule("summary")
        self.write(
            f"  {self.paint(str(counts[Status.OK]), 'green')} ok"
            f"   {self.paint(str(counts[Status.WARN]), 'yellow')} warn"
            f"   {self.paint(str(counts[Status.FAILED]), 'red')} failed"
            f"   {self.paint(str(counts[Status.SKIPPED]), 'dim')} skipped"
            f"   {report.get('duration_s', 0):.1f}s"
        )

        failed = [s for s in steps if Status(s["status"]) is Status.FAILED]
        if failed:
            self.write()
            for step in failed:
                self.write(f"  {self.paint('FAILED', 'red')}  {step['name']}: {step['message']}")

        self.write()
        self._next_action(report)

    def _next_action(self, report: dict[str, Any]) -> None:
        """Tell the operator exactly what to do next, or that there is nothing."""
        if report.get("success"):
            self.write(f"  {self.paint('SETUP COMPLETE', 'bold', 'green')}")
            self.write(f"    Next: {self.paint('python aria_autonomous.py', 'cyan')}")
            warnings = [s for s in report.get("steps", []) if Status(s["status"]) is Status.WARN]
            if warnings:
                self.write(
                    f"    {self.paint(f'{len(warnings)} step(s) need attention (non-blocking)', 'dim')}"
                )
            return

        self.write(f"  {self.paint('SETUP INCOMPLETE', 'bold', 'red')}")
        for step in report.get("steps", []):
            if Status(step["status"]) is Status.FAILED:
                hint = step.get("details", {}).get("hint")
                self.write(f"    {step['name']}: {step['message']}")
                if hint:
                    self.write(f"      {self.paint(hint, 'cyan')}")
        self.write(f"    Diagnose: {self.paint('python aria_setup.py --diagnose', 'cyan')}")
        self.write(f"    Retry:    {self.paint('python aria_setup.py --auto-configure', 'cyan')}")

    # ----------------------------------------------------------------- files

    def write_report(self, report: dict[str, Any], path: Path) -> None:
        """Persist the report so `--diagnose` and the daemon can read it."""
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps({"generated_at": time.time(), **report}, indent=2, default=str),
                encoding="utf-8",
            )
        except OSError:
            # Never fail a run because the report could not be written.
            pass
