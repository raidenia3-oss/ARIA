"""AURA Window Manager - Local Desktop Window & Multi-Monitor Spatial Layout Manager (Bloque 73).

Subsistema backend 100% local para enumerar, mover, redimensionar y enfocar
ventanas del SO, detectar monitores multiples y persistir layouts espaciales.

Usa win32gui/win32api/ctypes (USER32) sin dependencias cloud.
"""

from __future__ import annotations

import ctypes
import json
import logging
import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from ctypes import wintypes

try:
    import win32gui
    import win32api
    import win32con
    from win32gui import EnumWindows, GetWindowText, GetWindowRect, SetWindowPos
    import pywintypes
    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False

logger = logging.getLogger("AURA.WindowManager")

_USER32 = ctypes.windll.user32
_GetSystemMetrics = _USER32.GetSystemMetrics
_GetSystemMetrics.argtypes = [ctypes.c_int]
_GetSystemMetrics.restype = ctypes.c_int

SM_CXSCREEN = 0
SM_CYSCREEN = 1
SM_CXVIRTUALSCREEN = 76
SM_CYVIRTUALSCREEN = 77

SM_CXMAXIMIZED = 3
SM_CYMAXIMIZED = 4
SM_XVSCREEN = 7
SM_YVSCREEN = 8
SM_CXFULLSCREEN = 11
SM_CYFULLSCREEN = 12

MonitorEnumProc = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_long, ctypes.c_long, ctypes.POINTER(ctypes.c_int))


@dataclass
class MonitorInfo:
    """Physical monitor descriptor."""

    index: int
    handle: int
    left: int
    top: int
    right: int
    bottom: int
    width: int
    height: int
    is_primary: bool = False

    @property
    def rect(self) -> Tuple[int, int, int, int]:
        return (self.left, self.top, self.right, self.bottom)

    @property
    def center(self) -> Tuple[int, int]:
        return (self.left + self.width // 2, self.top + self.height // 2)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "handle": self.handle,
            "left": self.left,
            "top": self.top,
            "right": self.right,
            "bottom": self.bottom,
            "width": self.width,
            "height": self.height,
            "is_primary": self.is_primary,
            "center": list(self.center),
            "rect": list(self.rect),
        }


@dataclass
class WindowInfo:
    """Snapshot of a top-level OS window."""

    handle: int
    title: str
    visible: bool
    left: int = 0
    top: int = 0
    right: int = 0
    bottom: int = 0
    monitor_index: int = 0
    process_name: str = ""
    pid: int = 0

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top

    @property
    def rect(self) -> Tuple[int, int, int, int]:
        return (self.left, self.top, self.right, self.bottom)

    @property
    def center(self) -> Tuple[int, int]:
        return (self.left + self.width // 2, self.top + self.height // 2)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "handle": self.handle,
            "title": self.title,
            "visible": self.visible,
            "left": self.left,
            "top": self.top,
            "right": self.right,
            "bottom": self.bottom,
            "width": self.width,
            "height": self.height,
            "monitor_index": self.monitor_index,
            "process_name": self.process_name,
            "pid": self.pid,
            "rect": list(self.rect),
            "center": list(self.center),
        }


@dataclass
class LayoutSlot:
    """A single window placement within a layout."""

    title_substring: str
    monitor_index: int = 0
    x: int = 0
    y: int = 0
    width: int = 800
    height: int = 600
    maximize: bool = False
    focus: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title_substring": self.title_substring,
            "monitor_index": self.monitor_index,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "maximize": self.maximize,
            "focus": self.focus,
        }


