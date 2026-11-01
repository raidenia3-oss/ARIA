"""Gates for scripts/aria_eyes.py.

No network: a fake VisionClient stands in for the provider, so these run
anywhere. What is being protected is not accuracy of the model (unmeasurable
here) but the guarantees the module claims around it: coverage accounting,
graceful degradation, and the fact that secrets never reach the output.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys
from pathlib import Path

import pytest
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "aria_eyes.py"


def _load():
    spec = importlib.util.spec_from_file_location("aria_eyes_under_test", MODULE_PATH)
    assert spec and spec.loader, f"cannot import {MODULE_PATH}"
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


ae = _load()


class FakeClient:
    """Records prompts and returns canned replies, or raises."""

    def __init__(self, replies=None, error: Exception | None = None):
        self.model = "fake/vision"
        self.key_source = "test"
        self.calls: list[tuple[str, int]] = []
        self._replies = replies or []
        self._error = error

    def complete(self, prompt, images, max_tokens=None):
        self.calls.append((prompt, len(images)))
        if self._error is not None:
            raise self._error
        if self._replies:
            reply = self._replies.pop(0)
            return reply(prompt) if callable(reply) else reply
        return "{}"


def tile_json(**over):
    payload = {
        "tile": "r0c0",
        "summary": "a dark region",
        "objects": [{"what": "dot", "count": 1, "where": "centre", "confidence": "high"}],
        "colors": [],
        "text_present": False,
        "text_verbatim": "",
        "is_empty": False,
        "confidence": "high",
    }
    payload.update(over)
    import json

    return json.dumps(payload)


@pytest.fixture
def sheet() -> Image.Image:
    img = Image.new("RGB", (1920, 576), (16, 19, 30))
    for cx in (240, 720, 1200, 1680):
        for cy in (144, 432):
            for y in range(cy - 80, cy + 80):
                for x in range(cx - 80, cx + 80):
                    if (x - cx) ** 2 + (y - cy) ** 2 <= 80**2:
                        img.putpixel((x, y), (241, 135, 186))
    return img


# --------------------------------------------------------------------- repo root


def test_repo_root_lands_on_the_repo_not_a_parent():
    # The real module lives under scripts/, but tools/scripts is a junction to
    # scripts/, so depth arithmetic used to resolve one level too high.
    root = ae.REPO_ROOT
    assert any((root / m).exists() for m in ("pyproject.toml", ".git", "AGENTS.md"))
    assert (root / "scripts" / "aria_eyes.py").exists()
    assert root.name == "AURA"


def test_find_repo_root_prefers_a_marker_over_depth():
    root = ae.find_repo_root(ROOT / "scripts")
    assert root == ROOT


def test_env_candidates_are_relative_not_absolute():
    for rel in ae.ENV_CANDIDATES:
        assert not pathlib.Path(rel).is_absolute(), rel


# ------------------------------------------------------------------- tile geometry


@pytest.mark.parametrize("size,cols,rows", [((100, 100), 3, 3), ((1920, 576), 2, 2), ((64, 33), 4, 1)])
def test_tiles_cover_the_whole_image_without_overlap(size, cols, rows):
    tiles = ae.plan_tiles(size, cols, rows)
    assert len(tiles) == cols * rows
    area = sum((b[2] - b[0]) * (b[3] - b[1]) for b in (t.box for t in tiles))
    assert area == size[0] * size[1]


def test_tile_boxes_start_at_origin_and_end_at_the_far_edge():
    tiles = ae.plan_tiles((960, 540), 2, 2)
    assert min(b[0] for b in (t.box for t in tiles)) == 0
    assert min(b[1] for b in (t.box for t in tiles)) == 0
    assert max(b[2] for b in (t.box for t in tiles)) == 960
    assert max(b[3] for b in (t.box for t in tiles)) == 540


def test_tile_labels_are_unique():
    tiles = ae.plan_tiles((100, 100), 4, 4)
    assert len({t.label for t in tiles}) == 16


# ----------------------------------------------------------------- json hardening


@pytest.mark.parametrize(
    "raw",
    [
        '{"a": 1}',
        '```json\n{"a": 1}\n```',
        'Here you go:\n{"a": 1}\nHope that helps.',
        '  \n{"a": 1}  \n',
    ],
)
def test_parse_json_object_accepts_real_world_wrappers(raw):
    assert ae.parse_json_object(raw) == {"a": 1}


@pytest.mark.parametrize("raw", ["not json at all", "", "{unclosed", "[]", None])
def test_parse_json_object_rejects_garbage_instead_of_guessing(raw):
    assert ae.parse_json_object(raw) is None


# --------------------------------------------------------------- stage 1 accuracy


def test_measured_facts_are_exact_not_estimated(sheet):
    facts = ae.deterministic_facts(sheet)
    assert facts["width"] == 1920
    assert facts["height"] == 576
    assert facts["aspect"] == pytest.approx(1920 / 576, abs=1e-3)
    assert facts["measured_by"].startswith("PIL")
    assert facts["mean_luminance"] > 0
    hexes = [c["hex"] for c in facts["dominant_colors"]]
    assert hexes[0] == "#10131e"
    assert sum(c["share_pct"] for c in facts["dominant_colors"]) < 100


def test_measured_facts_keep_the_luminance_map_as_readable_text(sheet):
    rows = ae.deterministic_facts(sheet)["luminance_map"]
    assert rows and all(isinstance(r, str) for r in rows)
    assert max(len(r) for r in rows) <= 64


# ------------------------------------------------------------- stage 2 accounting


def test_full_coverage_when_every_tile_answers(sheet):
    sweep = ae.tile_sweep(sheet, FakeClient(replies=[tile_json()] * 4), 2, 2, None)
    assert sweep["tiles_answered"] == 4
    assert sweep["tiles_planned"] == 4
    assert sweep["coverage_pct"] == 100.0
    assert sweep["grid"] == "2x2"


def test_coverage_drops_and_is_reported_when_tiles_go_unanswered(sheet):
    sweep = ae.tile_sweep(sheet, FakeClient(replies=[tile_json(), "garbage", "", "{}"]), 2, 2, None)
    assert sweep["tiles_answered"] == 2
    assert sweep["coverage_pct"] == 50.0


def test_empty_json_object_counts_as_answered_not_as_a_failure(sheet):
    # bool({}) is False in Python; an empty-but-valid reply must not be scored
    # as an unparsed tile or coverage silently under-reports.
    sweep = ae.tile_sweep(sheet, FakeClient(replies=["{}"] * 4), 2, 2, None)
    assert sweep["tiles_answered"] == 4
    assert sweep["coverage_pct"] == 100.0


def test_one_dead_tile_does_not_abort_the_sweep(sheet):
    class Flaky(FakeClient):
        def complete(self, prompt, images, max_tokens=None):
            self.calls.append((prompt, len(images)))
            if len(self.calls) == 2:
                raise RuntimeError("boom")
            return tile_json()

    sweep = ae.tile_sweep(sheet, Flaky(), 2, 2, None)
    assert sweep["tiles_answered"] == 3
    broken = [t for t in sweep["tiles"] if not t["parsed"]]
    assert len(broken) == 1
    assert "boom" in broken[0]["error"]


def test_sweep_sends_exactly_one_image_per_call(sheet):
    client = FakeClient(replies=[tile_json()] * 4)
    ae.tile_sweep(sheet, client, 2, 2, None)
    assert len(client.calls) == 4
    assert all(images == 1 for _, images in client.calls)


# --------------------------------------------------------------------- stage 5


def test_cross_check_flags_a_colour_the_measurement_does_not_support(sheet):
    facts = ae.deterministic_facts(sheet)
    report = "A bright red button sits in the corner against a black background."
    result = ae.cross_check(report, facts)
    assert any("red" in c for c in result["contradictions"])


def test_cross_check_stays_quiet_when_the_colour_is_real(sheet):
    facts = ae.deterministic_facts(sheet)
    result = ae.cross_check("A pink disc floats on a near-black background.", facts)
    assert result["contradictions"] == []


def test_cross_check_does_not_flag_a_rare_but_correct_colour():
    # Regression: the disc covers ~0.4% of the pixels. Gating the verdict on
    # coverage marked its correct colour as a contradiction, which is how a real
    # granite run produced 3 false alarms on "pink", "orange" and "yellow".
    from PIL import Image as _Image

    img = _Image.new("RGB", (200, 200), (16, 19, 30))
    for x in range(94, 106):
        for y in range(94, 106):
            img.putpixel((x, y), (239, 123, 119))  # salmon, the measured disc colour
    facts = ae.deterministic_facts(img)
    shares = {c["hex"]: c["share_pct"] for c in facts["dominant_colors"]}
    assert shares.get("#ef7b77", 0) < 0.5, "fixture should be a rare colour"
    result = ae.cross_check("a pink disc on a near black background", facts)
    assert result["contradictions"] == []
    assert result["approximate_matches"], "the measured colour should be reported as a match"


def test_cross_check_admits_it_cannot_check_geometry(sheet):
    result = ae.cross_check("there are seventeen objects", ae.deterministic_facts(sheet))
    assert "NOT auto-verified" in result["method"]


# ------------------------------------------------------------ graceful degradation


def test_describe_returns_measured_facts_even_when_the_provider_is_dead(sheet, tmp_path):
    path = tmp_path / "x.png"
    sheet.save(path)
    dead = FakeClient(error=RuntimeError("HTTP 402: no credits"))
    result = ae.describe(path, dead, cols=2, rows=2, log=lambda _m: None)
    unit = result["units"][0]
    assert unit["measured"]["width"] == 1920
    assert unit["tile_sweep"]["tiles_answered"] == 0
    assert unit["complete"] is False
    assert unit["stage_errors"]
    assert any("402" in e for e in unit["stage_errors"])


def test_describe_marks_a_clean_run_complete(sheet, tmp_path):
    path = tmp_path / "y.png"
    sheet.save(path)
    replies = [tile_json()] * 4 + ['{"lines": [], "total_lines": 0}'] + ["SUBJECT: x"] + [
        '{"unsupported": [], "missing": [], "verdict": "accurate"}'
    ]
    result = ae.describe(path, FakeClient(replies=replies), cols=2, rows=2, log=lambda _m: None)
    unit = result["units"][0]
    assert unit["stage_errors"] == []
    assert unit["complete"] is True
    assert unit["ocr"]["available"] is True


# ------------------------------------------------------------------- secret hygiene


def test_no_secret_value_is_embedded_in_the_source():
    text = MODULE_PATH.read_text(encoding="utf-8")
    assert "sk-or-v1-" not in text
    assert "sk-" not in text.replace("sk-or-v1-", "")


def test_rendered_report_never_echoes_the_credential(sheet, tmp_path):
    path = tmp_path / "z.png"
    sheet.save(path)
    client = FakeClient(error=RuntimeError("HTTP 401: rejected"))
    client.key_source = "file:ame_backend/.env.local"
    result = ae.describe(path, client, cols=2, rows=2, log=lambda _m: None)
    text = ae.render_text(result)
    assert "ame_backend/.env.local" in text or "incomplete" in text.lower()
    for candidate, _source in ae.resolve_api_keys():
        if len(candidate) > 12:
            assert candidate not in text


# ------------------------------------------------------------------ colour names


@pytest.mark.parametrize("word", sorted(ae.COLOR_WORDS))
def test_every_colour_word_has_three_components(word):
    assert len(ae.COLOR_WORDS[word]) == 3


def test_closest_colour_word_is_a_nearest_match():
    word, _ = ae._closest_color_word((238, 240, 245))
    assert word in ("white", "gray", "grey")


# ------------------------------------------------------------------- media loading


def _distinct_frames(n: int, size=(64, 48)):
    """Frames that differ, because PIL collapses identical animation frames."""
    out = []
    for i in range(n):
        im = Image.new("RGB", size, (239, 123, 119))
        im.paste(Image.new("RGB", (6, 12), (255, 255, 255)), (4 + i * 6, 12))
        out.append(im)
    return out


def test_palette_image_is_converted_so_colours_are_not_invented(tmp_path):
    # A mode "P" GIF reports palette index 0 where the real colour is
    # (239, 123, 119). Stage 1 measures pixels, so an unconverted palette image
    # makes the whole deterministic layer describe black.
    path = tmp_path / "p.gif"
    Image.new("RGB", (64, 48), (239, 123, 119)).save(path)
    assert Image.open(path).mode == "P", "fixture must actually be paletted"

    (label, img), = ae.load_source(path, 0)

    assert img.mode == "RGB"
    assert img.getpixel((1, 1)) == (239, 123, 119)


@pytest.mark.parametrize("ext", ["png", "jpg", "webp", "bmp", "tiff", "ppm", "pcx", "tga", "qoi"])
def test_common_photo_formats_load_as_rgb(tmp_path, ext):
    path = tmp_path / f"s.{ext}"
    Image.new("RGB", (64, 48), (16, 19, 30)).save(path)
    units = ae.load_source(path, 0)
    assert len(units) == 1
    assert units[0][1].mode == "RGB"


@pytest.mark.parametrize("ext", ["gif", "webp", "apng"])
def test_animated_images_yield_the_requested_frames(tmp_path, ext):
    path = tmp_path / f"a.{ext}"
    frames = _distinct_frames(6)
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=120, loop=0)
    if Image.open(path).n_frames == 1:
        pytest.skip(f"Pillow collapsed the {ext} animation")

    units = ae.load_source(path, 4)

    assert len(units) == 4
    assert all(img.mode == "RGB" for _, img in units)
    assert len({label for label, _ in units}) == 4, "labels must identify each frame"


def test_multipage_tiff_walks_its_pages(tmp_path):
    path = tmp_path / "pages.tiff"
    frames = _distinct_frames(3)
    frames[0].save(path, save_all=True, append_images=frames[1:])
    assert Image.open(path).n_frames == 3

    units = ae.load_source(path, 4)

    assert len(units) == 3
    assert all(img.mode == "RGB" for _, img in units)


@pytest.mark.parametrize(
    "ext,suffix_added",
    [("mp4", ""), ("mkv", ""), ("webm", ""), ("avi", ""), ("mov", ""),
     ("ts", ""), ("flv", ""), ("wmv", "")],
)
def test_video_containers_decode_without_extension_trust(tmp_path, ext, suffix_added):
    # .ts, .flv and .wmv were all routed to Pillow by the old suffix check and
    # died with UnidentifiedImageError even though PyAV decodes them fine.
    path = tmp_path / f"v{Path(ext).suffix}{suffix_added}"
    _write_video(path, ext)
    if not path.exists() or path.stat().st_size == 0:
        pytest.skip(f"this PyAV build cannot mux {ext}")

    units = ae.load_source(path, 4)

    assert len(units) == 4, f"{ext} should yield the requested frames"
    assert all(img.mode == "RGB" for _, img in units)


def test_non_seekable_stream_is_decoded_forward_not_dropped(tmp_path):
    # MPEG-TS reports a duration but only answers the first seek; accepting that
    # partial sample used to yield one frame where the file held twelve.
    path = tmp_path / "v.ts"
    _write_video(path, "ts")
    if not path.exists() or path.stat().st_size == 0:
        pytest.skip("this PyAV build cannot mux ts")

    units = ae.load_source(path, 4)

    assert len(units) == 4


def test_video_is_decoded_even_without_a_video_extension(tmp_path):
    # Routing must come from decoding, not from the suffix: a real clip named
    # .dat used to be handed to Pillow and die with UnidentifiedImageError.
    real = tmp_path / "clip.mp4"
    _write_video(real, "mp4")
    if not real.exists() or real.stat().st_size == 0:
        pytest.skip("this PyAV build cannot mux mp4")
    disguised = tmp_path / "clip.dat"
    disguised.write_bytes(real.read_bytes())

    units = ae.load_source(disguised, 4)

    assert len(units) == 4, "a real clip should decode whatever it is called"


def test_still_is_read_as_an_image_even_when_named_like_a_clip(tmp_path):
    import io

    buf = io.BytesIO()
    Image.new("RGB", (64, 48), (10, 20, 30)).save(buf, format="PNG")
    disguised = tmp_path / "still.mp4"
    disguised.write_bytes(buf.getvalue())

    units = ae.load_source(disguised, 0)

    assert len(units) == 1
    assert units[0][1].mode == "RGB" and units[0][1].size == (64, 48)


@pytest.mark.parametrize("name", ["photo.heic", "logo.svg", "shot.CR2", "art.eps"])
def test_undecodable_format_names_the_package_it_needs(tmp_path, name):
    path = tmp_path / name
    path.write_bytes(b"\x00\x01\x02not really an image\x00")
    with pytest.raises(RuntimeError) as err:
        ae.load_source(path, 0)
    hint = str(err.value)
    assert "needs" in hint
    assert any(token in hint for token in ("pip install", "Ghostscript")), hint


def test_missing_file_is_reported_before_any_decode(tmp_path):
    with pytest.raises(FileNotFoundError):
        ae.load_source(tmp_path / "nope.png", 0)


def test_optional_decoder_table_is_well_formed():
    for entry in ae.OPTIONAL_DECODERS:
        assert len(entry) == 3, entry
        suffixes, label, remedy = entry
        assert suffixes and all(s.startswith(".") for s in suffixes)
        assert label and remedy


def _write_video(path, ext):
    av = pytest.importorskip("av")
    numpy = pytest.importorskip("numpy")
    codecs = {
        "mp4": ("mpeg4", "mp4"), "mkv": ("mpeg4", "matroska"),
        "webm": ("libvpx-vp9", "webm"), "avi": ("mpeg4", "avi"),
        "mov": ("mpeg4", "mov"), "ts": ("mpeg2video", "mpegts"),
        "flv": ("flv", "flv"), "wmv": ("wmv2", "asf"),
    }
    codec, container = codecs[ext]
    with av.open(str(path), mode="w", format=container) as out:
        stream = out.add_stream(codec, rate=10)
        stream.width, stream.height, stream.pix_fmt = 64, 48, "yuv420p"
        for i in range(12):
            arr = numpy.full((48, 64, 3), (200, 30 + i, 30), dtype=numpy.uint8)
            for packet in stream.encode(av.VideoFrame.from_ndarray(arr, format="rgb24")):
                out.mux(packet)
        for packet in stream.encode():
            out.mux(packet)