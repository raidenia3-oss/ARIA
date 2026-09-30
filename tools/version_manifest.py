"""Shared manifest of every location that carries the ARIA OS version.

Both ``tools/sync_version.py`` and ``tools/verify_version.py`` import
``MANAGED_TARGETS`` from here. Keeping one list is deliberate: if the writer and
the checker each carried their own copy, the two would drift and the CI gate
would happily green-light files nobody writes.

A target declares *how* its version literal is found and rewritten:

``regex``
    A single-line assignment. ``pattern`` locates it, ``template`` rebuilds the
    line with ``{version}`` substituted.
``cargo_package``
    A ``version = "..."`` line, but only inside the ``[package]`` table of a
    ``Cargo.toml``. A naive ``re.sub`` would also rewrite dependency versions
    and break the build.
``json``
    A top-level ``"version": "..."`` key of a JSON document.
``yaml_key``
    A ``key: "value"`` line, optionally restricted to a named parent block.
``flutter``
    A ``version: 1.2.3+4`` line in ``pubspec.yaml``. The build-number suffix is
    preserved: Flutter treats ``+4`` as the build counter, not part of the
    release version.
``plain``
    The whole file is the version followed by a newline (``VERSION``).

Frozen subproducts (the Tauri shell, the Godot build, ARIA v4) are deliberately
absent: they carry the version of a historical product line, not ARIA OS. See
``FROZEN_TARGETS`` for the audit trail.
"""

from __future__ import annotations

import json
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = REPO_ROOT / "pyproject.toml"

#: Version strings we manage are strict three-part semver with no suffix.
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")

__all__ = [
    "FROZEN_TARGETS",
    "MANAGED_TARGETS",
    "PYPROJECT",
    "REPO_ROOT",
    "Target",
    "canonical_version",
    "extract",
    "rewrite",
]


@dataclass(frozen=True)
class Target:
    """One file that embeds a copy of the canonical version."""

    path: str
    kind: str
    label: str
    pattern: str = ""
    template: str = ""
    block: str = ""
    required: bool = True
    note: str = ""

    def compiled(self) -> re.Pattern[str]:
        return re.compile(self.pattern, re.MULTILINE)


MANAGED_TARGETS: tuple[Target, ...] = (
    Target(
        path="aria_version.py",
        kind="regex",
        label="runtime constant",
        pattern=r'^(ARIA_VERSION\s*=\s*)"([^"]*)"',
        template=r'\g<1>"{version}"',
    ),
    Target(
        path="ARIA_APP/__init__.py",
        kind="regex",
        label="package __version__",
        pattern=r'^(__version__\s*=\s*)"([^"]*)"',
        template=r'\g<1>"{version}"',
    ),
    Target(
        path="VERSION",
        kind="plain",
        label="plain VERSION file",
    ),
    Target(
        path="v5/package.json",
        kind="json",
        label="Electron app version",
    ),
    Target(
        path="v6/axum-poc/Cargo.toml",
        kind="cargo_package",
        label="Axum core crate",
    ),
    Target(
        path="v6/axum-poc/src/version.rs",
        kind="regex",
        label="Rust ARIA_VERSION const",
        pattern=r'^(pub const ARIA_VERSION\s*:\s*&str\s*=\s*)"([^"]*)"',
        template=r'\g<1>"{version}"',
    ),
    Target(
        path="aria-backend-axum/Cargo.toml",
        kind="cargo_package",
        label="Axum backend crate",
    ),
    Target(
        path="v6/airi_mobile/pubspec.yaml",
        kind="flutter",
        label="Flutter client",
    ),
    Target(
        path="config.yaml",
        kind="yaml_key",
        label="runtime config app.version",
        pattern=r'^(  version\s*:\s*)"([^"]*)"',
        template=r'\g<1>"{version}"',
        block="app",
    ),
)


#: Historical product lines that intentionally keep their own version numbers.
FROZEN_TARGETS: tuple[tuple[str, str], ...] = (
    ("aura-v5-tauri/", "Tauri desktop shell, v5 line - frozen at 5.0.0"),
    ("v5.1/", "Godot 4.7 client, v5.1 line - frozen"),
    ("ARIA_v4/", "legacy v4 desktop app - frozen"),
    ("aria_autoconfig/__init__.py", "zero-touch setup package version, not the product version"),
    (".github/workflows/release.yml", "legacy v2.1 Alpine image build - superseded by the v6 pipeline"),
)


def canonical_version() -> str:
    """Read the one authored version out of ``pyproject.toml``."""
    with PYPROJECT.open("rb") as handle:
        data = tomllib.load(handle)
    try:
        version = data["project"]["version"]
    except KeyError as exc:  # pragma: no cover - configuration error
        raise SystemExit(
            "pyproject.toml has no [project].version - that value is the canonical "
            "ARIA OS version and must exist."
        ) from exc
    if not VERSION_RE.match(version):
        raise SystemExit(
            f"Canonical version {version!r} is not plain MAJOR.MINOR.PATCH semver. "
            "The updater and the rolling-release channel both require strict semver."
        )
    return version


