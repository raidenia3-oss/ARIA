"""Media fact extraction: ffprobe, ffmpeg scene cuts, Whisper, Ollama summaries.

Every external tool is invoked through an injectable runner, so the whole
extraction path is unit-testable without ffmpeg, Whisper or a network. The
optional tools degrade honestly: no Whisper means an empty transcript and a
``whisper: missing`` note in the tool report, never a plausible-looking
placeholder sentence.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence

from .errors import ExtractionError, ToolMissingError

FFPROBE = "ffprobe"
FFMPEG = "ffmpeg"
WHISPER = "whisper"

#: Environment override for the local inference server used for summaries.
OLLAMA_URL_ENV = "ARIA_OLLAMA_URL"
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"
DEFAULT_OLLAMA_MODEL = "dolphin-2_6-phi-2"

#: Scene-detection sensitivity, 0..1. Higher means fewer, bigger cuts.
SCENE_THRESHOLD = 0.3
#: Upper bound on stored keyframe markers.
MAX_KEYFRAMES = 40
#: Longest transcript whisper may run before it is abandoned.
TRANSCRIPT_TIMEOUT_SECS = 1800

#: ``[Parsed] showinfo pts_time:`` line emitted by the scene filter.
_PTS_RE = re.compile(r"pts_time:(\d+(?:\.\d+)?)")
_RATIONAL_RE = re.compile(r"^(\d+(?:\.\d+)?)/(\d+(?:\.\d+)?)$")


@dataclass(frozen=True)
class CommandResult:
    """Outcome of one external command."""

    argv: tuple[str, ...]
    returncode: int
    stdout: str = ""
    stderr: str = ""

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    def tail(self, limit: int = 500) -> str:
        """Last ``limit`` characters of the combined output, for error messages."""
        text = (self.stdout + "\n" + self.stderr).strip()
        return text[-limit:]


#: A runner takes an argv (never a shell string) and a timeout in seconds.
Runner = Callable[[Sequence[str], int], CommandResult]


class SubprocessRunner:
    """Default runner: ``subprocess.run`` with no shell, ever.

    Download URLs and titles reach argv here. With ``shell=True`` a title such
    as ``a; rm -rf ~`` would be a command, so the shell is never involved.
    """

    def __call__(self, argv: Sequence[str], timeout: int = 300) -> CommandResult:
        import subprocess

        args = [str(part) for part in argv]
        if shutil.which(args[0]) is None and not Path(args[0]).exists():
            raise ToolMissingError(args[0], "install it and retry")
        try:
            completed = subprocess.run(  # noqa: S603 - argv list, no shell
                args,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            return CommandResult(tuple(args), 124, "", f"timed out after {timeout}s: {exc}")
        except OSError as exc:
            return CommandResult(tuple(args), 127, "", str(exc))
        return CommandResult(
            tuple(args),
            completed.returncode,
            completed.stdout or "",
            completed.stderr or "",
        )


@dataclass
class MediaProbe:
    """Container facts read by ffprobe."""

    duration_seconds: int = 0
    height: int = 0
    resolution: str = "unknown"
    fps: float = 0.0
    format: str = ""
    bitrate_kbps: int = 0
    size_bytes: int = 0

    @classmethod
    def from_ffprobe(cls, data: dict[str, Any], size_bytes: int = 0) -> "MediaProbe":
        video_stream = next(
            (
                stream
                for stream in data.get("streams", [])
                if stream.get("codec_type") == "video"
            ),
            {},
        )
        container = data.get("format", {}) or {}
        height = int(video_stream.get("height") or 0)
        return cls(
            duration_seconds=int(_as_float(container.get("duration")) or 0),
            height=height,
            resolution=f"{height}p" if height else "unknown",
            fps=_as_float(video_stream.get("avg_frame_rate")) or 0.0,
            format=str(container.get("format_name") or ""),
            bitrate_kbps=int(_as_float(container.get("bit_rate")) or 0) // 1000,
            size_bytes=size_bytes or int(_as_float(container.get("size")) or 0),
        )


@dataclass
class TranscriptResult:
    """A transcript plus how (or whether) it was produced."""

    text: str = ""
    language: str = ""
    engine: str = "none"
    note: str = ""


def _as_float(value: Any) -> float:
    """Parse a number that ffprobe may report as ``"12/25"`` or ``"N/A"``."""
    if value is None:
        return 0.0
    text = str(value).strip()
    if not text or text.upper() in {"N/A", "UNKNOWN"}:
        return 0.0
    rational = _RATIONAL_RE.match(text)
    if rational:
        numerator, denominator = float(rational.group(1)), float(rational.group(2))
        return numerator / denominator if denominator else 0.0
    try:
        return float(text)
    except ValueError:
        return 0.0


def format_timestamp(seconds: float) -> str:
    """``93.4`` → ``"1:33"``, the form stored in keyframe markers."""
    total = max(0, int(round(seconds)))
    minutes, secs = divmod(total, 60)
    return f"{minutes}:{secs:02d}"


class MediaExtractor:
    """Reads media facts and text out of a downloaded file."""

    def __init__(
        self,
        cache_dir: str | os.PathLike[str],
        runner: Runner | None = None,
        ollama_url: str | None = None,
        ollama_model: str = DEFAULT_OLLAMA_MODEL,
        post_json: Callable[[str, dict[str, Any], int], dict[str, Any]] | None = None,
    ) -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.runner: Runner = runner or SubprocessRunner()
        self.ollama_url = (ollama_url or os.getenv(OLLAMA_URL_ENV) or DEFAULT_OLLAMA_URL).rstrip("/")
        self.ollama_model = ollama_model
        self._post_json = post_json or _urllib_post_json

    # ------------------------------------------------------------------
    # Tool discovery
    # ------------------------------------------------------------------

    def tool_status(self) -> dict[str, str]:
        """Which external tools are present, for `status` and for the docs."""
        from .downloader import YTDLP

        return {
            YTDLP: _tool_state(YTDLP, "downloads"),
            FFPROBE: _tool_state(FFPROBE, "container metadata"),
            FFMPEG: _tool_state(FFMPEG, "scene detection"),
            WHISPER: _tool_state(WHISPER, "transcripts"),
        }

    # ------------------------------------------------------------------
    # ffprobe
    # ------------------------------------------------------------------

    def probe(self, media_path: str | os.PathLike[str]) -> MediaProbe:
        """Read duration, resolution, fps, format and bitrate.

        Raises:
            ToolMissingError: ffprobe is not installed.
            ExtractionError: the file is not a media container ffprobe can read.
        """
        path = Path(media_path)
        if not path.exists():
            raise ExtractionError(f"no such media file: {path}")

        result = self.runner(
            [
                FFPROBE,
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                str(path),
            ],
            120,
        )
        if not result.ok:
            raise ExtractionError(f"ffprobe could not read {path.name}: {result.tail(200)}")
        try:
            data = json.loads(result.stdout or "{}")
        except json.JSONDecodeError as exc:
            raise ExtractionError(f"ffprobe returned invalid JSON for {path.name}") from exc
        return MediaProbe.from_ffprobe(data, size_bytes=path.stat().st_size)

    # ------------------------------------------------------------------
    # Whisper
    # ------------------------------------------------------------------

    def transcript(
        self, media_path: str | os.PathLike[str], language: str = "es"
    ) -> TranscriptResult:
        """Transcribe speech, reusing a cached transcript when one is current.

        Returns an empty result (never an error) when Whisper is absent: a video
        without a transcript is still a useful reference, and the caller can see
        the reason in ``TranscriptResult.note``.
        """
        path = Path(media_path)
        cached = self.cache_dir / f"{path.stem}.txt"
        if cached.exists() and cached.stat().st_mtime >= path.stat().st_mtime:
            return TranscriptResult(
                text=cached.read_text(encoding="utf-8", errors="replace").strip(),
                language=language,
                engine="cache",
                note=f"reused {cached.name}",
            )

        if shutil.which(WHISPER) is None:
            return TranscriptResult(
                note="whisper not installed; no transcript stored", language=language
            )

        result = self.runner(
            [
                WHISPER,
                str(path),
                "--output_format",
                "txt",
                "--output_dir",
                str(self.cache_dir),
                "--language",
                language,
            ],
            TRANSCRIPT_TIMEOUT_SECS,
        )
        if not cached.exists():
            return TranscriptResult(
                text="",
                language=language,
                engine="whisper",
                note=f"whisper produced no transcript: {result.tail(200)}",
            )
        return TranscriptResult(
            text=cached.read_text(encoding="utf-8", errors="replace").strip(),
            language=language,
            engine="whisper",
            note=f"stored {cached.name}",
        )

    # ------------------------------------------------------------------
    # ffmpeg scene detection
    # ------------------------------------------------------------------

    def keyframes(
        self, media_path: str | os.PathLike[str], limit: int = MAX_KEYFRAMES
    ) -> list[str]:
        """Scene-change timestamps, or a single ``0:00 start`` marker if ffmpeg
        is missing. Never invents cuts: an unavailable detector yields a marker
        that says nothing about content.
        """
        path = Path(media_path)
        if shutil.which(FFMPEG) is None:
            return ["0:00 start (ffmpeg missing)"]

        result = self.runner(
            [
                FFMPEG,
                "-hide_banner",
                "-nostats",
                "-i",
                str(path),
                "-vf",
                f"select=gt(scene\\,{SCENE_THRESHOLD}),showinfo",
                "-an",
                "-f",
                "null",
                "-",
            ],
            900,
        )
        # ffmpeg exits 0 even when no scene passes the filter, so the parsed
        # timestamps are the signal, not the exit code.
        cuts: list[str] = []
        for match in _PTS_RE.finditer(result.stderr or ""):
            marker = f"{format_timestamp(float(match.group(1)))} scene change"
            if marker not in cuts:
                cuts.append(marker)
            if len(cuts) >= limit:
                break
        return cuts or ["0:00 start (no scene change detected)"]

    # ------------------------------------------------------------------
    # Summaries
    # ------------------------------------------------------------------

    def summarize(self, text: str, title: str = "", max_chars: int = 600) -> str:
        """Summarise a transcript, through Ollama when it answers.

        Falls back to the opening of the transcript, which is extractive and
        therefore always traceable to the source. Inventing a summary in the
        shape of one would be worse than useless to an agent deciding whether to
        watch the video.
        """
        clean = " ".join(text.split())
        if not clean:
            return ""
        try:
            payload = self._post_json(
                f"{self.ollama_url}/api/generate",
                {
                    "model": self.ollama_model,
                    "prompt": (
                        "Resume este video en 3 frases y usa el titulo como "
                        f"contexto. Titulo: {title or 'sin titulo'}\n\n"
                        f"Transcripcion:\n{clean[:8000]}"
                    ),
                    "stream": False,
                },
                60,
            )
            answer = str(payload.get("response", "")).strip()
            if answer:
                return answer[:max_chars]
        except (urllib.error.URLError, OSError, ValueError, TimeoutError):
            pass
        return _extractive_summary(clean, max_chars)


def _tool_state(tool: str, purpose: str) -> str:
    """``"available"`` or a reason it is not."""
    return "available" if shutil.which(tool) else f"missing ({purpose} unavailable)"


def _extractive_summary(text: str, max_chars: int) -> str:
    """First sentences of the transcript, cut on a word boundary."""
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars].rsplit(" ", 1)[0].rstrip(" ,;:")
    return f"{cut}…"


def _urllib_post_json(url: str, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
    """POST JSON with stdlib only, so a summary never depends on `requests`."""
    data = json.dumps(payload).encode()
    request = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        return json.loads(response.read().decode() or "{}")
