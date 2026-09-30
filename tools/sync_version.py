#!/usr/bin/env python3
"""Propagate the canonical ARIA OS version from ``pyproject.toml`` to every copy.

The canonical version is authored in exactly one place. This script rewrites
the generated copies; ``tools/verify_version.py`` is the CI gate that keeps them
honest.

Usage::

    python tools/sync_version.py --dry-run    # show what would change, write nothing
    python tools/sync_version.py              # write the generated copies
    python tools/sync_version.py --check      # exit 1 if anything is out of date

Exit codes: ``0`` in sync, ``1`` drift with ``--check``, ``2`` a hard failure
(missing required file, unreadable file).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from version_manifest import (  # noqa: E402
    FROZEN_TARGETS,
    MANAGED_TARGETS,
    REPO_ROOT,
    canonical_version,
    rewrite,
)


def sync(dry_run: bool) -> int:
    version = canonical_version()
    print(f"Canonical version (pyproject.toml): {version}\n")

    changed: list[str] = []
    unchanged: list[str] = []
    failures: list[str] = []

    for target in MANAGED_TARGETS:
        full = REPO_ROOT / target.path
        if not full.exists():
            message = f"{target.path} is managed but missing"
            (failures if target.required else unchanged).append(message)
            print(f"ERROR  {target.path:<40} {message}")
            continue

        try:
            original = full.read_text(encoding="utf-8")
            updated, was_changed = rewrite(target, original, version)
        except Exception as exc:  # noqa: BLE001 - report, keep going
            failures.append(f"{target.path}: {exc}")
            print(f"ERROR  {target.path:<40} {exc}")
            continue

        if not was_changed:
            unchanged.append(target.path)
            print(f"OK     {target.path:<40} already {version}")
            continue

        changed.append(target.path)
        print(f"CHANGE {target.path:<40} -> {version}")
        if not dry_run:
            full.write_text(updated, encoding="utf-8", newline="")

    if dry_run and changed:
        print("\nDry run: no files written.")

    if failures:
        print(f"\nFAILED: {len(failures)} managed location(s) could not be synced.")
        for failure in failures:
            print(f"  - {failure}")
        return 2

    print(f"\nFrozen (not synced by design):")
    for path, reason in FROZEN_TARGETS:
        print(f"  - {path}: {reason}")

    if not changed:
        print(f"\nAlready in sync: {version}")
    else:
        verb = "would update" if dry_run else "updated"
        print(f"\n{verb.capitalize()} {len(changed)} file(s): {version}")
    return 0


def check() -> int:
    from version_manifest import extract

    version = canonical_version()
    drift: list[str] = []
    for target in MANAGED_TARGETS:
        full = REPO_ROOT / target.path
        if not full.exists():
            drift.append(f"{target.path}: managed file missing")
            continue
        found = extract(target, full.read_text(encoding="utf-8"))
        if not found:
            drift.append(f"{target.path}: no version literal found")
        elif found[0] != version:
            drift.append(f"{target.path}: {found[0]} != {version}")
    if drift:
        print(f"Out of sync with pyproject.toml ({version}):")
        for line in drift:
            print(f"  - {line}")
        return 1
    print(f"In sync: {version}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run", action="store_true", help="print the planned changes, write nothing"
    )
    mode.add_argument(
        "--check", action="store_true", help="exit 1 if any copy is out of date"
    )
    args = parser.parse_args(argv)

    if args.check:
        return check()
    return sync(dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
