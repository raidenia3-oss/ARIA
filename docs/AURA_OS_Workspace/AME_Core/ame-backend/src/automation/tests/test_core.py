"""Tests for automation core modules."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────


@pytest.fixture
def sample_targets() -> list[dict]:
    return [
        {
            "platform": "test_platform",
            "base_url": "https://example.com",
            "login_url": "https://example.com/login",
            "selectors": {
                "email": "#email",
                "password": "#password",
                "submit": "#submit",
            },
        }
    ]


@pytest.fixture
def targets_file(tmp_path: Path, sample_targets: list[dict]) -> Path:
    """Create a temporary targets.json config."""
    filepath = tmp_path / "targets.json"
    json.dump(sample_targets, filepath.open("w", encoding="utf-8"))
    return filepath


# ──────────────────────────────────────────────
# Tests – PlatformAdapters
# ──────────────────────────────────────────────


class TestPlatformAdapters:
    def test_import(self) -> None:
        """Verify the module can be imported."""
        from ame_backend.src.automation.platform_adapters import PlatformAdapters  # noqa: F811

        assert PlatformAdapters is not None

    def test_load_targets_no_file(self) -> None:
        """Load targets when file does not exist – must return []."""
        from ame_backend.src.automation.platform_adapters import PlatformAdapters

        adapter = PlatformAdapters()
        adapter.targets_path = Path("/does/not/exist/targets.json")
        adapter.targets = adapter._load_targets()
        assert adapter.targets == []

    def test_load_targets_corrupted(self, tmp_path: Path) -> None:
        """Load targets when file contains invalid JSON – must return []."""
        bad_file = tmp_path / "targets.json"
        bad_file.write_text("not valid json", encoding="utf-8")
        from ame_backend.src.automation.platform_adapters import PlatformAdapters

        adapter = PlatformAdapters()
        adapter.targets_path = bad_file
        adapter.targets = adapter._load_targets()
        assert adapter.targets == []

    def test_load_targets_ok(self, targets_file: Path) -> None:
        """Load valid targets file."""
        from ame_backend.src.automation.platform_adapters import PlatformAdapters

        adapter = PlatformAdapters()
        adapter.targets_path = targets_file
        adapter.targets = adapter._load_targets()
        assert len(adapter.targets) == 1
        assert adapter.targets[0]["platform"] == "test_platform"


# ──────────────────────────────────────────────
# Tests – HuntingLoop
# ──────────────────────────────────────────────


class TestHuntingLoop:
    def test_import(self) -> None:
        """Verify the module can be imported."""
        from ame_backend.src.automation.hunting_loop import HuntingLoop  # noqa: F811

        assert HuntingLoop is not None

    @pytest.mark.asyncio
    async def test_run_no_targets(self) -> None:
        """When no targets are configured, must gracefully handle the loop."""
        from ame_backend.src.automation.hunting_loop import HuntingLoop

        events: list[str] = []

        async def event_collector(msg: str) -> None:
            events.append(msg)

        loop = HuntingLoop(on_event=event_collector)

        # Replace targets.json with empty path so load_targets returns []
        loop.adapters.targets_path = Path("/nonexistent/targets.json")

        await loop.run()
        assert any("No targets" in e for e in events), f"Unexpected events: {events}"


# ──────────────────────────────────────────────
# Tests – SurveySolver
# ──────────────────────────────────────────────


class TestSurveySolver:
    def test_import(self) -> None:
        """Verify the survey solver module can be imported."""
        from ame_backend.src.automation.survey_solver import SurveySolver  # noqa: F811

        assert SurveySolver is not None


# ──────────────────────────────────────────────
# Tests – StealthEngine
# ──────────────────────────────────────────────


class TestStealthEngine:
    def test_import(self) -> None:
        """Verify the stealth engine module can be imported."""
        from ame_backend.src.automation.stealth_engine import Infiltrator  # noqa: F811

        assert Infiltrator is not None
