"""The ``aria-videos`` command.

Thin by design: every command maps to one :class:`VideoLibrary` call. Output is
a Rich table for humans and ``--json`` for the agent loop, so the same command
can serve both without a second implementation.
"""

from __future__ import annotations

import json
import sys
from typing import Any

import click
from rich.console import Console
from rich.table import Table

from .errors import LibraryError
from .library import VideoLibrary

console = Console()


def _emit(payload: Any, as_json: bool) -> None:
    if as_json:
        console.print_json(json.dumps(payload, default=str))
        return
    console.print(payload)


def _human_bytes(value: int) -> str:
    size = float(value)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


@click.group()
@click.option("--root", "root", default=None, help="Library root (defaults to $ARIA_USB_PATH).")
@click.pass_context
def main(ctx: click.Context, root: str | None) -> None:
    """ARIA video reference library."""
    ctx.ensure_object(dict)
    ctx.obj["library"] = VideoLibrary(root=root)


@main.command()
@click.option("--json", "as_json", is_flag=True, help="Machine-readable output.")
@click.pass_context
def status(ctx: click.Context, as_json: bool) -> None:
    """Show the library location, installed tools and index totals."""
    report = ctx.obj["library"].status()
    if as_json:
        _emit(report, True)
        return

    storage = report["storage"]
    table = Table(title="ARIA video reference library", show_header=False)
    table.add_row("Root", f"{storage['root']} ({storage['source']})")
    table.add_row("Removable", "yes" if storage["removable"] else "no")
    table.add_row("Videos on disk", str(storage["videos"]))
    table.add_row("Free space", _human_bytes(storage["free_bytes"]))
    table.add_row("Indexed videos", str(report["index"]["total_videos"]))
    table.add_row("With transcript", str(report["index"]["with_transcript"]))
    table.add_row("Discord", "configured" if report["discord_configured"] else "not configured")
    table.add_row("Notifications db", report["notifications_db"])
    console.print(table)

    tools = Table(title="Tools", show_header=False)
    for name, state in report["tools"].items():
        tools.add_row(name, state)
    console.print(tools)


@main.command()
@click.argument("url")
@click.option("--tag", "tags", multiple=True, help="Tag to attach (repeatable).")
@click.option("--agent", "agent_type", default=None, help="Agent to notify.")
@click.option("--context", default="", help="Why this agent should watch it.")
@click.option("--no-transcribe", is_flag=True, help="Skip Whisper.")
@click.option("--json", "as_json", is_flag=True, help="Machine-readable output.")
@click.pass_context
def download(
    ctx: click.Context,
    url: str,
    tags: tuple[str, ...],
    agent_type: str | None,
    context: str,
    no_transcribe: bool,
    as_json: bool,
) -> None:
    """Download a video, index it and notify the agent."""
    try:
        result = ctx.obj["library"].add_reference(
            url,
            tags=list(tags) or None,
            agent_type=agent_type,
            context=context,
            transcribe=not no_transcribe,
        )
    except LibraryError as exc:
        raise click.ClickException(str(exc)) from exc

    payload = result.to_dict()
    payload["status"] = "success"
    payload["url"] = url
    if as_json:
        _emit(payload, True)
        return

    video = result.video
    console.print(
        f"[green]stored[/green] {video.id} "
        f"({video.duration_display}, {video.resolution}, {_human_bytes(video.size_bytes)})"
    )
    if not result.added:
        console.print("[yellow]already in the index; entry refreshed[/yellow]")
    if video.summary:
        console.print(f"[dim]{video.short_summary()}[/dim]")
    if result.notified is not None:
        state = "delivered" if result.notified.delivered else "not delivered"
        console.print(f"[dim]agent {result.notified.notification.agent_id}: {state}[/dim]")


@main.command()
@click.argument("query")
@click.option("--limit", default=20, show_default=True, help="Maximum hits.")
@click.option("--json", "as_json", is_flag=True, help="Machine-readable output.")
@click.pass_context
def search(ctx: click.Context, query: str, limit: int, as_json: bool) -> None:
    """Search titles, tags, summaries and transcripts."""
    results = ctx.obj["library"].search(query, limit=limit)
    if as_json:
        _emit([result.to_dict() for result in results], True)
        return
    if not results:
        console.print(f"[yellow]no reference matches '{query}'[/yellow]")
        return

    table = Table(title=f"Results for '{query}'")
    table.add_column("Score", justify="right")
    table.add_column("Id")
    table.add_column("Duration", justify="right")
    table.add_column("Title")
    table.add_column("Matched in")
    for result in results:
        table.add_row(
            str(result.score),
            result.video.id,
            result.video.duration_display,
            result.video.title[:48],
            ", ".join(result.matched),
        )
    console.print(table)


