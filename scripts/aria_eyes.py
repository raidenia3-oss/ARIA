#!/usr/bin/env python3
"""
ARIA Eyes — puente de vision semantica para agentes sin entrada de imagen.

Por que existe: el harness del agente descarta los adjuntos de imagen, asi que un
modelo de texto no puede "ver" un PNG aunque la herramienta lo entregue. Este
modulo manda la imagen a un modelo multimodal por HTTP y devuelve un informe
estructurado que un modelo de texto si puede leer.

La parte importante no es que el modelo describa, sino que no se salte nada. Un
modelo pedido "describe esta imagen" resume y descarta. Por eso el informe se
construye en cinco etapas:

  1. Hechos deterministas (local, sin modelo). Dimensiones, colores dominantes
     con su porcentaje, luminancia porRegion. Esto es aritmetica: no puede
     alucinar y es la referencia contra la que se mide todo lo demas.
  2. Barrido por mosaicos. Una llamada por tesela, cada una con esquema fijo.
     Un modelo covers lo que se le pide en pequenas dosis; asking por tiles
     convierte una sola peticion que resumiria en N peticiones que no pueden
     omitirse sin dejar un hueco visible.
  3. OCR aparte. El texto se pide en una llamada propia, sin la escena delante.
     Mezclar descripcion y transcripcion hace que el modelo invente texto que
     "encaja" con la imagen.
  4. Verificacion adversarial. Se devuelve la imagen original junto al informe y
     se pide listar toda afirmacion que la imagen NO respalda.
  5. Contraste determinista. Se comparan los colores que dice el modelo con los
     que se midieron. Las contradicciones se marcan, no se promedian.

Nada se presenta como verdad sin estar medido o marcado. Las afirmaciones que
no se pudieron verificar viajan en `unverified_claims`, no en el cuerpo.

Uso:
  python tools/scripts/aria_eyes.py describe IMG.png
  python tools/scripts/aria_eyes.py describe IMG.png --grid 4x3 --json
  python tools/scripts/aria_eyes.py describe CLIP.mp4 --frames 4
  python tools/scripts/aria_eyes.py doctor
"""

from __future__ import annotations

import argparse
import base64
import collections
import io
import json
import math
import os
import pathlib
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    print("Pillow is required: pip install Pillow", file=sys.stderr)
    raise

def find_repo_root(start: pathlib.Path) -> pathlib.Path:
    """Walk up until a repo marker appears.

    Depth arithmetic is unreliable here: tools/scripts is a junction to
    scripts/, so the same file answers to two different parent chains.
    """
    markers = ("pyproject.toml", ".git", "AGENTS.md")
    for candidate in [start, *start.parents]:
        if any((candidate / marker).exists() for marker in markers):
            return candidate
    return start.parents[1] if len(start.parents) > 1 else start


REPO_ROOT = find_repo_root(pathlib.Path(__file__).resolve().parent)

DEFAULT_MODEL = os.environ.get("ARIA_EYES_MODEL", "google/gemini-2.5-flash")
DEFAULT_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"

LOCAL_VISION_MODEL = os.environ.get("ARIA_EYES_LOCAL_MODEL", "granite3.2-vision:2b")
OLLAMA_ENDPOINT = os.environ.get("ARIA_EYES_OLLAMA_URL", "http://localhost:11434")

# Measured on this box, not guessed. granite3.2-vision:2b runs on CPU at
# ~3-5 tok/s and its projector has a hard floor of ~2242 visual tokens:
#   1920x576 -> 8074 tokens, ~273 s, miscounts the panels
#    960x288 -> 2971 tokens, ~110 s
#    640x192 -> 2242 tokens,  ~87 s, reads the labels better
#    480x270 -> 2242 tokens,  ~48 s, correct
# So smaller is both faster AND more accurate here. Downscaling caps cost.
LOCAL_MAX_SIDE = 768
LOCAL_CONTEXT = 4096

ENV_CANDIDATES = (
    ".env.ai",
    ".env",
    "ame_backend/.env.local",
    "backend/.env",
    "backend/.env.local",
    "ARIA_APP/.env",
)

RAMP = " .:-=+*#%@"


class VisionClient(Protocol):
    """Anything that can answer a text prompt about zero or more images."""

    def complete(self, prompt: str, images: list[Image.Image]) -> str: ...


# --------------------------------------------------------------------------- keys