@dataclass
class SpatialLayout:
    """A persisted multi-monitor spatial layout profile."""

    layout_id: str
    name: str
    slots: List[LayoutSlot] = field(default_factory=list)
    created_at: float = 0.0
    updated_at: float = 0.0
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "layout_id": self.layout_id,
            "name": self.name,
            "description": self.description,
            "slots": [s.to_dict() for s in self.slots],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class OSWindowEnumerator:
    """Enumerates top-level windows and physical monitors via USER32."""

    def __init__(self) -> None:
        self._win32_available = WIN32_AVAILABLE

    def enumerate_monitors(self) -> List[MonitorInfo]:
        monitors: List[MonitorInfo] = []
        if not self._win32_available:
            return monitors

        index = [0]

        def callback(hmonitor, lprect, lparam):
            rect = wintypes.RECT()
            ctypes.windll.user32.GetMonitorInfoW(hmonitor, ctypes.byref(rect))
            is_primary = bool(ctypes.windll.user32.GetMonitorInfoW(hmonitor, ctypes.byref(rect)) and rect.left == 0 and rect.top == 0)
            monitors.append(MonitorInfo(
                index=index[0],
                handle=hmonitor,
                left=rect.left,
                top=rect.top,
                right=rect.right,
                bottom=rect.bottom,
                width=rect.right - rect.left,
                height=rect.bottom - rect.top,
                is_primary=is_primary,
            ))
            index[0] += 1
            return 1

        proc = MonitorEnumProc(callback)
        ctypes.windll.user32.EnumDisplayMonitors(0, None, proc, 0)
        return monitors

    def enumerate_windows(self, visible_only: bool = True) -> List[WindowInfo]:
        windows: List[WindowInfo] = []
        if not self._win32_available:
            return windows

        monitors = self.enumerate_monitors()

        def on_enum(handle, param):
            if not win32gui.IsWindowVisible(handle) and visible_only:
                return 1
            title = win32gui.GetWindowText(handle)
            if not title:
                return 1
            try:
                rect = win32gui.GetWindowRect(handle)
            except pywintypes.error:
                return 1
            mon_idx = self._find_monitor(rect, monitors)
            pid = self._get_pid(handle)
            windows.append(WindowInfo(
                handle=handle,
                title=title,
                visible=win32gui.IsWindowVisible(handle),
                left=rect[0],
                top=rect[1],
                right=rect[2],
                bottom=rect[3],
                monitor_index=mon_idx,
                process_name=self._get_process_name(pid),
                pid=pid,
            ))
            return 1

        EnumWindows(on_enum, 0)
        return windows

    @staticmethod
    def _find_monitor(rect, monitors):
        cx = (rect[0] + rect[2]) // 2
        cy = (rect[1] + rect[3]) // 2
        for m in monitors:
            if m.left <= cx <= m.right and m.top <= cy <= m.bottom:
                return m.index
        return 0

    @staticmethod
    def _get_pid(handle):
        try:
            return win32api.GetWindowThreadProcessId(handle)
        except Exception:
            return 0

    @staticmethod
    def _get_process_name(pid):
        if not pid:
            return ""
        try:
            import subprocess
            out = subprocess.check_output(["wmic", "process", "get", "name,processid", "/format:csv"], timeout=2)
            for line in out.decode("utf-8", errors="ignore").splitlines():
                if str(pid) in line:
                    parts = line.split(",")
                    if len(parts) >= 2:
                        return parts[1].strip()
        except Exception:
            pass
        return ""