@main.command(name="list")
@click.option("--limit", default=None, type=int, help="Maximum entries.")
@click.option("--json", "as_json", is_flag=True, help="Machine-readable output.")
@click.pass_context
def list_references(ctx: click.Context, limit: int | None, as_json: bool) -> None:
    """List indexed videos, newest first."""
    videos = ctx.obj["library"].list_references(limit=limit)
    if as_json:
        _emit([video.to_dict() for video in videos], True)
        return
    if not videos:
        console.print("[yellow]the library is empty[/yellow]")
        return

    table = Table(title="Reference library")
    table.add_column("Id")
    table.add_column("Added", no_wrap=True)
    table.add_column("Duration", justify="right")
    table.add_column("Size", justify="right")
    table.add_column("Title")
    for video in videos:
        table.add_row(
            video.id,
            video.date_downloaded.strftime("%Y-%m-%d"),
            video.duration_display,
            _human_bytes(video.size_bytes),
            video.title[:48],
        )
    console.print(table)


@main.command()
@click.argument("video_id")
@click.option("--json", "as_json", is_flag=True, help="Machine-readable output.")
@click.pass_context
def info(ctx: click.Context, video_id: str, as_json: bool) -> None:
    """Show one video's full record."""
    video = ctx.obj["library"].get(video_id)
    if video is None:
        raise click.ClickException(f"no video with id '{video_id}'")
    _emit(video.to_dict(), as_json) if as_json else _print_detail(video)


def _print_detail(video) -> None:  # noqa: ANN001 - dataclass, keeps click typing simple
    table = Table(title=video.id, show_header=False)
    for label, value in (
        ("Title", video.title),
        ("Source", video.source_url or "unknown"),
        ("Downloaded", video.date_downloaded.isoformat()),
        ("Duration", f"{video.duration_display} ({video.duration_seconds}s)"),
        ("Resolution", f"{video.resolution} @ {video.fps}fps"),
        ("Size", _human_bytes(video.size_bytes)),
        ("Tags", ", ".join(video.tags)),
        ("Keyframes", ", ".join(video.keyframes[:8]) or "none"),
        ("Summary", video.summary or "(none)"),
        ("Notes", video.agent_notes or "(none)"),
    ):
        table.add_row(label, value)
    console.print(table)
    if video.transcript:
        console.print(f"[dim]transcript: {len(video.transcript)} chars[/dim]")


@main.command()
@click.argument("agent_id")
@click.option("--limit", default=10, show_default=True, help="Maximum rows.")
@click.option("--json", "as_json", is_flag=True, help="Machine-readable output.")
@click.pass_context
def pending(ctx: click.Context, agent_id: str, limit: int, as_json: bool) -> None:
    """Show unread video notifications for an agent."""
    rows = ctx.obj["library"].notifier.pending(agent_id, limit=limit)
    if as_json:
        _emit([row.to_dict() for row in rows], True)
        return
    if not rows:
        console.print(f"[yellow]nothing pending for {agent_id}[/yellow]")
        return
    for row in rows:
        console.print(f"[cyan]{row.video_id}[/cyan] — {row.context}")


@main.command()
@click.option("--json", "as_json", is_flag=True, help="Machine-readable output.")
@click.pass_context
def rebuild(ctx: click.Context, as_json: bool) -> None:
    """Rebuild the index from the files on the stick."""
    index = ctx.obj["library"].indexer.rebuild_from_disk()
    ctx.obj["library"].indexer.save(index)
    _emit({"total_videos": index["total_videos"]}, as_json) if as_json else console.print(
        f"[green]index rebuilt:[/green] {index['total_videos']} videos"
    )


@main.command()
@click.option("--drop-media", is_flag=True, help="Also delete media not present in the index.")
@click.option(
    "--retention-days",
    default=30,
    show_default=True,
    help="Delete notifications older than this.",
)
@click.option("--json", "as_json", is_flag=True, help="Machine-readable output.")
@click.pass_context
def clean(ctx: click.Context, drop_media: bool, retention_days: int, as_json: bool) -> None:
    """Reclaim stick space: partial downloads, stale cache, old notifications."""
    try:
        report = ctx.obj["library"].clean(
            drop_media=drop_media, retention_days=retention_days
        )
    except LibraryError as exc:
        raise click.ClickException(str(exc)) from exc
    if as_json:
        _emit(report, True)
        return
    console.print(
        f"[green]cleaned:[/green] {report['partials_removed']} partial downloads, "
        f"{report['cached_transcripts_removed']} cached transcripts, "
        f"{report['notifications_removed']} notifications"
    )
    if report["orphan_media_found"]:
        removed = report["orphan_media_removed"]
        console.print(
            f"[yellow]{report['orphan_media_found']} media files are not in the index[/yellow]"
            + (f"; removed {removed}" if removed else "; re-run with --drop-media to remove")
        )


if __name__ == "__main__":  # pragma: no cover - module entry point
    sys.exit(main())


__all__ = ["main"]
