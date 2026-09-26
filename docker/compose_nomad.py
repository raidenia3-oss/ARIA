"""Generate docker-compose.nomad.yml from NomadManager template."""

from __future__ import annotations

import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path.append(str(root))
sys.path.append(str(root / "backend"))

from backend.nomad.nomad_manager import NomadManager  # noqa: E402


def main() -> int:
    manager = NomadManager()
    content = manager.compose_template()
    out = Path(__file__).resolve().parent / "docker-compose.nomad.yml"
    out.write_text(content, encoding="utf-8")
    print(str(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