class WindowController:
    """Moves, resizes, focuses and maximizes OS windows via USER32."""

    def __init__(self) -> None:
        self._win32_available = WIN32_AVAILABLE

    def move(self, handle: int, x: int, y: int, width: int, height: int) -> bool:
        if not self._win32_available:
            return False
        try:
            flags = win32con.SWP_NOZORDER | win32con.SWP_NOACTIVATE
            SetWindowPos(handle, win32con.HWND_TOP, x, y, width, height, flags)
            return True
        except Exception as exc:
            logger.warning("move failed handle=%s: %s", handle, exc)
            return False

    def focus(self, handle: int) -> bool:
        if not self._win32_available:
            return False
        try:
            win32gui.SetForegroundWindow(handle)
            return True
        except Exception as exc:
            logger.warning("focus failed handle=%s: %s", handle, exc)
            return False

    def maximize(self, handle: int) -> bool:
        if not self._win32_available:
            return False
        try:
            win32gui.ShowWindow(handle, win32con.SW_MAXIMIZE)
            return True
        except Exception as exc:
            logger.warning("maximize failed handle=%s: %s", handle, exc)
            return False

    def restore(self, handle: int) -> bool:
        if not self._win32_available:
            return False
        try:
            win32gui.ShowWindow(handle, win32con.SW_RESTORE)
            return True
        except Exception as exc:
            logger.warning("restore failed handle=%s: %s", handle, exc)
            return False

    def close(self, handle: int) -> bool:
        if not self._win32_available:
            return False
        try:
            win32gui.PostMessage(handle, win32con.WM_CLOSE, 0, 0)
            return True
        except Exception as exc:
            logger.warning("close failed handle=%s: %s", handle, exc)
            return False

    def set_visibility(self, handle: int, visible: bool) -> bool:
        if not self._win32_available:
            return False
        try:
            win32gui.ShowWindow(handle, win32con.SW_SHOW if visible else win32con.SW_HIDE)
            return True
        except Exception as exc:
            logger.warning("set_visibility failed handle=%s: %s", handle, exc)
            return False