def load_env_file(path: pathlib.Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        values[key.strip()] = value.strip().strip("'\"")
    return values


def resolve_api_keys() -> list[tuple[str, str]]:
    """Every candidate key, as (key, source_label), most specific source first.

    Order is NOT a reliability signal: .env.ai ships a 28-character placeholder
    while the working credential lives in ame_backend/.env.local. The client
    rotates through the list on 401 instead of trusting file order.
    """
    env_name = "OPENROUTER_API_KEY"
    found: list[tuple[str, str]] = []
    env_value = os.environ.get(env_name, "").strip()
    if env_value:
        found.append((env_value, f"environment:{env_name}"))
    for rel in ENV_CANDIDATES:
        value = load_env_file(REPO_ROOT / rel).get(env_name, "").strip()
        if value:
            found.append((value, f"file:{rel}"))
    seen: set[str] = set()
    unique: list[tuple[str, str]] = []
    for key, source in found:
        if key not in seen:
            seen.add(key)
            unique.append((key, source))
    return unique


def resolve_api_key() -> tuple[str, str]:
    """First candidate. Prefer resolve_api_keys() when actually calling."""
    candidates = resolve_api_keys()
    return candidates[0] if candidates else ("", "missing")


# --------------------------------------------------------------------------- client


class OpenRouterVision:
    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        endpoint: str = DEFAULT_ENDPOINT,
        timeout: float = 180.0,
        key: str | None = None,
        max_tokens: int = 1500,
        min_tokens: int = 256,
    ) -> None:
        self.model = model
        self.endpoint = endpoint
        self.timeout = timeout
        self.max_tokens = max_tokens
        self.min_tokens = min_tokens
        self._key = key
        self._candidates: list[str] | None = None
        self._index = 0
        self.key_source = "explicit" if key else "unresolved"

    def _candidates_list(self) -> list[str]:
        if self._candidates is None:
            if self._key:
                self._candidates = [self._key]
            else:
                pairs = resolve_api_keys()
                self._candidates = [k for k, _ in pairs]
                self.key_source = pairs[0][1] if pairs else "missing"
        return self._candidates

    @property
    def key(self) -> str:
        candidates = self._candidates_list()
        if not candidates:
            return ""
        self._index = min(self._index, len(candidates) - 1)
        return candidates[self._index]

    def _rotate(self) -> None:
        candidates = self._candidates_list()
        if self._index + 1 < len(candidates):
            self._index += 1

    def complete(self, prompt: str, images: list[Image.Image], max_tokens: int | None = None) -> str:
        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        for img in images:
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{encode_png(img)}"},
                }
            )
        budget = max_tokens or self.max_tokens
        attempts: list[str] = []
        for _ in range(len(self._candidates_list()) or 1):
            if not self.key:
                raise RuntimeError(
                    "no OPENROUTER_API_KEY; checked environment and "
                    + ", ".join(ENV_CANDIDATES)
                )
            body = {
                "model": self.model,
                "messages": [{"role": "user", "content": content}],
                "temperature": 0,
                "max_tokens": budget,
            }
            request = urllib.request.Request(
                self.endpoint,
                data=json.dumps(body).encode(),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.key}",
                },
            )
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    payload = json.loads(response.read())
                return payload["choices"][0]["message"]["content"]
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", "replace")[:240]
                if exc.code in (401, 403):
                    attempts.append(f"max_tokens={budget}: HTTP {exc.code} (key rejected)")
                    self._rotate()
                    continue
                if exc.code == 402 and "max_tokens" in detail and budget > self.min_tokens:
                    # Account credit cap: the provider states how much it can pay.
                    affordable = re.search(r"can only afford (\d+)", detail)
                    target = int(affordable.group(1)) if affordable else budget // 2
                    budget = max(self.min_tokens, min(budget - 1, target))
                    attempts.append(f"HTTP 402, budget -> {budget}")
                    continue
                raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
            except urllib.error.URLError as exc:
                raise RuntimeError(f"vision provider unreachable: {exc.reason}") from exc
        raise RuntimeError(
            "vision provider call failed after: " + "; ".join(attempts) if attempts
            else "vision provider call failed"
        )


