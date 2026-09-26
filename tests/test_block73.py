"""Unit tests for Bloque 73 - Desktop Window Manager.

Tests dataclasses, layout engine (in-memory), and facade logic without
requiring win32/physical monitors.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path

import pytest

from backend.desktop.window_manager import (
    WIN32_AVAILABLE,
    DesktopWindowManager,
    LayoutSlot,
    MonitorInfo,
    OSWindowEnumerator,
    SpatialLayout,
    SpatialLayoutEngine,
    WindowController,
    WindowInfo,
    get_window_manager,
    reset_window_manager,
)


class TestMonitorInfo:
    def test_to_dict(self):
        m = MonitorInfo(
            index=0,
            handle=1,
            left=0,
            top=0,
            right=1920,
            bottom=1080,
            width=1920,
            height=1080,
            is_primary=True,
        )
        d = m.to_dict()
        assert d["index"] == 0
        assert d["width"] == 1920
        assert d["is_primary"] is True
        assert d["center"] == [960, 540]
        assert d["rect"] == [0, 0, 1920, 1080]

    def test_rect_and_center(self):
        m = MonitorInfo(
            index=1, handle=2, left=100, top=50, right=500, bottom=300, width=400, height=250
        )
        assert m.rect == (100, 50, 500, 300)
        assert m.center == (300, 175)


class TestWindowInfo:
    def test_to_dict(self):
        w = WindowInfo(
            handle=10,
            title="Test",
            visible=True,
            left=0,
            top=0,
            right=800,
            bottom=600,
            monitor_index=0,
            pid=42,
        )
        d = w.to_dict()
        assert d["handle"] == 10
        assert d["width"] == 800
        assert d["height"] == 600
        assert d["pid"] == 42

    def test_rect_and_center(self):
        w = WindowInfo(handle=1, title="x", visible=True, left=10, top=20, right=110, bottom=120)
        assert w.rect == (10, 20, 110, 120)
        assert w.center == (60, 70)


class TestLayoutSlot:
    def test_to_dict(self):
        s = LayoutSlot(
            title_substring="foo",
            monitor_index=1,
            x=10,
            y=20,
            width=300,
            height=200,
            maximize=True,
            focus=True,
        )
        d = s.to_dict()
        assert d["title_substring"] == "foo"
        assert d["maximize"] is True
        assert d["focus"] is True


class TestSpatialLayout:
    def test_to_dict(self):
        s = LayoutSlot(title_substring="a")
        layout = SpatialLayout(layout_id="abc", name="n", slots=[s], description="d")
        d = layout.to_dict()
        assert d["layout_id"] == "abc"
        assert d["name"] == "n"
        assert len(d["slots"]) == 1


class TestSpatialLayoutEngine:
    def test_create_and_get(self, tmp_path):
        engine = SpatialLayoutEngine(storage_path=tmp_path / "layouts.json")
        layout = engine.create_layout("Test", [{"title_substring": "foo"}], "desc")
        assert layout.layout_id
        fetched = engine.get_layout(layout.layout_id)
        assert fetched is not None
        assert fetched.name == "Test"

    def test_list_and_delete(self, tmp_path):
        engine = SpatialLayoutEngine(storage_path=tmp_path / "layouts.json")
        l1 = engine.create_layout("A", [{"title_substring": "x"}])
        l2 = engine.create_layout("B", [{"title_substring": "y"}])
        assert len(engine.list_layouts()) == 2
        assert engine.delete_layout(l1.layout_id) is True
        assert len(engine.list_layouts()) == 1
        assert engine.delete_layout(l1.layout_id) is False

    def test_persistence(self, tmp_path):
        path = tmp_path / "layouts.json"
        engine = SpatialLayoutEngine(storage_path=path)
        engine.create_layout("Persisted", [{"title_substring": "z"}], "d")
        engine2 = SpatialLayoutEngine(storage_path=path)
        layouts = engine2.list_layouts()
        assert len(layouts) == 1
        assert layouts[0].name == "Persisted"
        assert layouts[0].description == "d"

    def test_apply_layout_not_found(self, tmp_path):
        engine = SpatialLayoutEngine(storage_path=tmp_path / "x.json")
        result = engine.apply_layout("missing", WindowController(), OSWindowEnumerator())
        assert result["applied"] is False
        assert result["reason"] == "layout_not_found"


class TestDesktopWindowManager:
    def test_singleton(self):
        reset_window_manager()
        a = get_window_manager()
        b = get_window_manager()
        assert a is b
        reset_window_manager()

    def test_monitors_empty_when_no_win32(self):
        reset_window_manager()
        wm = get_window_manager()
        if not WIN32_AVAILABLE:
            assert wm.get_monitors() == []
            assert wm.get_windows() == []
        reset_window_manager()

    def test_move_returns_bool(self):
        reset_window_manager()
        wm = get_window_manager()
        result = wm.move_window(99999, 0, 0, 100, 100)
        assert isinstance(result, bool)
        reset_window_manager()


class TestWindowController:
    def test_methods_return_bool_without_win32(self):
        ctrl = WindowController()
        assert isinstance(ctrl.move(1, 0, 0, 100, 100), bool)
        assert isinstance(ctrl.focus(1), bool)
        assert isinstance(ctrl.maximize(1), bool)
        assert isinstance(ctrl.restore(1), bool)
        assert isinstance(ctrl.close(1), bool)
        assert isinstance(ctrl.set_visibility(1, True), bool)


class TestOSWindowEnumerator:
    def test_enumerate_returns_list(self):
        enum = OSWindowEnumerator()
        result = enum.enumerate_windows()
        assert isinstance(result, list)
        result2 = enum.enumerate_monitors()
        assert isinstance(result2, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