class SpatialLayoutEngine:
    """Applies, saves and restores multi-monitor spatial layouts."""

    def __init__(self, storage_path: Optional[Path] = None) -> None:
        self._storage_path = storage_path or Path(__file__).resolve().parent.parent / "data" / "window_layouts.json"
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._layouts: Dict[str, SpatialLayout] = {}
        self._lock = threading.RLock()
        self._load()

    def _load(self) -> None:
        if not self._storage_path.exists():
            return
        try:
            with open(self._storage_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            for item in raw.get("layouts", []):
                slots = [LayoutSlot(**s) for s in item.get("slots", [])]
                layout = SpatialLayout(
                    layout_id=item.get("layout_id", ""),
                    name=item.get("name", ""),
                    description=item.get("description", ""),
                    slots=slots,
                    created_at=item.get("created_at", 0.0),
                    updated_at=item.get("updated_at", 0.0),
                )
                self._layouts[layout.layout_id] = layout
        except Exception as exc:
            logger.warning("layout load failed: %s", exc)

    def _save(self) -> None:
        try:
            data = {"layouts": [l.to_dict() for l in self._layouts.values()]}
            with open(self._storage_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as exc:
            logger.warning("layout save failed: %s", exc)

    def create_layout(self, name: str, slots: List[Dict[str, Any]], description: str = "") -> SpatialLayout:
        with self._lock:
            layout = SpatialLayout(
                layout_id=str(uuid.uuid4()),
                name=name,
                description=description,
                slots=[LayoutSlot(**s) for s in slots],
                created_at=time.time(),
                updated_at=time.time(),
            )
            self._layouts[layout.layout_id] = layout
            self._save()
            return layout

    def get_layout(self, layout_id: str) -> Optional[SpatialLayout]:
        with self._lock:
            return self._layouts.get(layout_id)

    def list_layouts(self) -> List[SpatialLayout]:
        with self._lock:
            return list(self._layouts.values())

    def delete_layout(self, layout_id: str) -> bool:
        with self._lock:
            if layout_id in self._layouts:
                del self._layouts[layout_id]
                self._save()
                return True
            return False

    def apply_layout(self, layout_id: str, controller: WindowController, enumerator: OSWindowEnumerator) -> Dict[str, Any]:
        layout = self.get_layout(layout_id)
        if not layout:
            return {"applied": False, "reason": "layout_not_found"}
        windows = enumerator.enumerate_windows()
        monitors = enumerator.enumerate_monitors()
        applied = 0
        failed = 0
        for slot in layout.slots:
            target = next((w for w in windows if slot.title_substring.lower() in w.title.lower()), None)
            if not target:
                failed += 1
                continue
            mon = next((m for m in monitors if m.index == slot.monitor_index), None)
            x = slot.x + (mon.left if mon else 0)
            y = slot.y + (mon.top if mon else 0)
            if slot.maximize:
                controller.maximize(target.handle)
            else:
                controller.move(target.handle, x, y, slot.width, slot.height)
            if slot.focus:
                controller.focus(target.handle)
            applied += 1
        return {
            "applied": applied > 0,
            "layout_id": layout_id,
            "windows_matched": applied,
            "windows_missed": failed,
            "total_windows": len(windows),
        }

    def capture_layout(self, name: str, description: str = "") -> SpatialLayout:
        enumerator = OSWindowEnumerator()
        windows = enumerator.enumerate_windows()
        monitors = enumerator.enumerate_monitors()
        slots = []
        for w in windows:
            mon = next((m for m in monitors if m.index == w.monitor_index), None)
            base_x = w.left - (mon.left if mon else 0)
            base_y = w.top - (mon.top if mon else 0)
            slots.append(LayoutSlot(
                title_substring=w.title,
                monitor_index=w.monitor_index,
                x=base_x,
                y=base_y,
                width=w.width,
                height=w.height,
            ))
        return self.create_layout(name, [s.to_dict() for s in slots], description)


class DesktopWindowManager:
    """High-level facade combining enumerator, controller and layout engine."""

    def __init__(self) -> None:
        self._enumerator = OSWindowEnumerator()
        self._controller = WindowController()
        self._layout_engine = SpatialLayoutEngine()

    @property
    def enumerator(self) -> OSWindowEnumerator:
        return self._enumerator

    @property
    def controller(self) -> WindowController:
        return self._controller

    @property
    def layout_engine(self) -> SpatialLayoutEngine:
        return self._layout_engine

    def get_monitors(self) -> List[MonitorInfo]:
        return self._enumerator.enumerate_monitors()

    def get_windows(self, visible_only: bool = True) -> List[WindowInfo]:
        return self._enumerator.enumerate_windows(visible_only)

    def move_window(self, handle: int, x: int, y: int, width: int, height: int) -> bool:
        return self._controller.move(handle, x, y, width, height)

    def focus_window(self, handle: int) -> bool:
        return self._controller.focus(handle)

    def maximize_window(self, handle: int) -> bool:
        return self._controller.maximize(handle)

    def restore_window(self, handle: int) -> bool:
        return self._controller.restore(handle)

    def close_window(self, handle: int) -> bool:
        return self._controller.close(handle)

    def apply_layout(self, layout_id: str) -> Dict[str, Any]:
        return self._layout_engine.apply_layout(layout_id, self._controller, self._enumerator)

    def create_layout(self, name: str, slots: List[Dict[str, Any]], description: str = "") -> SpatialLayout:
        return self._layout_engine.create_layout(name, slots, description)

    def capture_layout(self, name: str, description: str = "") -> SpatialLayout:
        return self._layout_engine.capture_layout(name, description)

    def list_layouts(self) -> List[SpatialLayout]:
        return self._layout_engine.list_layouts()

    def delete_layout(self, layout_id: str) -> bool:
        return self._layout_engine.delete_layout(layout_id)


_manager: Optional[DesktopWindowManager] = None
_manager_lock = threading.Lock()


def get_window_manager() -> DesktopWindowManager:
    """Return the singleton DesktopWindowManager instance."""
    global _manager
    if _manager is None:
        with _manager_lock:
            if _manager is None:
                _manager = DesktopWindowManager()
    return _manager


def reset_window_manager() -> None:
    """Reset the singleton (mainly for tests)."""
    global _manager
    with _manager_lock:
        _manager = None


__all__ = [
    "MonitorInfo",
    "WindowInfo",
    "LayoutSlot",
    "SpatialLayout",
    "OSWindowEnumerator",
    "WindowController",
    "SpatialLayoutEngine",
    "DesktopWindowManager",
    "get_window_manager",
    "reset_window_manager",
    "WIN32_AVAILABLE",
]
