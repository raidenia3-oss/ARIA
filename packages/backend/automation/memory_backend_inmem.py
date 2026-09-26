"""In-memory backend for tests and non-Windows platforms.

Re-exports the canonical InMemoryBackend from backend.automation.memory_injector
and adds test-only helpers (add_process / add_region / remove_process) that
mirror the inline backend API.
"""

from __future__ import annotations

from backend.automation.memory_injector import InMemoryBackend as _Base

# Re-export the canonical backend so callers can use either module path.
InMemoryBackend = _Base


def create_process(pid: int, name: str = "") -> int:
    """Create a simulated process in the in-memory backend."""
    backend = InMemoryBackend()
    backend.add_process(pid, name)
    return pid


__all__ = ["InMemoryBackend", "create_process"]