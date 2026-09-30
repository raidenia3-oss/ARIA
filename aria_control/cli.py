"""The ``aria`` command.

Thin, scriptable wrapper over :class:`~aria_control.client.ControlClient`. The
rich dashboard is used for presentation only; every command also has a
machine-readable ``--json`` mode so scripts and CI never parse ANSI.

Mutating commands confirm first. ``aria restart`` and ``aria upgrade`` act on a
running system, and a mistyped command should cost a keystroke, not a restart.
"""

from __future__ import annotations

import json
import os
import sys
import time
from typing import Any, Callable

import click

from aria_control.client import (
    API_KEY_ENV,
    AuthRequired,
    BackendUnreachable,
    ControlClient,
    ControlError,
    DEFAULT_BASE_URL,
)
from aria_control.tui import MARKERS, Dashboard

#: Backend did not answer.
EXIT_UNREACHABLE = 2
#: Control plane answered with an error.
EXIT_CONTROL_ERROR = 3
#: No bearer token configured.
EXIT_NO_TOKEN = 4

#: How long ``--wait`` polls before giving up, in seconds.
JOB_WAIT_TIMEOUT = 300.0
#: Polling interval for ``--wait``.
JOB_POLL_SECONDS = 1.0


def _emit(payload: Any, as_json: bool, renderer: Callable[[Any], None]) -> None:
    """Print raw JSON, or hand the payload to a rich renderer."""
    if as_json:
        click.echo(json.dumps(payload, indent=2, default=str))
    else:
        renderer(payload)


def _fail(exc: ControlError) -> None:
    """Print an error and exit with the code that describes it."""
    click.secho(f"error: {exc}", fg="red", err=True)
    if isinstance(exc, AuthRequired):
        sys.exit(EXIT_NO_TOKEN)
    if isinstance(exc, BackendUnreachable):
        sys.exit(EXIT_UNREACHABLE)
    sys.exit(EXIT_CONTROL_ERROR)


def _table(title: str, columns: list[tuple[str, str]], rows: list[list[str]]) -> None:
    """Render a plain rich table.

    ``columns`` is a list of ``(header, style)``; an empty style means default.
    """
    from rich.console import Console
    from rich.table import Table

    table = Table(title=title, expand=True)
    for header, style in columns:
        table.add_column(header, style=style or None)
    for row in rows:
        table.add_row(*row)
    Console().print(table)


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "--base-url",
    default=lambda: os.environ.get("ARIA_BACKEND_URL", DEFAULT_BASE_URL),
    show_default="ARIA_BACKEND_URL",
    help="Axum backend base URL.",
)
@click.option(
    "--token",
    default=lambda: os.environ.get(API_KEY_ENV),
    help=f"Bearer token. Defaults to ${API_KEY_ENV}.",
)
@click.pass_context
def cli(ctx: click.Context, base_url: str, token: str | None) -> None:
    """ARIA Control Center — inspect and drive the running system."""
    ctx.ensure_object(dict)
    ctx.obj["client"] = ControlClient(base_url=base_url, token=token)


# --- status -----------------------------------------------------------------


@cli.command()
@click.option("--watch", "-w", is_flag=True, help="Refresh until Ctrl+C.")
@click.option("--json", "as_json", is_flag=True, help="Emit the raw payload.")
@click.option("--logs", "log_lines", default=20, show_default=True, help="Log lines to show.")
@click.pass_context
def status(ctx: click.Context, watch: bool, as_json: bool, log_lines: int) -> None:
    """Show the control-center dashboard."""
    client: ControlClient = ctx.obj["client"]
    try:
        if as_json:
            _emit(client.status(), True, lambda _: None)
            return
        Dashboard(client=client, log_lines=log_lines).run(watch=watch)
    except ControlError as exc:
        _fail(exc)


# --- logs -------------------------------------------------------------------


@cli.command()
@click.option("--lines", "-n", default=50, show_default=True, help="How many lines.")
@click.option("--follow", "-f", is_flag=True, help="Stream new lines until Ctrl+C.")
@click.option("--json", "as_json", is_flag=True, help="Emit the raw payload.")
@click.pass_context
def logs(ctx: click.Context, lines: int, follow: bool, as_json: bool) -> None:
    """Show captured control-plane logs."""
    client: ControlClient = ctx.obj["client"]
    try:
        payload = client.logs(lines=lines)
    except ControlError as exc:
        _fail(exc)

    if as_json:
        _emit(payload, True, lambda _: None)
        return
    if not follow:
        _render_logs(payload.get("lines", []))
        return

    click.secho("streaming /api/control/logs/stream (Ctrl+C to stop)", fg="bright_black")
    try:
        _stream_logs(client)
    except KeyboardInterrupt:
        click.echo("[dim]stopped[/]")


