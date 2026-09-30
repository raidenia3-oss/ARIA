"""Tests for the ARIA video reference library.

Everything here runs offline: no yt-dlp, no ffmpeg, no Whisper, no Discord. The
external tools are reached through an injected runner, so the tests exercise the
logic that decides *what* happens rather than the tools that do it.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from aria_video_library import (
    AgentNotifier,
    VideoIndexer,
    VideoLibrary,
    VideoLibraryStorage,
    VideoMetadata,
)
from aria_video_library.downloader import (
    VideoDownloader,
    build_video_id,
    infer_source,
    sanitize_component,
    url_fingerprint,
)
from aria_video_library.errors import (
    DownloadError,
    InsufficientSpaceError,
    StorageError,
    ToolMissingError,
)
from aria_video_library.extractor import (
    CommandResult,
    MediaExtractor,
    MediaProbe,
    TranscriptResult,
    format_timestamp,
)
from aria_video_library.indexer import FIELD_WEIGHTS
from aria_video_library.models import AgentNotification
from aria_video_library.storage import USB_PATH_ENV, resolve_usb_root

# ---------------------------------------------------------------------------
# Doubles
# ---------------------------------------------------------------------------


class FakeRunner:
    """Stand-in for :class:`SubprocessRunner` that replays canned results."""

    def __init__(self, responses: dict[str, CommandResult] | None = None) -> None:
        self.responses = responses or {}
        self.calls: list[tuple[str, ...]] = []
        self.on_call = None

    def __call__(self, argv, timeout: int = 300) -> CommandResult:  # noqa: ANN001
        args = tuple(str(part) for part in argv)
        self.calls.append(args)
        if self.on_call is not None:
            self.on_call(args)
        key = args[0]
        for name, response in self.responses.items():
            if key == name or args[0].endswith(name):
                return CommandResult(args, response.returncode, response.stdout, response.stderr)
        return CommandResult(args, 0, "", "")

    def called_with(self, needle: str) -> list[tuple[str, ...]]:
        return [call for call in self.calls if needle in call]


class FakeExtractor:
    """Extraction with fixed answers; no subprocess at all."""

    def __init__(self, cache_dir: Path, transcript: str = "hola mundo") -> None:
        self.cache_dir = cache_dir
        self.transcript_text = transcript
        self.probes = 0
        self.keyframe_calls = 0

    def probe(self, media_path):  # noqa: ANN001, ANN201
        self.probes += 1
        return MediaProbe(
            duration_seconds=93,
            height=1920,
            resolution="1920p",
            fps=29.97,
            format="mov,mp4,m4a",
            bitrate_kbps=4200,
            size_bytes=Path(media_path).stat().st_size,
        )

    def transcript(self, media_path, language: str = "es"):  # noqa: ANN001, ANN201
        return TranscriptResult(text=self.transcript_text, language=language, engine="fake")

    def keyframes(self, media_path, limit: int = 40):  # noqa: ANN001, ANN201
        self.keyframe_calls += 1
        return ["0:00 start", "0:31 scene change"]

    def summarize(self, text: str, title: str = "", max_chars: int = 600) -> str:
        return f"resumen de {title}" if text else ""

    def tool_status(self):  # noqa: ANN201
        return {"ffprobe": "available", "ffmpeg": "missing", "whisper": "missing"}


#: Pinned so generated ids — which embed the download date — never depend on
#: what day the suite happens to run.
FIXED_DATE = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)
#: The URL every download test uses; the video id embeds a hash of it.
REEL_URL = "https://instagram.com/reel/abc"


@pytest.fixture()
def storage(tmp_path: Path) -> VideoLibraryStorage:
    return VideoLibraryStorage(tmp_path / "usb")


def make_video(**overrides) -> VideoMetadata:
    payload = {
        "id": "instagram_ai-tools_20260930",
        "source_url": "https://instagram.com/reel/abc",
        "title": "AI Tools Episode 5",
        "date_downloaded": datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc),
        "duration_seconds": 125,
        "size_bytes": 1024,
        "format": "mp4",
        "resolution": "1080p",
        "fps": 30.0,
        "transcript": "hoy hablamos de agentes",
        "summary": "Un resumen sobre agentes",
        "keyframes": ["0:00 start"],
        "tags": ["ai", "tools"],
        "agent_type": "agent-image-analysis",
        "agent_notes": "reference for the orb",
        "relevance_score": 0.95,
    }
    payload.update(overrides)
    return VideoMetadata(**payload)


# ---------------------------------------------------------------------------
# models
# ---------------------------------------------------------------------------


class TestModels:
    def test_roundtrip_preserves_every_field(self):
        video = make_video()
        restored = VideoMetadata.from_dict(json.loads(json.dumps(video.to_dict(), default=str)))
        assert restored.id == video.id
        assert restored.duration_seconds == 125
        assert restored.tags == ["ai", "tools"]
        assert restored.date_downloaded == video.date_downloaded

    def test_from_dict_ignores_unknown_keys(self):
        restored = VideoMetadata.from_dict({"id": "x", "invented_later": 42})
        assert restored.id == "x"
        assert restored.resolution == "unknown"

    def test_from_dict_repairs_broken_fields(self):
        restored = VideoMetadata.from_dict(
            {"id": "x", "date_downloaded": "not a date", "tags": "not a list"}
        )
        assert isinstance(restored.date_downloaded, datetime)
        assert restored.tags == ["reference"]
        assert restored.keyframes == []

    def test_duration_display_variants(self):
        assert make_video(duration_seconds=0).duration_display == "0:00"
        assert make_video(duration_seconds=125).duration_display == "2:05"
        assert make_video(duration_seconds=3725).duration_display == "1:02:05"

    def test_short_summary_cuts_on_word_boundary(self):
        video = make_video(summary="palabra " * 100)
        assert video.short_summary(50).endswith("…")
        assert len(video.short_summary(50)) <= 51

    def test_notification_roundtrip(self):
        notification = AgentNotification("agent", "video", "why")
        restored = AgentNotification.from_dict(notification.to_dict())
        assert restored.agent_id == "agent"
        assert restored.read is False


# ---------------------------------------------------------------------------
# storage
# ---------------------------------------------------------------------------


class TestStorage:
    def test_layout_is_created(self, storage: VideoLibraryStorage):
        assert storage.video_dir.is_dir()
        assert storage.cache_dir.is_dir()
        assert storage.index_file.parent.is_dir()

    def test_explicit_root_wins_over_env(self, tmp_path: Path, monkeypatch):
        monkeypatch.setenv(USB_PATH_ENV, str(tmp_path / "from-env"))
        device = resolve_usb_root(tmp_path / "explicit")
        assert device.path == tmp_path / "explicit"
        assert device.source == "argument"

    def test_env_root_used_when_no_argument(self, tmp_path: Path, monkeypatch):
        monkeypatch.setenv(USB_PATH_ENV, str(tmp_path / "stick"))
        device = resolve_usb_root()
        assert device.path == tmp_path / "stick"
        assert device.source == f"${USB_PATH_ENV}"

    def test_blank_env_is_ignored(self, tmp_path: Path, monkeypatch):
        monkeypatch.setenv(USB_PATH_ENV, "   ")
        device = resolve_usb_root()
        assert device.path.is_absolute()
        assert device.source != f"${USB_PATH_ENV}"

    def test_missing_root_raises_storage_error(self, tmp_path: Path):
        blocker = tmp_path / "file.txt"
        blocker.write_text("not a directory")
        with pytest.raises(StorageError):
            VideoLibraryStorage(blocker / "usb")

    def test_find_video_handles_any_extension(self, storage: VideoLibraryStorage):
        (storage.video_dir / "clip_1.mp4").write_bytes(b"x")
        (storage.video_dir / "clip_2.mkv").write_bytes(b"x")
        assert storage.find_video("clip_1") is not None
        assert storage.find_video("clip_2").suffix == ".mkv"
        assert storage.find_video("clip_3") is None

    def test_used_bytes_counts_media_only(self, storage: VideoLibraryStorage):
        (storage.video_dir / "a.mp4").write_bytes(b"x" * 10)
        (storage.cache_dir / "a.txt").write_bytes(b"x" * 999)
        assert storage.used_bytes() == 10

    def test_ensure_capacity_rejects_impossible_download(self, storage, monkeypatch):
        monkeypatch.setattr(storage, "free_bytes", lambda: 100)
        with pytest.raises(InsufficientSpaceError):
            storage.ensure_capacity(expected_bytes=10_000)

    def test_ensure_capacity_accepts_headroom(self, storage, monkeypatch):
        monkeypatch.setattr(storage, "free_bytes", lambda: 10_000_000)
        storage.ensure_capacity(expected_bytes=1_000, margin_bytes=1_000)

    def test_report_describes_the_layout(self, storage: VideoLibraryStorage):
        report = storage.report()
        assert report["root"] == str(storage.root)
        assert report["videos"] == 0
        assert report["free_bytes"] > 0


# ---------------------------------------------------------------------------
# downloader
# ---------------------------------------------------------------------------


class TestDownloaderNaming:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("AI Tools Episode 5", "ai-tools-episode-5"),
            ("  Wow!!!  ", "wow"),
            ("", ""),
            ("Ñandú/ñandú", "and-and"),
            ("a" * 80, "a" * 40),
        ],
    )
    def test_sanitize_component(self, raw: str, expected: str):
        assert sanitize_component(raw) == expected

    @pytest.mark.parametrize(
        ("url", "expected"),
        [
            ("https://www.instagram.com/reel/abc", "instagram"),
            ("https://tiktok.com/@a/video/1", "tiktok"),
            ("https://youtu.be/abc", "youtube"),
            ("https://example.com/a.mp4", "web"),
            ("", "unknown"),
        ],
    )
    def test_infer_source(self, url: str, expected: str):
        assert infer_source(url) == expected

    def test_build_video_id_keeps_date_and_slug(self):
        when = datetime(2026, 9, 30, tzinfo=timezone.utc)
        video_id = build_video_id("https://instagram.com/reel/x", "AI Tools", when)
        assert video_id == f"instagram_ai-tools-{url_fingerprint('https://instagram.com/reel/x')}_20260930"

    def test_video_ids_do_not_collide_on_identical_titles(self):
        when = datetime(2026, 9, 30, tzinfo=timezone.utc)
        first = build_video_id("https://instagram.com/reel/one", "AI Tools", when)
        second = build_video_id("https://instagram.com/reel/two", "AI Tools", when)
        assert first != second
        assert build_video_id("https://instagram.com/reel/one", "AI Tools", when) == first

    def test_build_video_id_falls_back_to_url_path(self):
        when = datetime(2026, 9, 30, tzinfo=timezone.utc)
        video_id = build_video_id("https://instagram.com/reel/Some-Reel", "", when)
        assert video_id.startswith("instagram_some-reel-")
        assert video_id.endswith("_20260930")

    @pytest.mark.parametrize("url", ["file:///etc/passwd", "ftp://instagram.com/a", "not-a-url"])
    def test_non_http_urls_are_rejected(self, url: str, storage):
        downloader = VideoDownloader(storage, extractor=FakeExtractor(storage.cache_dir))
        with pytest.raises(DownloadError):
            downloader.download(url)


class TestDownloader:
    def _downloader(self, storage, responses=None, **kwargs):  # noqa: ANN001, ANN003
        extractor = FakeExtractor(storage.cache_dir)
        runner = FakeRunner(responses or {})
        kwargs.setdefault("clock", lambda: FIXED_DATE)
        return VideoDownloader(storage, extractor=extractor, runner=runner, **kwargs), runner

    def test_expected_size_prefers_reported_filesize(self):
        downloader, _ = None, None
        from aria_video_library.downloader import VideoDownloader as VD

        assert VD.expected_size(downloader, {"filesize": 123}) == 123
        assert VD.expected_size(downloader, {"filesize_approx": 456}) == 456
        assert VD.expected_size(downloader, {}) == 0

    def test_expected_size_falls_back_to_bitrate_estimate(self):
        from aria_video_library.downloader import VideoDownloader as VD

        assert VD.expected_size(None, {"duration": 10, "tbr": 800}) == 1_000_000

    def test_download_produces_full_metadata(self, storage, monkeypatch):
        monkeypatch.setattr(storage, "ensure_capacity", lambda *a, **k: None)
        media = storage.video_dir / (
            f"{build_video_id(REEL_URL, 'AI Tools Episode 5', FIXED_DATE)}.mp4"
        )

        def create(args):  # noqa: ANN001, ANN202
            media.write_bytes(b"x" * 2048)

        downloader, runner = self._downloader(
            storage,
            responses={
                "yt-dlp": CommandResult((), 0, json.dumps({"title": "AI Tools Episode 5"}), "")
            },
        )
        runner.on_call = create

        metadata = downloader.download(REEL_URL, tags=["ai"])
        assert metadata.title == "AI Tools Episode 5"
        assert metadata.duration_seconds == 93
        assert metadata.resolution == "1920p"
        assert metadata.format == "mov"
        assert metadata.tags == ["ai"]
        assert metadata.transcript == "hola mundo"
        assert metadata.keyframes == ["0:00 start", "0:31 scene change"]
        assert metadata.file_path.endswith(".mp4")

    def test_download_uses_expected_format_flags(self, storage, monkeypatch):
        monkeypatch.setattr(storage, "ensure_capacity", lambda *a, **k: None)
        media = storage.video_dir / f"{build_video_id(REEL_URL, 'clip', FIXED_DATE)}.mp4"

        def create(args):  # noqa: ANN001, ANN202
            if "--merge-output-format" in args:
                media.write_bytes(b"x")

        downloader, runner = self._downloader(
            storage, responses={"yt-dlp": CommandResult((), 0, json.dumps({"title": "clip"}), "")}
        )
        runner.on_call = create
        downloader.download(REEL_URL)
        fetch = runner.called_with("--merge-output-format")
        assert fetch, "yt-dlp was never asked to download"
        assert "bestvideo*+bestaudio/best" in fetch[0]

    def test_existing_file_is_not_downloaded_again(self, storage):
        (storage.video_dir / f"{build_video_id(REEL_URL, 'clip', FIXED_DATE)}.mp4").write_bytes(
            b"x" * 10
        )
        downloader, runner = self._downloader(
            storage, responses={"yt-dlp": CommandResult((), 0, json.dumps({"title": "clip"}), "")}
        )
        metadata = downloader.download(REEL_URL)
        assert "already on the library" in metadata.agent_notes
        assert not runner.called_with("--merge-output-format")

    def test_failed_download_raises_with_ytdlp_output(self, storage, monkeypatch):
        monkeypatch.setattr(storage, "ensure_capacity", lambda *a, **k: None)
        downloader, _ = self._downloader(storage)
        downloader.runner = FakeRunner(
            {"yt-dlp": CommandResult((), 1, "", "ERROR: private video")}
        )
        with pytest.raises(DownloadError, match="private video"):
            downloader.download(REEL_URL)

    def test_missing_tool_is_reported_honestly(self, storage, monkeypatch):
        monkeypatch.setattr(storage, "ensure_capacity", lambda *a, **k: None)

        def missing(argv, timeout=300):  # noqa: ANN001, ANN202
            raise ToolMissingError("yt-dlp", "install it with: pip install yt-dlp")

        downloader, _ = self._downloader(storage)
        downloader.runner = missing
        with pytest.raises(ToolMissingError):
            downloader.download(REEL_URL)

    def test_probe_remote_rejects_garbage_output(self, storage):
        downloader, _ = self._downloader(storage)
        downloader.runner = FakeRunner({"yt-dlp": CommandResult((), 0, "not json", "")})
        with pytest.raises(DownloadError):
            downloader.probe_remote(REEL_URL)


# ---------------------------------------------------------------------------
# extractor
# ---------------------------------------------------------------------------


class TestExtractor:
    def test_probe_parses_ffprobe_json(self, storage, tmp_path: Path):
        media = tmp_path / "clip.mp4"
        media.write_bytes(b"x" * 42)
        payload = json.dumps(
            {
                "format": {"duration": "93.4", "format_name": "mov,mp4", "bit_rate": "4200000"},
                "streams": [
                    {"codec_type": "audio"},
                    {"codec_type": "video", "height": 1920, "width": 1080, "avg_frame_rate": "30000/1001"},
                ],
            }
        )
        extractor = MediaExtractor(
            storage.cache_dir, runner=FakeRunner({"ffprobe": CommandResult((), 0, payload, "")})
        )
        probe = extractor.probe(media)
        assert probe.duration_seconds == 93
        assert probe.resolution == "1920p"
        assert probe.fps == pytest.approx(29.97, abs=0.01)
        assert probe.bitrate_kbps == 4200
        assert probe.size_bytes == 42

    def test_probe_failure_raises(self, storage, tmp_path: Path):
        media = tmp_path / "clip.mp4"
        media.write_bytes(b"x")
        extractor = MediaExtractor(
            storage.cache_dir, runner=FakeRunner({"ffprobe": CommandResult((), 1, "", "moov atom not found")})
        )
        from aria_video_library.errors import ExtractionError

        with pytest.raises(ExtractionError, match="moov atom"):
            extractor.probe(media)

    def test_missing_file_raises_before_running(self, storage):
        from aria_video_library.errors import ExtractionError

        extractor = MediaExtractor(storage.cache_dir, runner=FakeRunner())
        with pytest.raises(ExtractionError):
            extractor.probe(storage.video_dir / "absent.mp4")

    def test_transcript_reuses_cache(self, storage, tmp_path: Path):
        media = tmp_path / "clip.mp4"
        media.write_bytes(b"x")
        (storage.cache_dir / "clip.txt").write_text("cached transcript", encoding="utf-8")
        extractor = MediaExtractor(storage.cache_dir, runner=FakeRunner())
        result = extractor.transcript(media)
        assert result.text == "cached transcript"
        assert result.engine == "cache"

    def test_transcript_without_whisper_reports_why(self, storage, tmp_path: Path, monkeypatch):
        monkeypatch.setattr("shutil.which", lambda tool: None)
        media = tmp_path / "clip.mp4"
        media.write_bytes(b"x")
        result = MediaExtractor(storage.cache_dir, runner=FakeRunner()).transcript(media)
        assert result.text == ""
        assert "whisper not installed" in result.note

    def test_keyframes_parse_scene_timestamps(self, storage, tmp_path: Path, monkeypatch):
        monkeypatch.setattr("shutil.which", lambda tool: "/usr/bin/ffmpeg")
        media = tmp_path / "clip.mp4"
        media.write_bytes(b"x")
        stderr = (
            "[Parsed_showinfo_1] n:0 pts_time:1.5\n"
            "[Parsed_showinfo_1] n:1 pts_time:31.02\n"
            "[Parsed_showinfo_1] n:2 pts_time:1.5\n"
        )
        extractor = MediaExtractor(
            storage.cache_dir, runner=FakeRunner({"ffmpeg": CommandResult((), 0, "", stderr)})
        )
        assert extractor.keyframes(media) == ["0:02 scene change", "0:31 scene change"]

    def test_keyframes_without_ffmpeg_are_labelled(self, storage, tmp_path: Path, monkeypatch):
        monkeypatch.setattr("shutil.which", lambda tool: None)
        media = tmp_path / "clip.mp4"
        media.write_bytes(b"x")
        result = MediaExtractor(storage.cache_dir, runner=FakeRunner()).keyframes(media)
        assert result == ["0:00 start (ffmpeg missing)"]

    def test_summarize_uses_ollama_when_available(self, storage):
        def post(url, payload, timeout):  # noqa: ANN001, ANN201
            assert payload["stream"] is False
            return {"response": "Resumen generado por el modelo local."}

        extractor = MediaExtractor(storage.cache_dir, post_json=post)
        assert extractor.summarize("texto largo", title="AI Tools").startswith("Resumen generado")

    def test_summarize_falls_back_to_the_transcript_itself(self, storage):
        def post(url, payload, timeout):  # noqa: ANN001, ANN201
            raise OSError("connection refused")

        text = "primera frase. " * 40
        summary = MediaExtractor(storage.cache_dir, post_json=post).summarize(text, max_chars=100)
        assert summary.endswith("…")
        assert "primera frase" in summary

    def test_summarize_of_nothing_is_empty(self, storage):
        assert MediaExtractor(storage.cache_dir, post_json=lambda *a: {}).summarize("") == ""

    def test_tool_status_reports_absence(self, storage, monkeypatch):
        monkeypatch.setattr("shutil.which", lambda tool: None)
        status = MediaExtractor(storage.cache_dir, runner=FakeRunner()).tool_status()
        assert status["ffprobe"].startswith("missing")
        assert "transcripts" in status["whisper"]

    def test_tool_status_names_the_downloader(self, storage, monkeypatch):
        # yt-dlp is the one hard requirement: without it nothing can be added at
        # all, so `status` must not omit it while listing the optional tools.
        monkeypatch.setattr("shutil.which", lambda tool: None)
        status = MediaExtractor(storage.cache_dir, runner=FakeRunner()).tool_status()
        assert "yt-dlp" in status
        assert "downloads" in status["yt-dlp"]

    def test_format_timestamp(self):
        assert format_timestamp(0) == "0:00"
        assert format_timestamp(93.4) == "1:33"
        assert format_timestamp(-5) == "0:00"


# ---------------------------------------------------------------------------
# indexer
# ---------------------------------------------------------------------------


class TestIndexer:
    def test_add_and_read_back(self, storage):
        indexer = VideoIndexer(storage)
        assert indexer.add_video(make_video()) is True
        assert indexer.add_video(make_video()) is False
        assert len(indexer.list_videos()) == 1
        assert indexer.get("instagram_ai-tools_20260930").title == "AI Tools Episode 5"

    def test_upsert_refreshes_without_duplicating(self, storage):
        indexer = VideoIndexer(storage)
        indexer.add_video(make_video(summary="old"))
        indexer.add_video(make_video(summary="new"))
        videos = indexer.list_videos()
        assert len(videos) == 1
        assert videos[0].summary == "new"

    def test_search_ranks_title_over_transcript(self, storage):
        indexer = VideoIndexer(storage)
        indexer.add_video(make_video(id="b", title="unrelated", transcript="agents everywhere"))
        indexer.add_video(make_video(id="a", title="agents everywhere"))
        results = indexer.search("agents")
        assert [result.video.id for result in results] == ["a", "b"]
        assert results[0].matched == ["title"]

    def test_search_requires_every_term(self, storage):
        indexer = VideoIndexer(storage)
        indexer.add_video(make_video())
        assert len(indexer.search("episode tools")) >= 1
        assert indexer.search("kubernetes agent-tools") == []

    def test_search_matches_tags(self, storage):
        indexer = VideoIndexer(storage)
        indexer.add_video(make_video(tags=["reference", "insta"]))
        assert indexer.search("insta")[0].video.id == "instagram_ai-tools_20260930"

    def test_search_ignores_punctuation_and_short_tokens(self, storage):
        indexer = VideoIndexer(storage)
        indexer.add_video(make_video())
        assert indexer.search("!!!") == []
        assert indexer.search("") == []

    def test_search_respects_limit(self, storage):
        indexer = VideoIndexer(storage)
        for suffix in "abc":
            indexer.add_video(make_video(id=f"video_{suffix}", title="agents"))
        assert len(indexer.search("agents", limit=2)) == 2

    def test_search_finds_transcript_only_matches(self, storage):
        indexer = VideoIndexer(storage)
        indexer.add_video(
            make_video(id="t", title="untitled clip", tags=[], summary="", transcript="kubernetes")
        )
        assert indexer.search("kubernetes")[0].matched == ["transcript"]

    def test_remove_drops_entry_but_keeps_file(self, storage):
        indexer = VideoIndexer(storage)
        indexer.add_video(make_video())
        (storage.video_dir / "instagram_ai-tools_20260930.mp4").write_bytes(b"x")
        assert indexer.remove("instagram_ai-tools_20260930") is True
        assert indexer.remove("instagram_ai-tools_20260930") is False
        assert (storage.video_dir / "instagram_ai-tools_20260930.mp4").exists()

    def test_corrupt_index_is_quarantined_and_rebuilt(self, storage):
        indexer = VideoIndexer(storage)
        indexer.add_video(make_video())
        storage.index_file.write_text("{ this is not json", encoding="utf-8")
        (storage.video_dir / "orphan_clip.mp4").write_bytes(b"x" * 7)

        index = indexer.load()
        ids = {entry["id"] for entry in index["videos"]}
        assert "orphan_clip" in ids
        quarantined = list(storage.cache_dir.glob("index.json.corrupt-*"))
        assert quarantined, "the unreadable index was not moved aside"

    def test_rebuild_recovers_files_without_inventing_metadata(self, storage):
        indexer = VideoIndexer(storage)
        (storage.video_dir / "orphan_clip.mp4").write_bytes(b"x" * 7)
        index = indexer.rebuild_from_disk()
        entry = next(item for item in index["videos"] if item["id"] == "orphan_clip")
        assert entry["size_bytes"] == 7
        assert entry["duration_seconds"] == 0
        assert "Recovered from disk" in entry["agent_notes"]

    def test_missing_index_reads_as_empty(self, storage):
        assert VideoIndexer(storage).load()["videos"] == []

    def test_save_is_atomic_and_leaves_no_temp(self, storage):
        indexer = VideoIndexer(storage)
        indexer.add_video(make_video())
        assert not list(storage.index_file.parent.glob("*.tmp"))
        assert json.loads(storage.index_file.read_text(encoding="utf-8"))["total_videos"] == 1

    def test_stats_summarise_the_library(self, storage):
        indexer = VideoIndexer(storage)
        indexer.add_video(make_video())
        indexer.add_video(make_video(id="second", transcript="", tags=["ai"]))
        stats = indexer.stats()
        assert stats["total_videos"] == 2
        assert stats["total_duration"] == 250
        assert stats["with_transcript"] == 1
        assert stats["tags"]["ai"] == 2

    def test_field_weights_match_the_documented_ordering(self):
        assert FIELD_WEIGHTS["title"] > FIELD_WEIGHTS["tags"] > FIELD_WEIGHTS["summary"]
        assert FIELD_WEIGHTS["summary"] > FIELD_WEIGHTS["transcript"]


# ---------------------------------------------------------------------------
# notifier
# ---------------------------------------------------------------------------


class TestNotifier:
    def test_message_contains_what_the_agent_needs(self):
        from aria_video_library.agent_notifier import build_message

        message = build_message("agent-image-analysis", make_video())
        assert "AI Tools Episode 5" in message
        assert "2:05" in message
        assert "agent-image-analysis" in message
        assert "ai, tools" in message

    def test_message_never_contains_the_webhook(self):
        notifier = AgentNotifier(webhook="https://discord.com/api/webhooks/secret/token")
        outcome = notifier.notify_agent("agent", make_video())
        assert "secret" not in outcome.message

    def test_long_messages_are_truncated_for_discord(self):
        from aria_video_library.agent_notifier import truncate_message

        message = "\n".join(f"line {index}" for index in range(500))
        trimmed = truncate_message(message)
        assert len(trimmed) <= 2000
        assert trimmed.endswith("*(truncated)*")

    def test_short_messages_pass_through(self):
        from aria_video_library.agent_notifier import truncate_message

        assert truncate_message("hola") == "hola"

    def test_delivery_requires_a_webhook(self, storage):
        notifier = AgentNotifier(db_path=storage.root / "aura.db")
        outcome = notifier.notify_agent("agent", make_video())
        assert outcome.delivered is False
        assert outcome.stored is True
        assert "no Discord webhook" in outcome.detail

    def test_webhook_env_is_resolved(self, monkeypatch):
        from aria_video_library.agent_notifier import resolve_webhook

        monkeypatch.delenv("ARIA_VIDEO_WEBHOOK", raising=False)
        monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://example/hook")
        assert resolve_webhook() == "https://example/hook"
        assert resolve_webhook("https://explicit/hook") == "https://explicit/hook"

    def test_successful_post_is_reported_as_delivered(self, storage):
        seen = {}

        def post(url, payload, timeout):  # noqa: ANN001, ANN201
            seen["url"] = url
            seen["content"] = payload["content"]
            return 204

        notifier = AgentNotifier(
            webhook="https://example/hook", db_path=storage.root / "aura.db", post=post
        )
        outcome = notifier.notify_agent("agent", make_video(), context="for the orb work")
        assert outcome.delivered is True
        assert seen["url"] == "https://example/hook"
        assert "AI Tools Episode 5" in seen["content"]

    def test_rejected_post_is_not_delivered(self, storage):
        import urllib.error

        def post(url, payload, timeout):  # noqa: ANN001, ANN201
            raise urllib.error.HTTPError(url, 429, "slow down", {}, None)  # type: ignore[arg-type]

        notifier = AgentNotifier(
            webhook="https://example/hook", db_path=storage.root / "aura.db", post=post
        )
        outcome = notifier.notify_agent("agent", make_video())
        assert outcome.delivered is False
        assert outcome.stored is True

    def test_notifications_are_queued_and_acknowledged(self, storage):
        notifier = AgentNotifier(db_path=storage.root / "aura.db")
        notifier.notify_agent("agent-a", make_video())
        notifier.notify_agent("agent-b", make_video(id="other"))

        pending = notifier.pending("agent-a")
        assert len(pending) == 1
        assert pending[0].video_id == "instagram_ai-tools_20260930"
        assert notifier.mark_read("agent-a", "instagram_ai-tools_20260930") == 1
        assert notifier.pending("agent-a") == []

    def test_stored_message_is_recoverable(self, storage):
        notifier = AgentNotifier(db_path=storage.root / "aura.db")
        notifier.notify_agent("agent", make_video())
        assert "AI Tools" in (notifier.message_for("instagram_ai-tools_20260930") or "")

    def test_agent_id_is_required(self, storage):
        notifier = AgentNotifier(db_path=storage.root / "aura.db")
        with pytest.raises(ValueError):
            notifier.notify_agent("", make_video())

    def test_database_failure_does_not_erase_the_message(self, storage):
        notifier = AgentNotifier(db_path=storage.root / "nested" / "deep" / "aura.db")
        outcome = notifier.notify_agent("agent", make_video())
        assert outcome.message
        assert isinstance(outcome.stored, bool)


# ---------------------------------------------------------------------------
# library facade + CLI
# ---------------------------------------------------------------------------


def build_library(tmp_path: Path):
    storage = VideoLibraryStorage(tmp_path / "usb")
    extractor = FakeExtractor(storage.cache_dir)
    runner = FakeRunner({"yt-dlp": CommandResult((), 0, json.dumps({"title": "AI Tools Episode 5"}), "")})
    media = storage.video_dir / f"{build_video_id(REEL_URL, 'AI Tools Episode 5', FIXED_DATE)}.mp4"

    def create(args):  # noqa: ANN001, ANN202
        if "--merge-output-format" in args:
            media.write_bytes(b"x" * 512)

    runner.on_call = create
    downloader = VideoDownloader(
        storage, extractor=extractor, runner=runner, clock=lambda: FIXED_DATE
    )
    notifier = AgentNotifier(db_path=tmp_path / "aura.db")
    library = VideoLibrary(
        storage=storage, downloader=downloader, notifier=notifier, indexer=VideoIndexer(storage)
    )
    return library, storage, notifier


class TestLibrary:
    def test_add_reference_downloads_indexes_and_notifies(self, tmp_path: Path):
        library, storage, notifier = build_library(tmp_path)
        result = library.add_reference(
            "https://instagram.com/reel/abc",
            tags=["ai", "tools"],
            agent_type="agent-image-analysis",
            context="reference for the orb",
        )
        assert result.added is True
        assert result.notified is not None
        assert result.notified.notification.agent_id == "agent-image-analysis"
        assert notifier.pending("agent-image-analysis")[0].context == "reference for the orb"
        assert VideoIndexer(storage).list_videos()[0].id == result.video.id

    def test_no_notification_without_an_agent(self, tmp_path: Path):
        library, _, _ = build_library(tmp_path)
        result = library.add_reference(REEL_URL, tags=["ai"])
        assert result.notified is None

    def test_notify_can_be_skipped(self, tmp_path: Path):
        library, _, notifier = build_library(tmp_path)
        library.add_reference(REEL_URL, agent_type="agent", notify=False)
        assert notifier.pending("agent") == []

    def test_failures_surface_as_exceptions(self, tmp_path: Path):
        library, _, _ = build_library(tmp_path)
        with pytest.raises(DownloadError):
            library.add_reference("file:///etc/passwd")

    def test_search_and_status(self, tmp_path: Path):
        library, storage, _ = build_library(tmp_path)
        library.add_reference(REEL_URL, tags=["ai"])
        assert library.search("episode")[0].video.id.startswith("instagram_")
        status = library.status()
        assert status["storage"]["root"] == str(storage.root)
        assert status["tools"]["whisper"].startswith("missing")
        assert status["index"]["total_videos"] == 1

    def test_added_twice_refreshes_the_index(self, tmp_path: Path):
        library, _, _ = build_library(tmp_path)
        first = library.add_reference(REEL_URL, tags=["ai"])
        second = library.add_reference(REEL_URL, tags=["ai"])
        assert first.added is True
        assert second.added is False
        assert len(library.list_references()) == 1


class TestCli:
    def test_status_renders(self, tmp_path: Path):
        from click.testing import CliRunner

        from aria_video_library.cli import main

        result = CliRunner().invoke(main, ["--root", str(tmp_path / "usb"), "status"])
        assert result.exit_code == 0, result.output
        assert "ARIA video reference library" in result.output

    def test_download_json_output(self, tmp_path: Path, monkeypatch):
        from click.testing import CliRunner

        import aria_video_library.cli as cli_module

        library, _, _ = build_library(tmp_path)
        monkeypatch.setattr(cli_module, "VideoLibrary", lambda root=None: library)
        result = CliRunner().invoke(
            cli_module.main,
            ["--root", str(tmp_path / "usb"), "download", "https://instagram.com/reel/abc", "--json"],
        )
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["status"] == "success"
        assert payload["video"]["tags"] == ["reference"]

    def test_search_reports_no_hits(self, tmp_path: Path):
        from click.testing import CliRunner

        from aria_video_library.cli import main

        result = CliRunner().invoke(
            main, ["--root", str(tmp_path / "usb"), "search", "kubernetes"]
        )
        assert result.exit_code == 0
        assert "no reference matches" in result.output

    def test_info_of_unknown_video_fails_cleanly(self, tmp_path: Path):
        from click.testing import CliRunner

        from aria_video_library.cli import main

        result = CliRunner().invoke(main, ["--root", str(tmp_path / "usb"), "info", "nope"])
        assert result.exit_code != 0

    def test_rebuild_reports_the_count(self, tmp_path: Path):
        from click.testing import CliRunner

        from aria_video_library.cli import main

        storage = VideoLibraryStorage(tmp_path / "usb")
        (storage.video_dir / "orphan.mp4").write_bytes(b"x")
        result = CliRunner().invoke(
            main, ["--root", str(tmp_path / "usb"), "rebuild", "--json"]
        )
        assert result.exit_code == 0, result.output
        assert json.loads(result.output)["total_videos"] == 1


# ---------------------------------------------------------------------------
# Regressions for the review findings
# ---------------------------------------------------------------------------


class TestStorageHardening:
    """A partial download must never be mistaken for the stored video."""

    def test_partial_files_are_not_media(self, storage: VideoLibraryStorage):
        assert storage.is_media(storage.video_dir / "clip.mp4")
        assert storage.is_media(storage.video_dir / "clip.mkv")
        assert not storage.is_media(storage.video_dir / "clip.mp4.part")
        assert not storage.is_media(storage.video_dir / "clip.ytdl")
        # yt-dlp's unmerged stream components share the id and the container.
        assert not storage.is_media(storage.video_dir / "clip.f137.mp4")
        assert not storage.is_media(storage.video_dir / "clip.txt")

    def test_find_video_ignores_a_leftover_part_file(self, storage: VideoLibraryStorage):
        (storage.video_dir / "clip.mp4.part").write_bytes(b"x" * 10)
        assert storage.find_video("clip") is None

    def test_find_video_ignores_unmerged_components(self, storage: VideoLibraryStorage):
        (storage.video_dir / "clip.f137.mp4").write_bytes(b"x" * 10)
        (storage.video_dir / "clip.f140.m4a").write_bytes(b"x" * 10)
        assert storage.find_video("clip") is None

    def test_cleanup_partials_removes_only_leftovers(self, storage: VideoLibraryStorage):
        (storage.video_dir / "keep.mp4").write_bytes(b"x")
        (storage.video_dir / "keep.mp4.part").write_bytes(b"x")
        (storage.video_dir / "keep.f137.mp4").write_bytes(b"x")
        assert storage.cleanup_partials("keep") == 2
        assert (storage.video_dir / "keep.mp4").exists()
        assert not (storage.video_dir / "keep.mp4.part").exists()

    def test_ambiguous_removable_drives_fall_back(self, tmp_path: Path, monkeypatch):
        monkeypatch.delenv(USB_PATH_ENV, raising=False)
        monkeypatch.setattr(
            "aria_video_library.storage._windows_removable_drives",
            lambda: [Path("D:/"), Path("E:/")],
        )
        device = resolve_usb_root()
        assert device.removable is False
        assert device.source == "fallback"

    def test_single_removable_drive_is_used(self, tmp_path: Path, monkeypatch):
        monkeypatch.delenv(USB_PATH_ENV, raising=False)
        monkeypatch.setattr(
            "aria_video_library.storage._windows_removable_drives",
            lambda: [Path("E:/")],
        )
        assert resolve_usb_root().path == Path("E:/")

    def test_report_counts_only_media_and_reports_cache(self, storage: VideoLibraryStorage):
        (storage.video_dir / "a.mp4").write_bytes(b"x" * 5)
        (storage.video_dir / "a.mp4.part").write_bytes(b"x" * 100)
        (storage.cache_dir / "a.txt").write_bytes(b"x" * 7)
        report = storage.report()
        assert report["videos"] == 1
        assert report["cache_bytes"] == 7


class TestIndexerHardening:
    def test_transient_read_error_does_not_quarantine(self, storage, monkeypatch):
        indexer = VideoIndexer(storage)
        indexer.add_video(make_video())
        before = json.loads(storage.index_file.read_text(encoding="utf-8"))
        monkeypatch.setattr(
            Path,
            "read_text",
            lambda *a, **k: (_ for _ in ()).throw(OSError("device not ready")),
        )
        with pytest.raises(OSError):
            indexer.load()
        monkeypatch.undo()
        assert json.loads(storage.index_file.read_text(encoding="utf-8")) == before
        assert not list(storage.cache_dir.glob("index.json.corrupt-*"))

    def test_newer_schema_is_refused_not_downgraded(self, storage):
        indexer = VideoIndexer(storage)
        storage.index_file.write_text(
            json.dumps({"schema_version": 99, "videos": [{"id": "x", "future_field": 1}]}),
            encoding="utf-8",
        )
        from aria_video_library.errors import IndexCorruptError

        with pytest.raises(IndexCorruptError, match="newer library"):
            indexer.load()
        # The file must be left exactly as it was found.
        assert "future_field" in storage.index_file.read_text(encoding="utf-8")

    def test_unknown_fields_survive_a_rewrite(self, storage):
        indexer = VideoIndexer(storage)
        storage.index_file.write_text(
            json.dumps({"videos": [{"id": "x", "title": "t", "future_field": "keep me"}]}),
            encoding="utf-8",
        )
        indexer.add_video(make_video(id="y"))
        raw = json.loads(storage.index_file.read_text(encoding="utf-8"))
        entry = next(item for item in raw["videos"] if item["id"] == "x")
        assert entry["future_field"] == "keep me"

    def test_readd_keeps_tags_and_agent(self, storage):
        indexer = VideoIndexer(storage)
        indexer.add_video(make_video(tags=["ai", "tools"], transcript="first take"))
        indexer.add_video(make_video(tags=None, transcript="", agent_type=None))
        stored = indexer.get("instagram_ai-tools_20260930")
        assert stored.tags == ["ai", "tools"]
        assert stored.transcript == "first take"
        assert stored.agent_type == "agent-image-analysis"

    def test_readd_still_refreshes_real_changes(self, storage):
        indexer = VideoIndexer(storage)
        indexer.add_video(make_video(summary="old", duration_seconds=10))
        indexer.add_video(make_video(summary="new", duration_seconds=20))
        stored = indexer.get("instagram_ai-tools_20260930")
        assert stored.summary == "new"
        assert stored.duration_seconds == 20

    def test_save_keeps_a_backup_of_the_last_good_index(self, storage):
        indexer = VideoIndexer(storage)
        indexer.add_video(make_video())
        indexer.add_video(make_video(id="second"))
        backup = storage.index_file.with_name("index.json.bak")
        assert backup.exists()
        assert len(json.loads(backup.read_text(encoding="utf-8"))["videos"]) == 1

    def test_backup_can_be_restored(self, storage):
        indexer = VideoIndexer(storage)
        indexer.add_video(make_video())
        indexer.add_video(make_video(id="second"))
        storage.index_file.write_text("broken", encoding="utf-8")
        assert indexer.restore_backup() is True
        assert len(indexer.list_videos()) == 1

    def test_quarantine_retention_is_bounded(self, storage):
        indexer = VideoIndexer(storage)
        for _ in range(5):
            storage.index_file.write_text("{ not json", encoding="utf-8")
            indexer.load()
        copies = list(storage.cache_dir.glob("index.json.corrupt-*"))
        assert len(copies) == 3

    def test_recovered_entries_use_utc(self, storage):
        indexer = VideoIndexer(storage)
        (storage.video_dir / "orphan.mp4").write_bytes(b"x")
        index = indexer.rebuild_from_disk()
        entry = next(item for item in index["videos"] if item["id"] == "orphan")
        assert entry["date_downloaded"].endswith("+00:00")

    def test_relevance_score_breaks_ties(self, storage):
        indexer = VideoIndexer(storage)
        indexer.add_video(make_video(id="low", title="agents", relevance_score=0.1))
        indexer.add_video(make_video(id="high", title="agents", relevance_score=0.99))
        assert [r.video.id for r in indexer.search("agents")] == ["high", "low"]

    def test_lock_file_is_not_left_behind_as_index_data(self, storage):
        indexer = VideoIndexer(storage)
        indexer.add_video(make_video())
        assert indexer.lock_file.parent == storage.index_file.parent
        assert "index.lock" not in storage.index_file.read_text(encoding="utf-8")


class TestDownloaderHardening:
    def test_failed_download_cleans_the_partial_file(self, storage, monkeypatch):
        monkeypatch.setattr(storage, "ensure_capacity", lambda *a, **k: None)
        from aria_video_library.downloader import VideoDownloader as VD

        media_id = build_video_id(REEL_URL, "clip", FIXED_DATE)
        runner = _failing_after_probe(FakeRunner(), media_id, storage)
        downloader = VD(
            storage,
            extractor=FakeExtractor(storage.cache_dir),
            runner=runner,
            clock=lambda: FIXED_DATE,
        )

        with pytest.raises(DownloadError):
            downloader.download(REEL_URL)
        assert not (storage.video_dir / f"{media_id}.mp4.part").exists()

    def test_fingerprint_is_stable_and_url_specific(self):
        assert url_fingerprint(REEL_URL) == url_fingerprint(REEL_URL)
        assert url_fingerprint(REEL_URL) != url_fingerprint("https://instagram.com/reel/other")
        assert len(url_fingerprint(REEL_URL)) == 6


def _failing_after_probe(runner, media_id, storage):  # noqa: ANN001, ANN201
    """Runner that reports a partial transfer and then fails the download."""
    probe_json = json.dumps({"title": "clip"})

    def dispatch(argv, timeout=300):  # noqa: ANN001, ANN202
        args = [str(part) for part in argv]
        if "--dump-single-json" in args:
            return CommandResult(tuple(args), 0, probe_json, "")
        if "--merge-output-format" in args:
            (storage.video_dir / f"{media_id}.mp4.part").write_bytes(b"partial")
            return CommandResult(tuple(args), 1, "", "ERROR: fragment 3 not found")
        return CommandResult(tuple(args), 0, "", "")

    runner.__call__ = dispatch  # type: ignore[method-assign]
    return runner


class TestNotifierHardening:
    def test_prune_drops_old_notifications(self, storage):
        notifier = AgentNotifier(db_path=storage.root / "aura.db")
        notifier.notify_agent("agent", make_video())
        assert notifier.prune(retention_days=3650) == 0
        assert notifier.prune(retention_days=0) == 1
        assert notifier.pending("agent") == []

    def test_non_lock_database_errors_are_reported_not_retried(self, storage, monkeypatch):
        notifier = AgentNotifier(db_path=storage.root / "aura.db")
        import sqlite3

        calls = []

        def explode(*args, **kwargs):  # noqa: ANN001, ANN002, ANN202
            calls.append(1)
            raise sqlite3.OperationalError("no such table: nope")

        monkeypatch.setattr(notifier, "_connect", explode)
        outcome = notifier.notify_agent("agent", make_video())
        assert outcome.stored is False
        assert len(calls) == 1  # not retried: it is not a lock error

    def test_lock_contention_is_retried(self, storage, monkeypatch):
        notifier = AgentNotifier(db_path=storage.root / "aura.db")
        import sqlite3

        attempts = {"n": 0}
        real_connect = notifier._connect

        class LockOnce:
            """Delegates to a real connection but fails the first INSERT."""

            def __init__(self, connection):  # noqa: ANN001
                self._connection = connection
                self.fail_next_insert = True

            def execute(self, sql, *a, **k):  # noqa: ANN001, ANN202
                if sql.strip().upper().startswith("INSERT") and self.fail_next_insert:
                    self.fail_next_insert = False
                    raise sqlite3.OperationalError("database is locked")
                return self._connection.execute(sql, *a, **k)

            def __getattr__(self, name):  # noqa: ANN001, ANN202
                return getattr(self._connection, name)

            def __enter__(self):  # noqa: ANN204
                return self

            def __exit__(self, *exc):  # noqa: ANN002, ANN204
                return self._connection.__exit__(*exc)

        def flaky():  # noqa: ANN202
            attempts["n"] += 1
            connection = real_connect()
            return LockOnce(connection) if attempts["n"] == 1 else connection

        monkeypatch.setattr(notifier, "_connect", flaky)
        outcome = notifier.notify_agent("agent", make_video())
        assert outcome.stored is True
        assert attempts["n"] >= 2
        assert notifier.pending("agent")


class TestLibraryClean:
    def test_clean_removes_partials_and_stale_cache(self, tmp_path: Path):
        library, storage, notifier = build_library(tmp_path)
        library.add_reference(REEL_URL, agent_type="agent")
        (storage.video_dir / "instagram_stale_20260101.mp4.part").write_bytes(b"x" * 100)
        (storage.cache_dir / "instagram_stale_20260101.txt").write_text("old", encoding="utf-8")
        (storage.cache_dir / "instagram_ai-tools-episode-5-0a5f26_20260930.txt").write_text(
            "keep", encoding="utf-8"
        )

        report = library.clean()
        assert report["partials_removed"] == 1
        assert report["cached_transcripts_removed"] == 1
        assert report["notifications_removed"] == 0
        assert notifier.pending("agent")

    def test_clean_can_drop_unindexed_media_only_with_the_flag(self, tmp_path: Path):
        library, storage, _ = build_library(tmp_path)
        library.add_reference(REEL_URL, tags=["ai"])
        orphan = storage.video_dir / "instagram_orphan_20260101.mp4"
        orphan.write_bytes(b"x" * 10)

        assert library.clean()["orphan_media_removed"] == 0
        assert orphan.exists()
        assert library.clean(drop_media=True)["orphan_media_removed"] == 1
        assert not orphan.exists()
        # The indexed video is never removed.
        assert storage.media_files()

    def test_clean_cli_reports_what_it_did(self, tmp_path: Path):
        from click.testing import CliRunner

        import aria_video_library.cli as cli_module

        library, storage, _ = build_library(tmp_path)
        (storage.video_dir / "instagram_orphan_20260101.mp4.part").write_bytes(b"x")
        CliRunner().invoke(cli_module.main, ["--root", str(tmp_path / "usb"), "clean", "--json"])
        result = CliRunner().invoke(
            cli_module.main, ["--root", str(tmp_path / "usb"), "clean", "--json"]
        )
        assert result.exit_code == 0, result.output
        assert json.loads(result.output)["partials_removed"] == 0
