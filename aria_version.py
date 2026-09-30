"""Single source of truth for the ARIA version.

The canonical version lives in ``pyproject.toml`` under ``[project].version``.
Every other file that reports or embeds a version is *generated* from it by
``tools/sync_version.py`` and policed by ``tools/verify_version.py``.

Why generated copies instead of a runtime read: ARIA ships as a frozen PyInstaller
binary that does not bundle ``pyproject.toml``, so ``__version__`` has to be a real
literal. The verify gate is what keeps the literal honest.

Import the constant from here rather than hardcoding a second literal.
"""

from __future__ import annotations

ARIA_VERSION = "6.0.0"
ARIA_CHANNEL = "stable"
ARIA_NAME = "ARIA OS"

__all__ = ["ARIA_VERSION", "ARIA_CHANNEL", "ARIA_NAME", "get_version", "version_tuple"]


def get_version() -> str:
    """Return the canonical ARIA version string."""
    return ARIA_VERSION


def version_tuple() -> tuple[int, int, int]:
    """Return the version as a comparable ``(major, minor, patch)`` tuple.

    Raises:
        ValueError: if ``ARIA_VERSION`` is not a three-part numeric version.
    """
    parts = ARIA_VERSION.split("-", 1)[0].split("+", 1)[0].split(".")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        raise ValueError(f"ARIA_VERSION is not a three-part version: {ARIA_VERSION!r}")
    return int(parts[0]), int(parts[1]), int(parts[2])