def _render_logs(entries: list[dict[str, Any]]) -> None:
    rows = [
        [
            str(entry.get("ts", ""))[-8:] or "-",
            str(entry.get("level", "info")).lower(),
            str(entry.get("target", "-")),
            str(entry.get("message", "")),
        ]
        for entry in entries
    ]
    if not rows:
        click.echo("[dim]no entries[/]")
        return
    _table(
        "ARIA logs",
        [("Time", "dim"), ("Level", "cyan"), ("Target", "dim"), ("Message", "")],
        rows,
    )


def _stream_logs(client: ControlClient) -> None:
    """Follow the log WebSocket until Ctrl+C.

    Needs the ``websockets`` package; the bearer token travels in the handshake
    headers because Axum reads it from ``Authorization`` or ``x-api-key``.
    """
    import asyncio

    import websockets
    from rich.console import Console
    from rich.live import Live
    from rich.table import Table

    headers: dict[str, str] = {}
    token = client.token or os.environ.get(API_KEY_ENV)
    if token:
        headers["Authorization"] = f"Bearer {token}"
    url = (
        client.base_url.rstrip("/").replace("https://", "wss://").replace("http://", "ws://")
        + "/api/control/logs/stream"
    )

    # Bounded so a long-running stream cannot grow without limit.
    buffer: list[dict[str, Any]] = []
    tail = 25

    def frame() -> Table:
        table = Table(box=None, expand=True)
        table.add_column("Time", style="dim", no_wrap=True)
        table.add_column("Level", style="cyan", no_wrap=True)
        table.add_column("Message")
        for entry in buffer[-tail:]:
            table.add_row(
                str(entry.get("ts", ""))[-8:] or "-",
                str(entry.get("level", "info")).lower(),
                f"{entry.get('target', '-')} {entry.get('message', '')}",
            )
        return table

    async def pump():
        # Async generator: yields one decoded entry per frame. The buffer is
        # trimmed by the consumer, not here.
        async with websockets.connect(url, additional_headers=headers) as socket:
            async for raw in socket:
                try:
                    entry = json.loads(raw)
                except (TypeError, ValueError):
                    continue
                yield entry

    async def drive(live: Live) -> None:
        async for entry in pump():
            buffer.append(entry)
            del buffer[:-500]
            live.update(frame())

    with Live(console=Console(), refresh_per_second=4) as live:
        try:
            asyncio.run(drive(live))
        except KeyboardInterrupt:
            return


# --- config -----------------------------------------------------------------


@cli.group()
def config() -> None:
    """Read or write control-plane settings."""


@config.command("list")
@click.option("--json", "as_json", is_flag=True, help="Emit the raw payload.")
@click.pass_context
def config_list(ctx: click.Context, as_json: bool) -> None:
    """List every setting with its current value."""
    try:
        payload = ctx.obj["client"].config()
    except ControlError as exc:
        _fail(exc)
    _emit(payload, as_json, _render_config_table)


def _render_config_table(payload: dict[str, Any]) -> None:
    rows = [
        [
            str(field.get("key", "")),
            str(field.get("value", "")),
            str(field.get("default", "")),
            str(field.get("description", "")),
        ]
        for field in payload.get("fields", [])
    ]
    _table(
        "ARIA configuration",
        [("Key", "cyan"), ("Value", "green"), ("Default", "dim"), ("Description", "dim")],
        rows,
    )


@config.command("get")
@click.argument("key")
@click.option("--json", "as_json", is_flag=True, help="Emit the raw payload.")
@click.pass_context
def config_get(ctx: click.Context, key: str, as_json: bool) -> None:
    """Show one setting."""
    try:
        payload = ctx.obj["client"].config()
    except ControlError as exc:
        _fail(exc)
    current = (payload.get("config") or {}).get(key)
    if current is None:
        click.secho(
            f"error: unknown key '{key}'; valid keys: {', '.join(sorted(payload.get('config', {})))}",
            fg="red",
            err=True,
        )
        sys.exit(EXIT_CONTROL_ERROR)
    _emit({"key": key, "value": current}, as_json, lambda item: click.echo(f"{item['key']} = {item['value']}"))


@config.command("set")
@click.argument("key")
@click.argument("value")
@click.option("--json", "as_json", is_flag=True, help="Emit the raw payload.")
@click.pass_context
def config_set(ctx: click.Context, key: str, value: str, as_json: bool) -> None:
    """Set one setting."""
    try:
        payload = ctx.obj["client"].set_config(key, value)
    except ControlError as exc:
        _fail(exc)
    _emit(payload, as_json, lambda item: click.secho(f"OK  {item.get('key')} = {item.get('value')}", fg="green"))


# --- inventory --------------------------------------------------------------


@cli.command()
@click.option("--json", "as_json", is_flag=True, help="Emit the raw payload.")
@click.pass_context
def services(ctx: click.Context, as_json: bool) -> None:
    """List ARIA services and their liveness."""
    try:
        payload = ctx.obj["client"].services()
    except ControlError as exc:
        _fail(exc)
    _emit(payload, as_json, _render_services)


