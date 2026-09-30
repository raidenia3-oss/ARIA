"""Rich dashboard for the ARIA control center.

Two render modes, deliberately:

``render()`` — one shot. Deterministic, exits, safe in CI and over a pipe.
``run(watch=True)`` — a ``Live`` refresh loop until Ctrl+C.

The spec's original sketch looped forever with no input handling, which cannot
exit and cannot be tested. Interactive single-key navigation is deferred until
``textual`` is available; see ``docs/CONTROL_CENTER.md``.

Glyphs are ASCII-safe. ARIA runs on Windows consoles where emoji fall back to
mojibake, and a dashboard nobody can read is worse than a plain one.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from rich.console import Console, Group, RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from aria_control.client import AuthRequired, BackendUnreachable, ControlClient, ControlError

#: Status marker and colour per service state.
MARKERS = {
    "running": ("[green]OK[/]", "green"),
    "stopped": ("[red]DOWN[/]", "red"),
    "unknown": ("[yellow]?[/]", "yellow"),
}

#: Marker per log level.
LEVEL_MARKERS = {
    "error": "[red]ERR[/]",
    "warn": "[yellow]WARN[/]",
    "info": "[cyan]INFO[/]",
    "debug": "[dim]DBG[/]",
    "trace": "[dim]TRC[/]",
}

#: Log lines shown in the dashboard panel.
DEFAULT_LOG_LINES = 20

#: Seconds between refreshes in watch mode.
DEFAULT_REFRESH_SECONDS = 2.0


@dataclass
class Snapshot:
    """One consistent read of the control plane.

    Partial results are the normal case: the dashboard must still render when
    ``/logs`` fails but ``/status`` succeeds, so each section is optional and
    carries its own error.
    """

    status: dict[str, Any] | None = None
    services: list[dict[str, Any]] = field(default_factory=list)
    logs: list[dict[str, Any]] = field(default_factory=list)
    errors: dict[str, str] = field(default_factory=dict)
    fatal: str | None = None

    @property
    def ok(self) -> bool:
        return self.fatal is None


def _marker(status: str) -> RenderableType:
    text, colour = MARKERS.get(status, ("[?]?[/]", "yellow"))
    return Text.from_markup(text, style=colour)


class Dashboard:
    """Renders control-plane state with Rich."""

    def __init__(
        self,
        client: ControlClient | None = None,
        console: Console | None = None,
        log_lines: int = DEFAULT_LOG_LINES,
    ) -> None:
        self.client = client or ControlClient()
        self.console = console or Console()
        self.log_lines = log_lines

    # -- data -------------------------------------------------------------

    def snapshot(self) -> Snapshot:
        """Read the control plane, tolerating partial failure."""
        snap = Snapshot()
        try:
            snap.status = self.client.status()
        except (BackendUnreachable, AuthRequired) as exc:
            snap.fatal = str(exc)
            return snap
        except ControlError as exc:
            snap.fatal = str(exc)
            return snap

        try:
            payload = self.client.services()
            snap.services = list(payload.get("services", []))
        except ControlError as exc:
            snap.errors["services"] = str(exc)

        try:
            payload = self.client.logs(lines=self.log_lines)
            snap.logs = list(payload.get("lines", []))
        except ControlError as exc:
            snap.errors["logs"] = str(exc)

        return snap

    # -- rendering --------------------------------------------------------

    def render(self, snap: Snapshot | None = None) -> RenderableType:
        """Build the full dashboard as a Rich renderable."""
        snap = snap if snap is not None else self.snapshot()
        if snap.fatal is not None:
            return Panel(
                Text.assemble(
                    ("Backend unreachable\n\n", "bold red"),
                    (snap.fatal, "red"),
                    ("\n\nStart it with: ", "dim"),
                    ("aria-backend", "bold"),
                ),
                title="ARIA Control Center",
                border_style="red",
            )
        return Group(
            self._header(snap),
            self._services_panel(snap),
            self._logs_panel(snap),
            self._footer(),
        )

    def _header(self, snap: Snapshot) -> RenderableType:
        status = snap.status or {}
        version = status.get("aria_version", "?")
        channel = status.get("channel", "?")
        uptime = status.get("uptime", "?")
        healthy = status.get("services_healthy", 0)
        total = status.get("services_total", 0)
        last_check = status.get("last_update_check") or "never"

        body = Table.grid(padding=(0, 2))
        body.add_column(style="bold cyan", justify="right")
        body.add_column()
        body.add_row("Version", f"{version} ({channel})")
        body.add_row("Uptime", str(uptime))
        body.add_row("Services", f"{healthy}/{total} healthy")
        body.add_row("Last update check", str(last_check))
        body.add_row("Checked", str(status.get("checked_at", "-")))

        return Panel(body, title=f"ARIA v{version} Control Center", border_style="cyan")

    def _services_panel(self, snap: Snapshot) -> RenderableType:
        if not snap.services:
            detail = snap.errors.get("services", "no services reported")
            return Panel(Text(detail, style="yellow"), title="Services", border_style="yellow")

        table = Table(box=None, pad_edge=False, expand=True)
        table.add_column("Service", style="cyan", no_wrap=True)
        table.add_column("Status")
        table.add_column("PID", justify="right", style="dim")
        table.add_column("Port", justify="right", style="dim")
        table.add_column("Description", style="dim")

        for service in snap.services:
            name = str(service.get("name", "?"))
            state = str(service.get("status", "unknown"))
            pid = service.get("pid")
            port = service.get("port")
            table.add_row(
                name,
                _marker(state),
                str(pid) if pid else "-",
                str(port) if port else "-",
                str(service.get("description", "")),
            )
        return Panel(table, title="Services", border_style="blue")

    def _logs_panel(self, snap: Snapshot) -> RenderableType:
        if not snap.logs:
            detail = snap.errors.get("logs", "no log entries captured yet")
            return Panel(Text(detail, style="dim"), title="Recent Logs", border_style="dim")

        table = Table(box=None, pad_edge=False, expand=True)
        table.add_column("Time", style="dim", no_wrap=True)
        table.add_column("Level", no_wrap=True)
        table.add_column("Target", style="dim", no_wrap=True)
        table.add_column("Message")

        for entry in snap.logs:
            level = str(entry.get("level", "info")).lower()
            stamp = str(entry.get("ts", ""))[-8:] or "-"
            table.add_row(
                stamp,
                Text.from_markup(LEVEL_MARKERS.get(level, "[ ]?[/]")),
                str(entry.get("target", "-")),
                str(entry.get("message", "")),
            )
        return Panel(table, title="Recent Logs", border_style="magenta")

    def _footer(self) -> RenderableType:
        return Panel(
            Text(
                "aria status --watch   aria logs -f   aria config list   "
                "aria services   aria plugins   aria restart   aria upgrade   (Ctrl+C to stop)",
                style="dim",
            ),
            border_style="dim",
        )

    # -- driving ----------------------------------------------------------

    def print_once(self) -> None:
        """Render a single frame and return."""
        self.console.print(self.render())

    def run(self, watch: bool = False, interval: float = DEFAULT_REFRESH_SECONDS) -> None:
        """Render once, or refresh forever until interrupted.

        ``Ctrl+C`` is the documented exit for watch mode. Single-key navigation
        needs a terminal-aware input layer; until ``textual`` lands, catching
        ``KeyboardInterrupt`` is the honest version of "press q".
        """
        if not watch:
            self.print_once()
            return

        from rich.live import Live

        try:
            with Live(self.render(), console=self.console, refresh_per_second=2) as live:
                while True:
                    live.update(self.render())
                    time.sleep(interval)
        except KeyboardInterrupt:
            self.console.print("[dim]stopped[/]")


__all__ = ["DEFAULT_LOG_LINES", "DEFAULT_REFRESH_SECONDS", "Dashboard", "LEVEL_MARKERS", "MARKERS", "Snapshot"]
