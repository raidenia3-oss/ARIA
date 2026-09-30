"""``python -m aria_control`` — same entry point as the ``aria`` script."""

from __future__ import annotations

from aria_control.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