def encode_png(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG", optimize=True)
    return base64.b64encode(buf.getvalue()).decode("ascii")


# --------------------------------------------------------------------------- stage 1


def dominant_colors(img: Image.Image, k: int = 6) -> list[dict[str, Any]]:
    small = img.convert("RGB").resize((180, 180), Image.BILINEAR)
    # getdata() is deprecated and removed in Pillow 14; get_flattened_data() is a
    # newer-Pillow method rather than the accessor, hence the call and the guard.
    flat = small.get_flattened_data() if hasattr(small, "get_flattened_data") else small.getdata()
    counts = collections.Counter(list(flat))
    total = sum(counts.values()) or 1
    picked: list[dict[str, Any]] = []
    for color, n in counts.most_common():
        if any(sum(abs(c - q[k]) for k, c in enumerate(color)) < 60 for q, _ in picked):
            continue
        picked.append((color, n / total))
        if len(picked) >= k:
            break
    return [
        {"rgb": list(rgb), "hex": "#%02x%02x%02x" % rgb, "share_pct": round(share * 100, 2)}
        for rgb, share in picked
    ]


def luminance_map(img: Image.Image, width: int = 64) -> list[str]:
    w, h = img.size
    height = max(1, round(width * h / w * 0.5))
    small = img.convert("L").resize((width, height), Image.BOX)
    px = small.load()
    return [
        "".join(RAMP[min(len(RAMP) - 1, px[x, y] * len(RAMP) // 256)] for x in range(width))
        for y in range(height)
    ]


def deterministic_facts(img: Image.Image) -> dict[str, Any]:
    w, h = img.size
    gray = img.convert("L")
    hist = gray.histogram()
    pixels = w * h or 1
    return {
        "width": w,
        "height": h,
        "aspect": round(w / h, 4) if h else None,
        "mean_luminance": round(sum(i * n for i, n in enumerate(hist)) / pixels, 2),
        "dark_pct": round(sum(hist[:64]) / pixels * 100, 2),
        "bright_pct": round(sum(hist[192:]) / pixels * 100, 2),
        "dominant_colors": dominant_colors(img),
        "luminance_map": luminance_map(img),
        "measured_by": "PIL (deterministic, not a model)",
    }


# --------------------------------------------------------------------------- stage 2


@dataclass(frozen=True)
class Tile:
    index: int
    row: int
    col: int
    box: tuple[int, int, int, int]

    @property
    def label(self) -> str:
        return f"r{self.row}c{self.col}"


def plan_tiles(size: tuple[int, int], cols: int, rows: int) -> list[Tile]:
    w, h = size
    tiles: list[Tile] = []
    for row in range(rows):
        for col in range(cols):
            x0 = round(col * w / cols)
            x1 = round((col + 1) * w / cols)
            y0 = round(row * h / rows)
            y1 = round((row + 1) * h / rows)
            tiles.append(Tile(len(tiles), row, col, (x0, y0, x1, y1)))
    return tiles


TILE_PROMPT = """You are describing ONE tile of a larger image, tile {label} of {total}.
The tile you were given is the crop. Do not describe anything outside it.

Answer with JSON only, no prose, no markdown fence. Every key is mandatory.

{{
  "tile": "{label}",
  "summary": "one sentence: what is in this tile, concrete nouns only",
  "objects": [{{"what": "noun", "count": 0, "where": "top-left|top-centre|top-right|centre-left|centre|centre-right|bottom-left|bottom-centre|bottom-right", "confidence": "high|medium|low"}}],
  "colors": [{{"what": "the thing", "color": "plain color name"}}],
  "text_present": true,
  "text_verbatim": "copy any characters EXACTLY as rendered, else empty string",
  "is_empty": false,
  "confidence": "high|medium|low"
}}

Rules:
- Set is_empty true ONLY if the tile genuinely has no content.
- Never invent text. If you cannot read it, text_present true and text_verbatim "".
- Never describe the whole image. Only this tile."""


def parse_json_object(text: str | None) -> dict[str, Any] | None:
    if not isinstance(text, str):
        return None
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        parsed = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def tile_sweep(
    img: Image.Image,
    client: VisionClient,
    cols: int = 3,
    rows: int = 3,
    on_progress: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    tiles = plan_tiles(img.size, cols, rows)
    results: list[dict[str, Any]] = []
    for tile in tiles:
        crop = img.crop(tile.box)
        prompt = TILE_PROMPT.format(label=tile.label, total=len(tiles))
        try:
            raw = client.complete(prompt, [crop])
            parsed = parse_json_object(raw)
        except Exception as exc:  # noqa: BLE001
            parsed, raw = None, f"ERROR: {exc}"
        # `bool({})` is False, so an empty-but-valid JSON object would otherwise be
        # miscounted as a failed tile.
        ok = parsed is not None
        entry: dict[str, Any] = {
            "tile": tile.label,
            "bbox": list(tile.box),
            "parsed": ok,
            "answer": parsed,
            "error": None if ok else str(raw)[:300],
        }
        results.append(entry)
        if on_progress:
            status = "ok" if parsed else "UNPARSED"
            on_progress(f"  tile {tile.label} {status}")
    answered = sum(1 for r in results if r["parsed"])
    empty = sum(1 for r in results if r["parsed"] and (r["answer"] or {}).get("is_empty"))
    return {
        "grid": f"{cols}x{rows}",
        "tiles_planned": len(tiles),
        "tiles_answered": answered,
        "tiles_reported_empty": empty,
        "coverage_pct": round(answered / len(tiles) * 100, 2) if tiles else 0.0,
        "tiles": results,
    }


# --------------------------------------------------------------------------- stage 3

OCR_PROMPT = """Transcribe every piece of text in this image.

Answer with JSON only:
{{
  "lines": [{{"text": "exact characters", "location": "where it sits, plain words"}}],
  "total_lines": 0,
  "illegible_regions": ["describe any text-shaped area you cannot read"]
}}

Rules:
- Copy characters exactly. Preserve case, punctuation and spacing.
- Never guess a word. If you cannot read it, list it under illegible_regions.
- If the image truly has no text, return an empty lines array."""


def ocr_pass(img: Image.Image, client: VisionClient) -> dict[str, Any]:
    try:
        raw = client.complete(OCR_PROMPT, [img])
        parsed = parse_json_object(raw)
    except Exception as exc:  # noqa: BLE001
        return {"available": False, "reason": str(exc)[:300], "lines": []}
    if parsed is None:
        return {"available": False, "reason": "unparsable reply", "lines": []}
    return {
        "available": True,
        "lines": parsed.get("lines", []),
        "total_lines": parsed.get("total_lines"),
        "illegible_regions": parsed.get("illegible_regions", []),
    }


# --------------------------------------------------------------------------- stages 4-5

ASSEMBLY_PROMPT = """Below are per-tile notes produced independently for one image,
plus measured pixel facts. Write the integrated description.

MEASURED (trustworthy, arithmetic):
{facts}

PER-TILE NOTES (untrusted, may contain mistakes):
{notes}

Write plain prose under these exact headings, and do not invent anything that the
notes or the measurements do not support.

SUBJECT: one sentence, what the image is of.
COMPOSITION: layout, grid, where things sit, how many.
TEXT: every string, verbatim. Write "no readable text" if the notes found none.
COLORS: the dominant colors, using the measured hex values where they apply.
MOTION: what changes across the image, or "static image".
UNSURE: everything you could not settle from the notes. Empty if nothing."""

VERIFY_PROMPT = """You are an adversarial checker. You have the original image and a
description someone wrote about it.

DESCRIPTION:
{report}

List every statement in that description that the image does NOT support, and
every important thing in the image the description MISSED.

Answer with JSON only:
{{
  "unsupported": ["exact claim that is wrong or invented"],
  "missing": ["important content absent from the description"],
  "verdict": "accurate" | "partly_wrong" | "wrong"
}}"""


def build_assembly_prompt(facts: dict[str, Any], sweep: dict[str, Any], ocr: dict[str, Any]) -> str:
    notes_lines = []
    for entry in sweep["tiles"]:
        answer = entry.get("answer") or {}
        if not entry["parsed"]:
            notes_lines.append(f"- {entry['tile']}: NOT ANALYSED ({entry['error']})")
            continue
        objects = ", ".join(
            f"{o.get('what')} x{o.get('count')} @{o.get('where')}" for o in answer.get("objects", [])
        )
        notes_lines.append(
            f"- {entry['tile']} bbox={entry['bbox']}: {answer.get('summary', '')}"
            f" | objects: {objects or 'none listed'}"
            f" | empty={answer.get('is_empty')}"
            f" | text={answer.get('text_verbatim') or '(none)'}"
        )
    ocr_lines = [f"- {ln.get('text')} @ {ln.get('location')}" for ln in ocr.get("lines", [])]
    facts_payload = {
        "width": facts["width"],
        "height": facts["height"],
        "dominant_colors": facts["dominant_colors"],
        "dark_pct": facts["dark_pct"],
        "bright_pct": facts["bright_pct"],
    }
    prompt = ASSEMBLY_PROMPT.format(
        facts=json.dumps(facts_payload, ensure_ascii=False),
        notes="\n".join(notes_lines) or "- nothing",
    )
    prompt += "\n\nOCR PASS:\n" + ("\n".join(ocr_lines) or "- no text detected")
    return prompt


def verify(img: Image.Image, report: str, client: VisionClient) -> dict[str, Any]:
    try:
        raw = client.complete(VERIFY_PROMPT.format(report=report), [img])
        parsed = parse_json_object(raw)
    except Exception as exc:  # noqa: BLE001
        return {"available": False, "reason": str(exc)[:300]}
    if parsed is None:
        return {"available": False, "reason": "unparsable reply"}
    return {
        "available": True,
        "unsupported": parsed.get("unsupported", []),
        "missing": parsed.get("missing", []),
        "verdict": parsed.get("verdict"),
    }


COLOR_WORDS = {
    "red": (220, 40, 40),
    "orange": (240, 140, 40),
    "yellow": (240, 220, 60),
    "green": (60, 200, 90),
    "cyan": (60, 200, 220),
    "blue": (60, 90, 220),
    "purple": (150, 60, 220),
    "magenta": (230, 60, 200),
    "pink": (240, 140, 200),
    "white": (245, 245, 245),
    "gray": (128, 128, 128),
    "grey": (128, 128, 128),
    "black": (15, 15, 20),
}

# Squared-distance cutoff between a colour word and its nearest measured colour.
# Tuned against a real granite3.2-vision:2b run on a salmon disc:
#   pink -> 83, orange -> 91, yellow -> 70  (correct, must stay quiet)
#   red  -> 116                           (genuinely wrong, must be flagged)
# Everything at or under the cutoff is reported as an APPROXIMATE match, never as
# verified: a green pixel is not proof of "cyan", and this check exists to catch
# gross colour hallucinations, not to adjudicate fine hue boundaries.
COLOR_DISTANCE_TOLERANCE = 110


def _closest_color_word(rgb: tuple[int, int, int]) -> tuple[str, int]:
    best, best_d = "unknown", 10**9
    for word, ref in COLOR_WORDS.items():
        d = sum((rgb[i] - ref[i]) ** 2 for i in range(3))
        if d < best_d:
            best, best_d = word, d
    return best, best_d


def cross_check(report: str, facts: dict[str, Any]) -> dict[str, Any]:
    """Compare colour words the model used against the measured palette.

    Coverage is deliberately NOT part of the verdict. A colour covering 0.1% of
    the pixels is exactly what you expect when the model is describing one small
    object, and gating on share_pct used to mark those correct answers as
    contradictions while letting any dominant colour pass unchecked.
    """
    measured = {c["hex"] for c in facts["dominant_colors"]}
    words = set(re.findall(r"\b(" + "|".join(COLOR_WORDS) + r")\b", report.lower()))
    unsupported: list[str] = []
    approximate: list[str] = []
    for word in sorted(words):
        ref = COLOR_WORDS[word]
        nearest = min(
            facts["dominant_colors"],
            key=lambda c: sum((c["rgb"][i] - ref[i]) ** 2 for i in range(3)),
        )
        distance = sum((nearest["rgb"][i] - ref[i]) ** 2 for i in range(3))
        note = f"closest measured {nearest['hex']} at {nearest['share_pct']}%"
        if distance > COLOR_DISTANCE_TOLERANCE**2:
            unsupported.append(f"report says '{word}' but nothing measured is close ({note})")
        else:
            approximate.append(f"'{word}' is approximately backed by {note}")
    return {
        "colour_words_in_report": sorted(words),
        "measured_hexes": sorted(measured),
        "approximate_matches": approximate,
        "contradictions": unsupported,
        "method": "colour words checked against PIL measurements; matches are "
        "approximate, and geometry and counts are NOT auto-verified",
    }


# --------------------------------------------------------------------------- media


VIDEO_SUFFIXES = frozenset({
    ".mp4", ".m4v", ".mov", ".mkv", ".webm", ".avi", ".wmv", ".asf", ".flv", ".f4v",
    ".ts", ".m2ts", ".mts", ".vob", ".ogv", ".3gp", ".3g2", ".mxf", ".rm", ".rmvb",
    ".mpg", ".mpeg", ".mpe", ".qt", ".divx", ".dv", ".y4m", ".gif-video",
})

# Pillow has no decoder for these. Naming the optional package beats a bare
# UnidentifiedImageError, so each entry is (suffixes, what it is, how to get it).
OPTIONAL_DECODERS = (
    ((".heic", ".heif"), "HEIF/HEIC (iPhone photos)", "pip install pillow-heif"),
    ((".svg", ".svgz"), "SVG (vector art)", "pip install cairosvg"),
    ((".eps", ".ps"), "EPS/PostScript", "Ghostscript"),
    ((".cr2", ".cr3", ".nef", ".nrw", ".arw", ".dng", ".raf", ".orf", ".rw2"),
     "RAW camera negative", "pip install rawpy"),
    ((".pdf",), "PDF document", "pip install pymupdf"),
)

PDF_SUFFIXES = frozenset({".pdf"})


def looks_like_video(path: pathlib.Path) -> bool:
    """Extension hint only. PyAV is the real authority, see _video_stream."""
    return path.suffix.lower() in VIDEO_SUFFIXES


def looks_like_pdf(path: pathlib.Path) -> bool:
    """PDF detection via extension."""
    return path.suffix.lower() in PDF_SUFFIXES


def missing_decoder_hint(path: pathlib.Path) -> str:
    for suffixes, label, remedy in OPTIONAL_DECODERS:
        if path.suffix.lower() in suffixes:
            if remedy.startswith("pip "):
                return f"{label} needs an optional decoder: {remedy}"
            return f"{label} needs {remedy} to be installed"
    return ""


def _video_stream(path: pathlib.Path):
    """Return an open PyAV container with a video stream, or None.

    Extension-agnostic on purpose: .ts/.flv/.wmv are real videos that PIL cannot
    read, and a video with no extension still decodes here.
    """
    try:
        import av
    except ImportError:
        return None
    try:
        container = av.open(str(path))
    except Exception:  # noqa: BLE001 - not a container we understand
        return None
    if not container.streams.video:
        container.close()
        return None
    return container


def video_frames(path: pathlib.Path, count: int) -> list[tuple[str, Image.Image]]:
    """Sample `count` frames spread across the timeline.

    Seeking is the fast path but it is not always available (raw streams, some
    .ts and .rm files). When it raises we decode forward and subsample instead of
    losing the source entirely.

    Never raises. Having a video stream is not proof the frames decode: an .svg
    or a .heic can be probed successfully and then fail at the decoder, and a
    probe crash must not mask the real, clearer error from the image path.
    """
    try:
        return _video_frames(path, count)
    except Exception:  # noqa: BLE001 - a partial sample beats an exception here
        return []


def _video_frames(path: pathlib.Path, count: int) -> list[tuple[str, Image.Image]]:
    import av

    container = _video_stream(path)
    if container is None:
        return []
    out: list[tuple[str, Image.Image]] = []
    try:
        stream = container.streams.video[0]
        stream.thread_type = "AUTO"
        duration = float(container.duration) / av.time_base if container.duration else 0.0
        if duration <= 0 and stream.frames and stream.average_rate:
            duration = stream.frames / float(stream.average_rate)

        wanted = max(count, 1)
        if duration > 0:
            picks = [duration * (i / wanted) for i in range(wanted)]
            for t in picks:
                try:
                    container.seek(
                        int(t * av.time_base), stream=stream,
                        any_frame=False, backward=True,
                    )
                except Exception:  # noqa: BLE001 - non-seekable source
                    break
                frame = next(container.decode(stream), None)
                if frame is not None:
                    out.append((f"t={t:.2f}s", _as_rgb(frame.to_image())))
            # A partial sample is worse than a full forward decode: .ts reports a
            # duration but only answers the first seek, which used to yield a
            # single frame where 12 were available.
            if len(out) == len(picks):
                return out
            out.clear()

        # Forward-decode fallback: resample in memory by frame position.
        container.close()
        container = _video_stream(path)
        if container is None:
            return []
        stream = container.streams.video[0]
        decoded = [f.to_image() for f in container.decode(stream)]
        if not decoded:
            return []
        step = max(len(decoded) // wanted, 1)
        for i in range(0, len(decoded), step):
            out.append((f"frame {i}", _as_rgb(decoded[i])))
            if len(out) >= wanted:
                break
        return out
    finally:
        try:
            container.close()
        except Exception:  # noqa: BLE001
            pass


def _as_rgb(img: Image.Image) -> Image.Image:
    """Force a detached RGB copy.

    This is not cosmetic. A paletted GIF read as mode "P" reports pixel (0, 0, 0)
    where the real colour is (239, 123, 119), so stage 1 would measure black and
    the vision model would be sent a palette it cannot read as colour. EXIF
    orientation is applied here too, because a photo stored sideways is a real
    scene rotated 90 degrees and every measured colour region moves with it.
    """
    try:
        from PIL import ImageOps

        img = ImageOps.exif_transpose(img) or img
    except Exception:  # noqa: BLE001 - missing/odd EXIF is not fatal
        pass
    return img.convert("RGB").copy()


def image_frames(path: pathlib.Path, count: int) -> list[tuple[str, Image.Image]]:
    """Open a still, animated or multi-page image.

    `count` beyond 1 walks animation frames / TIFF pages, so `--frames 4` means
    something sensible for a GIF instead of silently reporting only frame 0.
    """
    try:
        handle = Image.open(path)
    except Exception as exc:  # noqa: BLE001
        hint = missing_decoder_hint(path)
        raise RuntimeError(hint or f"Pillow cannot decode {path.name}: {exc}") from exc

    with handle:
        total = int(getattr(handle, "n_frames", 1) or 1)
        want = max(count, 1)
        if total <= 1 or want == 1:
            try:
                return [(path.name, _as_rgb(handle))]
            except Exception as exc:  # noqa: BLE001
                raise RuntimeError(
                    missing_decoder_hint(path)
                    or f"{path.name} opened but its pixels cannot be decoded "
                       f"({exc}); PostScript/EPS needs Ghostscript on PATH"
                ) from exc

        picks = sorted({min(int(i * total / want), total - 1) for i in range(want)})
        out: list[tuple[str, Image.Image]] = []
        for idx in picks:
            handle.seek(idx)
            out.append((f"{path.name} frame {idx}/{total}", _as_rgb(handle)))
        return out


def pdf_pages(path: pathlib.Path, count: int) -> list[tuple[str, Image.Image]]:
    """Render PDF pages to RGB images using PyMuPDF (fitz)."""
    try:
        import fitz
    except ImportError:
        raise RuntimeError("PDF needs PyMuPDF: pip install pymupdf")
    doc = fitz.open(str(path))
    total = doc.page_count
    want = max(count, 1)
    picks: list[int] = []
    if total <= want:
        picks = list(range(total))
    else:
        step = total / want
        picks = [min(int(i * step), total - 1) for i in range(want)]
    out: list[tuple[str, Image.Image]] = []
    for idx in picks:
        page = doc[idx]
        pix = page.get_pixmap(dpi=150)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        out.append((f"{path.name} page {idx+1}/{total}", _as_rgb(img)))
    doc.close()
    return out


def load_source(path: pathlib.Path, frames: int) -> list[tuple[str, Image.Image]]:
    """Decode any photo, animation, page stack or video into RGB frames.

    Routing is decided by trying decoders rather than by trusting the extension,
    because the two disagree in both directions: a .ts file is a video PIL cannot
    open at all, and a .webp file is a still that PyAV has no reason to touch.
    """
    if not path.exists():
        raise FileNotFoundError(f"no such file: {path}")

    want = max(frames, 1)

    if looks_like_pdf(path):
        return pdf_pages(path, want)

    if frames > 0 and looks_like_video(path):
        got = video_frames(path, want)
        if got:
            return got
        return image_frames(path, want)

    try:
        return image_frames(path, want)
    except Exception as image_exc:  # noqa: BLE001
        got = video_frames(path, want)
        if got:
            return got
        if looks_like_pdf(path):
            try:
                return pdf_pages(path, want)
            except RuntimeError as pdf_exc:
                raise RuntimeError(str(pdf_exc)) from pdf_exc
        if isinstance(image_exc, RuntimeError):
            raise
        hint = missing_decoder_hint(path)
        raise RuntimeError(hint or f"cannot decode {path.name}: {image_exc}") from image_exc


# --------------------------------------------------------------------------- orchestration


def describe(
    path: pathlib.Path,
    client: VisionClient,
    cols: int = 3,
    rows: int = 3,
    frames: int = 0,
    verify_report: bool = True,
    log: Callable[[str], None] = print,
) -> dict[str, Any]:
    sources = load_source(path, frames)
    if not sources:
        raise RuntimeError(f"no frames could be decoded from {path}")

    units: list[dict[str, Any]] = []
    for label, img in sources:
        log(f"[{label}] {img.size[0]}x{img.size[1]}")
        errors: list[str] = []

        # Stage 1 never touches the model, so it cannot fail for credit reasons.
        facts = deterministic_facts(img)
        log("  stage 1: measured pixel facts")

        # Stage 2 already isolates per-tile failures inside tile_sweep.
        sweep = tile_sweep(img, client, cols, rows, log)
        log(
            f"  stage 2: tile sweep {sweep['coverage_pct']}% "
            f"({sweep['tiles_answered']}/{sweep['tiles_planned']})"
        )

        ocr: dict[str, Any]
        try:
            ocr = ocr_pass(img, client)
            log(f"  stage 3: ocr available={ocr['available']} lines={len(ocr.get('lines', []))}")
        except Exception as exc:  # noqa: BLE001
            ocr = {"available": False, "reason": str(exc)[:300], "lines": []}
            errors.append(f"ocr: {exc}")
            log("  stage 3: FAILED")

        # A narrative is nice to have; measured facts and tiles are the substance.
        try:
            report = client.complete(build_assembly_prompt(facts, sweep, ocr), [img])
            log("  stage 4: assembled narrative")
        except Exception as exc:  # noqa: BLE001
            report = f"[narrative unavailable: {exc}]"
            errors.append(f"narrative: {exc}")
            log("  stage 4: FAILED")

        check: dict[str, Any] = {"available": False, "reason": "skipped"}
        if verify_report:
            try:
                check = verify(img, report, client)
                log(f"  stage 5: verification verdict={check.get('verdict')}")
            except Exception as exc:  # noqa: BLE001
                check = {"available": False, "reason": str(exc)[:300]}
                errors.append(f"verification: {exc}")
                log("  stage 5: FAILED")

        xcheck = cross_check(report, facts)
        contradictions = xcheck["contradictions"]
        log(f"  stage 6: colour cross-check contradictions={len(contradictions)}")

        unverified = list(check.get("unsupported", [])) + contradictions

        units.append(
            {
                "label": label,
                "measured": facts,
                "tile_sweep": sweep,
                "ocr": ocr,
                "narrative": report,
                "verification": check,
                "cross_check": xcheck,
                "unverified_claims": unverified,
                "stage_errors": errors,
                "complete": not errors,
                "trust": {
                    "measured": "arithmetic",
                    "tiles": "model, per-tile",
                    "ocr": "model, verbatim request",
                    "narrative": "derived from the above",
                },
            }
        )

    return {
        "source": str(path),
        "model": getattr(client, "model", type(client).__name__),
        "credential": getattr(client, "key_source", "unknown"),
        "units": units,
        "caveat": "Model output is not a measurement. Trust `measured` blindly; "
        "everything else is checked, not guaranteed.",
    }


# --------------------------------------------------------------------------- text report


def render_text(result: dict[str, Any]) -> str:
    out: list[str] = []
    out.append(f"SOURCE: {result['source']}")
    out.append(f"MODEL:   {result['model']}")
    out.append(f"CAVEAT:  {result['caveat']}")
    for unit in result["units"]:
        m = unit["measured"]
        out.append("")
        out.append("=" * 72)
        out.append(f"UNIT {unit['label']}  {m['width']}x{m['height']}")
        out.append("=" * 72)
        out.append("-- MEASURED (trustworthy) --")
        out.append(
            f"size={m['width']}x{m['height']} aspect={m['aspect']} "
            f"mean_luma={m['mean_luminance']} dark={m['dark_pct']}% bright={m['bright_pct']}%"
        )
        for c in m["dominant_colors"]:
            out.append(f"  colour {c['hex']} rgb{c['rgb']} {c['share_pct']}%")
        out.append("  luminance map:")
        for row in m["luminance_map"]:
            out.append(f"    |{row}|")
        sweep = unit["tile_sweep"]
        out.append(
            f"-- TILE SWEEP {sweep['grid']} coverage={sweep['coverage_pct']}% "
            f"({sweep['tiles_answered']}/{sweep['tiles_planned']}) --"
        )
        for entry in sweep["tiles"]:
            if not entry["parsed"]:
                out.append(f"  {entry['tile']} bbox={entry['bbox']} NOT ANALYSED")
                continue
            a = entry["answer"]
            out.append(f"  {entry['tile']} bbox={entry['bbox']} {a.get('summary', '')}")
            for o in a.get("objects", []):
                out.append(
                    f"      - {o.get('what')} x{o.get('count')} @{o.get('where')} "
                    f"[{o.get('confidence')}]"
                )
            if a.get("text_verbatim"):
                out.append(f"      text: {a['text_verbatim']!r}")
        out.append("-- OCR --")
        ocr = unit["ocr"]
        if not ocr["available"]:
            out.append(f"  unavailable: {ocr.get('reason')}")
        elif not ocr["lines"]:
            out.append("  no text detected")
        else:
            for ln in ocr["lines"]:
                out.append(f"  {ln.get('text')!r} @ {ln.get('location')}")
        out.append("-- NARRATIVE --")
        out.append(unit["narrative"].strip())
        v = unit["verification"]
        out.append("-- VERIFICATION --")
        if not v["available"]:
            out.append(f"  unavailable: {v.get('reason')}")
        else:
            out.append(f"  verdict: {v.get('verdict')}")
            for claim in v.get("unsupported", []):
                out.append(f"  UNSUPPORTED: {claim}")
            for miss in v.get("missing", []):
                out.append(f"  MISSING: {miss}")
        out.append("-- CROSS CHECK --")
        for c in unit["cross_check"]["contradictions"]:
            out.append(f"  CONTRADICTION: {c}")
        for c in unit["cross_check"].get("approximate_matches", []):
            out.append(f"  approximate: {c}")
        if not unit["cross_check"]["contradictions"]:
            out.append("  no colour contradictions detected")
        if unit["unverified_claims"]:
            out.append(f"-- {len(unit['unverified_claims'])} UNVERIFIED CLAIM(S): DO NOT TRUST --")
        if unit["stage_errors"]:
            out.append(f"-- {len(unit['stage_errors'])} STAGE(S) INCOMPLETE --")
            for err in unit["stage_errors"]:
                out.append(f"  {err}")
    return "\n".join(out)


class OllamaVision:
    """Local, free, uncensored vision fallback through Ollama.

    `keep_alive: 0` is not an optimisation, it is the whole point: this machine
    is shared, so the 2.4 GB model has to leave RAM the moment the answer is out
    instead of squatting in Ollama's 5 minute default window while someone else
    is trying to work.
    """

    def __init__(
        self,
        model: str = LOCAL_VISION_MODEL,
        endpoint: str = OLLAMA_ENDPOINT,
        timeout: float = 600.0,
        max_side: int = LOCAL_MAX_SIDE,
        num_ctx: int = LOCAL_CONTEXT,
    ) -> None:
        self.model = model
        self.endpoint = endpoint
        self.timeout = timeout
        self.max_side = max_side
        self.num_ctx = num_ctx

    def _shrink(self, img: Image.Image) -> Image.Image:
        """Cap the long side before handing the image over.

        granite charges by visual tokens, so a 1920px image costs 3.6x the tokens
        of a 640px one and reads worse. Keep it small.
        """
        width, height = img.size
        longest = max(width, height)
        if longest <= self.max_side:
            return img
        scale = self.max_side / float(longest)
        return img.resize(
            (max(1, int(width * scale)), max(1, int(height * scale))),
            Image.LANCZOS,
        )

    def complete(self, prompt: str, images: list[Image.Image], max_tokens: int | None = None) -> str:
        body = {
            "model": self.model,
            "prompt": prompt,
            "images": [encode_png(self._shrink(img)) for img in images],
            "stream": False,
            "keep_alive": 0,
            "options": {
                "temperature": 0,
                "num_predict": max_tokens or 400,
                "num_ctx": self.num_ctx,
            },
        }
        request = urllib.request.Request(
            f"{self.endpoint}/api/generate",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read())
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:240]
            raise RuntimeError(f"local vision HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(
                f"local vision unreachable at {self.endpoint}; is `ollama serve` running?"
            ) from exc
        text = (payload.get("response") or "").strip()
        if not text:
            raise RuntimeError(f"local vision {self.model} returned an empty answer")
        return text

    def installed(self) -> bool:
        try:
            with urllib.request.urlopen(f"{self.endpoint}/api/tags", timeout=10) as response:
                payload = json.loads(response.read())
        except Exception:  # noqa: BLE001
            return False
        names = {m.get("name", "") for m in payload.get("models", [])}
        base = self.model.split(":")[0]
        return any(n == self.model or n.split(":")[0] == base for n in names)


class FallbackVision:
    """Cloud first, local second.

    The cloud model is more accurate and answers in seconds; the local one keeps
    ARIA able to see at all when there is no credit. Only the fallback is allowed
    to fail the run, and it records why the primary was dropped.
    """

    def __init__(self, primary: VisionClient, secondary: VisionClient) -> None:
        self.primary = primary
        self.secondary = secondary
        self.used = "primary"
        self.primary_error: str | None = None

    def complete(self, prompt: str, images: list[Image.Image]) -> str:
        try:
            return self.primary.complete(prompt, images)
        except Exception as exc:  # noqa: BLE001
            self.primary_error = f"{type(exc).__name__}: {exc}"
            self.used = "secondary"
            return self.secondary.complete(prompt, images)


def cmd_doctor() -> int:
    candidates = resolve_api_keys()
    print(f"OPENROUTER_API_KEY candidates: {len(candidates)}")
    for key, source in candidates:
        print(f"  source={source} len={len(key)}")
    print(f"model: {DEFAULT_MODEL}")
    print(f"endpoint: {DEFAULT_ENDPOINT}")
    cloud_ok = False
    for dep in ("PIL", "av"):
        try:
            __import__("av" if dep == "av" else "PIL")
            print(f"dependency {dep}: ok")
        except ImportError:
            print(f"dependency {dep}: MISSING")

    if not candidates:
        print("cloud live probe FAILED: no candidate key found")
    else:
        for key, source in candidates:
            client = OpenRouterVision(key=key)
            try:
                reply = client.complete("Reply with the single word: ready", [])
                print(f"cloud live probe OK using {source}: {reply.strip()[:40]}")
                cloud_ok = True
                break
            except Exception as exc:  # noqa: BLE001
                print(f"cloud live probe via {source} failed: {exc}")

    local = OllamaVision()
    print(f"\nlocal model: {local.model}")
    print(f"local endpoint: {local.endpoint}")
    print(f"local installed: {'yes' if local.installed() else 'NO - ollama pull ' + local.model}")
    print(f"local image cap: {local.max_side}px long side, num_ctx={local.num_ctx}, keep_alive=0")
    local_ok = False
    if local.installed():
        try:
            reply = local.complete("Reply with the single word: ready", [])
            print(f"local live probe OK: {reply.strip()[:40]}")
            local_ok = True
        except Exception as exc:  # noqa: BLE001
            print(f"local live probe failed: {exc}")

    if not cloud_ok and not local_ok:
        print("\nvision FAILED: neither the cloud nor the local provider answered")
        return 1
    if not cloud_ok:
        print("\nvision degraded: local only (no usable cloud credit)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="ARIA Eyes: vision for text-only agents")
    sub = parser.add_subparsers(dest="command", required=True)

    d = sub.add_parser("describe", help="describe an image or video")
    d.add_argument("path", type=pathlib.Path)
    d.add_argument("--grid", default="3x3", help="tile grid, e.g. 4x3")
    d.add_argument("--frames", type=int, default=0, help="sample N frames from a video")
    d.add_argument("--model", default=DEFAULT_MODEL)
    d.add_argument(
        "--provider",
        choices=("auto", "cloud", "local"),
        default="auto",
        help="auto = cloud with local Ollama fallback",
    )
    d.add_argument("--json", action="store_true", help="emit JSON instead of text")
    d.add_argument("--no-verify", action="store_true", help="skip the adversarial pass")

    sub.add_parser("doctor", help="check key, deps and provider reachability")

    args = parser.parse_args()

    if args.command == "doctor":
        return cmd_doctor()

    if not args.path.exists():
        print(f"missing: {args.path}", file=sys.stderr)
        return 1
    try:
        cols, _, rows = args.grid.partition("x")
        cols, rows = int(cols), int(rows or cols)
    except ValueError:
        print(f"bad --grid {args.grid!r}; expected like 4x3", file=sys.stderr)
        return 1

    local_client = OllamaVision()
    if args.provider == "cloud":
        client: VisionClient = OpenRouterVision(model=args.model)
    elif args.provider == "local":
        client = local_client
    else:
        client = FallbackVision(OpenRouterVision(model=args.model), local_client)
    try:
        result = describe(
            args.path,
            client,
            cols=cols,
            rows=rows,
            frames=args.frames,
            verify_report=not args.no_verify,
        )
    except RuntimeError as exc:
        if isinstance(client, FallbackVision):
            print(f"error: cloud and local vision both failed ({exc})", file=sys.stderr)
        else:
            print(f"error: {exc}", file=sys.stderr)
        return 1

    if isinstance(client, FallbackVision):
        if client.used == "secondary":
            print(
                f"[ARIA Eyes] cloud unavailable, answered with local {local_client.model}"
                f" ({client.primary_error})",
                file=sys.stderr,
            )
        else:
            print("[ARIA Eyes] answered with the cloud model", file=sys.stderr)

    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else render_text(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())