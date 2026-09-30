"""Allow ``python -m aria_video_library``, which is how the Axum route runs it.

``aria_video_library.cli:main`` is the entry point; this module exists so the
dispatched command line in ``videos.rs`` is a module invocation rather than a
script path, which would depend on the server's working directory.
"""

from __future__ import annotations

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