def _render_services(payload: dict[str, Any]) -> None:
    rows = [
        [
            str(service.get("name", "")),
            MARKERS.get(str(service.get("status", "unknown")), ("?", "yellow"))[0],
            str(service.get("pid") or "-"),
            str(service.get("port") or "-"),
            str(service.get("description", "")),
        ]
        for service in payload.get("services", [])
    ]
    _table(
        "ARIA services",
        [("Service", "cyan"), ("Status", ""), ("PID", "dim"), ("Port", "dim"), ("Description", "dim")],
        rows,
    )


@cli.command()
@click.option("--json", "as_json", is_flag=True, help="Emit the raw payload.")
@click.pass_context
def plugins(ctx: click.Context, as_json: bool) -> None:
    """List installed plugins."""
    try:
        payload = ctx.obj["client"].plugins()
    except ControlError as exc:
        _fail(exc)
    _emit(payload, as_json, _render_plugins)


def _render_plugins(payload: dict[str, Any]) -> None:
    rows = [
        [
            str(plugin.get("name", "")),
            str(plugin.get("status", "")),
            str(plugin.get("description", "")),
        ]
        for plugin in payload.get("plugins", [])
    ]
    _table("ARIA plugins", [("Name", "cyan"), ("Status", "green"), ("Description", "dim")], rows)


# --- mutating ---------------------------------------------------------------


@cli.command()
@click.option("--yes", "-y", is_flag=True, help="Skip the confirmation prompt.")
@click.option("--wait", is_flag=True, help="Poll the job until it finishes.")
@click.option("--json", "as_json", is_flag=True, help="Emit the raw payload.")
@click.pass_context
def restart(ctx: click.Context, yes: bool, wait: bool, as_json: bool) -> None:
    """Restart ARIA services."""
    client: ControlClient = ctx.obj["client"]
    if not yes and not click.confirm("Restart ARIA services?", default=False):
        click.echo("aborted")
        return
    try:
        payload = client.restart()
        if wait:
            payload = _await_job(client, payload.get("job_id", ""))
    except ControlError as exc:
        _fail(exc)
    _emit(payload, as_json, _render_job)


@cli.command()
@click.option("--yes", "-y", is_flag=True, help="Skip the confirmation prompt.")
@click.option("--wait", is_flag=True, help="Poll the job until it finishes.")
@click.option("--json", "as_json", is_flag=True, help="Emit the raw payload.")
@click.pass_context
def upgrade(ctx: click.Context, yes: bool, wait: bool, as_json: bool) -> None:
    """Check for and apply updates."""
    client: ControlClient = ctx.obj["client"]
    if not yes and not click.confirm("Apply updates now?", default=False):
        click.echo("aborted")
        return
    try:
        payload = client.upgrade()
        if wait:
            payload = _await_job(client, payload.get("job_id", ""))
    except ControlError as exc:
        _fail(exc)
    _emit(payload, as_json, _render_job)


@cli.command("job")
@click.argument("job_id")
@click.option("--json", "as_json", is_flag=True, help="Emit the raw payload.")
@click.pass_context
def job(ctx: click.Context, job_id: str, as_json: bool) -> None:
    """Show the outcome of a dispatched restart or upgrade."""
    try:
        payload = ctx.obj["client"].job(job_id)
    except ControlError as exc:
        _fail(exc)
    _emit(payload, as_json, _render_job)


def _await_job(client: ControlClient, job_id: str) -> dict[str, Any]:
    """Poll a dispatched job until it leaves the running state."""
    if not job_id:
        return {}
    deadline = time.monotonic() + JOB_WAIT_TIMEOUT
    payload: dict[str, Any] = {}
    while time.monotonic() < deadline:
        payload = client.job(job_id)
        if (payload.get("job") or {}).get("status") != "running":
            return payload
        time.sleep(JOB_POLL_SECONDS)
    click.secho("timed out waiting for the job; it may still be running", fg="yellow", err=True)
    return payload


def _render_job(payload: dict[str, Any]) -> None:
    record = payload.get("job", payload)
    status = str(record.get("status", "unknown"))
    colour = (
        "green"
        if status == "succeeded"
        else "yellow"
        if status in ("accepted", "running")
        else "red"
    )
    click.secho(
        f"{status.upper()}  {record.get('kind', '?')}  {record.get('id') or record.get('job_id', '')}",
        fg=colour,
    )
    if record.get("command"):
        click.secho(f"  command: {record['command']}", fg="bright_black")
    if record.get("output"):
        click.echo(record["output"])
    if not payload.get("job") and record.get("poll"):
        click.secho(f"  poll: {record['poll']}", fg="bright_black")


def main(argv: list[str] | None = None) -> int:
    """Entry point for the ``aria`` console script."""
    try:
        cli.main(args=argv, prog_name="aria", standalone_mode=True)
    except SystemExit as exc:
        return int(exc.code or 0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