def _split_toml_tables(content: str) -> list[tuple[str, str]]:
    """Split a TOML document into ``(table_name, body)`` pairs.

    Keys appearing before the first table header belong to the pseudo-table ``""``.
    """
    tables: list[tuple[str, list[str]]] = [("", [])]
    for line in content.splitlines(keepends=True):
        header = re.match(r"^\s*\[([^\[\]]+)\]\s*$", line)
        if header:
            tables.append((header.group(1).strip(), []))
            continue
        tables[-1][1].append(line)
    return [(name, "".join(lines)) for name, lines in tables]


def extract(target: Target, content: str) -> list[str]:
    """Return every version literal currently present in ``content``."""
    if target.kind == "plain":
        return [content.strip()] if content.strip() else []

    if target.kind == "json":
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            return []
        value = data.get("version")
        return [value] if isinstance(value, str) else []

    if target.kind == "cargo_package":
        for name, body in _split_toml_tables(content):
            if name != "package":
                continue
            match = re.search(r"^version\s*=\s*\"([^\"]+)\"", body, re.MULTILINE)
            if match:
                return [match.group(1)]
        return []

    if target.kind == "flutter":
        # The ``+build`` suffix is Flutter's build counter, not part of the
        # release version, so it is stripped before comparison and re-appended
        # on write. ``[ \t]*$`` rather than ``\s*$`` so the match cannot swallow
        # the following newline.
        match = re.search(r"^version:[ \t]*(\S+)[ \t]*$", content, re.MULTILINE)
        return [match.group(1).split("+", 1)[0]] if match else []

    if target.kind == "yaml_key" and target.block:
        match = _yaml_block(target.block, content)
        if not match:
            return []
        found = re.search(target.compiled(), match.group("body"))
        return [found.group(2)] if found else []

    return [m.group(2) for m in target.compiled().finditer(content)]


def rewrite(target: Target, content: str, version: str) -> tuple[str, bool]:
    """Return ``(new_content, was_rewritten)`` for a single target."""
    if target.kind == "plain":
        new = f"{version}\n"
        return new, new != content

    if target.kind == "json":
        data = json.loads(content)
        if data.get("version") == version:
            return content, False
        old = data.get("version")
        new = json.dumps(data, indent=2, ensure_ascii=False)
        if old is not None and old in new:
            new = new.replace(f'"version": "{old}"', f'"version": "{version}"', 1)
        else:  # pragma: no cover - defensive
            raise ValueError(f"cannot rewrite version field in {target.path}")
        if not content.endswith("\n"):
            new += "\n"
        return new, True

    if target.kind == "cargo_package":
        lines = content.splitlines(keepends=True)
        out: list[str] = []
        in_package = False
        changed = False
        for line in lines:
            header = re.match(r"^\s*\[([^\[\]]+)\]\s*$", line)
            if header:
                in_package = header.group(1).strip() == "package"
            if in_package:
                sub = re.sub(
                    r'^(version\s*=\s*)"[^"]*"', r'\g<1>"%s"' % version, line
                )
                changed = changed or sub != line
                out.append(sub)
                continue
            out.append(line)
        return "".join(out), changed

    if target.kind == "flutter":
        match = re.search(r"^(version:[ \t]*)(\S+)[ \t]*$", content, re.MULTILINE)
        if not match:
            return content, False
        current = match.group(2)
        build = current.split("+", 1)[1] if "+" in current else ""
        if current.split("+", 1)[0] == version:
            return content, False
        replacement = f"{match.group(1)}{version}" + (f"+{build}" if build else "")
        new = content[: match.start()] + replacement + content[match.end() :]
        return new, True

    if target.kind == "yaml_key" and target.block:
        match = _yaml_block(target.block, content)
        if not match:
            return content, False
        body = match.group("body")
        new_body, _ = target.compiled().subn(
            target.template.format(version=version), body
        )
        if new_body == body:
            return content, False
        new = content[: match.start("body")] + new_body + content[match.end("body") :]
        return new, True

    new = target.compiled().sub(target.template.format(version=version), content)
    return new, new != content


def _yaml_block(name: str, content: str) -> re.Match[str] | None:
    """Match a top-level YAML key and capture its indented body.

    The trailing newline is consumed explicitly. With ``\\s*$`` the regex engine
    happily matches the zero-width position *before* the newline, which leaves
    the body starting at ``\\n`` and therefore empty.
    """
    return re.compile(
        r"^%s:[ \t]*\r?\n(?P<body>(?:^[ \t]+.*(?:\r?\n|\Z))*)" % re.escape(name),
        re.MULTILINE,
    ).search(content)
