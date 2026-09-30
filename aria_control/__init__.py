"""ARIA Control Center — terminal client for the Axum control plane.

The dashboard and the CLI are a thin layer over ``/api/control/*`` on the Axum
backend. Anything the TUI can do, the web UI and the marketplace can do too,
because there is exactly one implementation of each operation.

Layout:

``aria_control.client``
    :class:`ControlClient` plus an injectable :class:`Transport`, so the CLI can
    be tested without a running server.
``aria_control.tui``
    Rich dashboard. Degrades to an explicit "backend unreachable" panel rather
    than crashing, because the most common way to run this is *before* the
    backend is up.
``aria_control.cli``
    The ``aria`` command.
"""

from __future__ import annotations

from aria_version import ARIA_VERSION

__version__ = ARIA_VERSION

__all__ = ["ARIA_VERSION", "__version__"]
