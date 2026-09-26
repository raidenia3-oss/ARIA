"""AURA System Tray Manager (Bloque 75)."""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import logging
import os
import threading
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger("AURA.Tray")

WM_USER = 0x0400
WM_TRAYICON = WM_USER + 1
WM_COMMAND = 0x0111
WM_DESTROY = 0x0002
WM_CLOSE = 0x0010
CW_USEDEFAULT = 0x80000000
IDI_APPLICATION = 32512
NIM_ADD = 0
NIM_MODIFY = 1
NIM_DELETE = 2
NIF_MESSAGE = 1
NIF_ICON = 2
NIF_TIP = 4
NIF_INFO = 16
NIIF_INFO = 1
NIIF_WARNING = 2
NIIF_ERROR = 3


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.wintypes.DWORD), ("hWnd", ctypes.wintypes.HWND),
        ("uID", ctypes.wintypes.UINT), ("uFlags", ctypes.wintypes.UINT),
        ("uCallbackMessage", ctypes.wintypes.UINT), ("hIcon", ctypes.wintypes.HICON),
        ("szTip", ctypes.wintypes.WCHAR * 128), ("dwState", ctypes.wintypes.DWORD),
        ("dwStateMask", ctypes.wintypes.DWORD), ("szInfo", ctypes.wintypes.WCHAR * 256),
        ("uVersion", ctypes.wintypes.UINT), ("szInfoTitle", ctypes.wintypes.WCHAR * 64),
        ("dwInfoFlags", ctypes.wintypes.DWORD), ("guidItem", ctypes.c_char * 16),
        ("hBalloonIcon", ctypes.wintypes.HICON),
    ]


@dataclass
class TrayMenuItem:
    id: int
    label: str
    callback: Optional[Callable] = None
    enabled: bool = True
    separator: bool = False


class SystemTrayManager:
    def __init__(self, app_name="AURA OS", tooltip="AURA", icon_path=None):
        self.app_name = app_name
        self.tooltip = tooltip
        self.icon_path = icon_path
        self._hwnd = None
        self._menu_items = {}
        self._running = False
        self._thread = None
        self._lock = threading.Lock()
        self._menu_id_counter = 1000

    def _create_window(self):
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        hinstance = kernel32.GetModuleHandleW(None)
        WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p)
        class WNDCLASSEXW(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_uint), ("style", ctypes.c_uint), ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int), ("hInstance", ctypes.c_void_p), ("hIcon", ctypes.c_void_p), ("hCursor", ctypes.c_void_p), ("hbrBackground", ctypes.c_void_p), ("lpszMenuName", ctypes.c_wchar_p), ("lpszClassName", ctypes.c_wchar_p), ("hIconSm", ctypes.c_void_p)]
        self._wnd_proc_fn = WNDPROC(self._wnd_proc)
        wc = WNDCLASSEXW()
        wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
        wc.lpfnWndProc = self._wnd_proc_fn
        wc.hInstance = hinstance
        wc.lpszClassName = f"AURATray_{uuid.uuid4().hex[:8]}"
        atom = user32.RegisterClassExW(ctypes.byref(wc))
        if not atom:
            raise RuntimeError("Failed to register tray window class")
        return user32.CreateWindowExW(0, wc.lpszClassName, self.app_name, 0, CW_USEDEFAULT, CW_USEDEFAULT, 0, 0, None, None, hinstance, None)

    def _wnd_proc(self, hwnd, msg, wparam, lparam):
        if msg == WM_TRAYICON and lparam == 0x0205:
            self._show_context_menu()
        elif msg == WM_COMMAND:
            cid = wparam & 0xFFFF
            if cid in self._menu_items:
                item = self._menu_items[cid]
                if item.callback and item.enabled:
                    try:
                        item.callback()
                    except Exception as e:
                        logger.error("Tray cb error: %s", e)
        elif msg == WM_DESTROY:
            self._remove_icon()
            ctypes.windll.user32.PostQuitMessage(0)
        return ctypes.windll.user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _load_icon(self):
        u32 = ctypes.windll.user32
        if self.icon_path and os.path.exists(self.icon_path):
            h = u32.LoadImageW(None, self.icon_path, 1, 0, 0, 0x90)
            return h if h else u32.LoadIconW(None, IDI_APPLICATION)
        return u32.LoadIconW(None, IDI_APPLICATION)

    def _add_icon(self):
        if self._hwnd is None:
            return False
        nid = NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        nid.hWnd = self._hwnd
        nid.uID = 1
        nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        nid.uCallbackMessage = WM_TRAYICON
        nid.hIcon = self._load_icon()
        nid.szTip = self.tooltip[:127]
        return bool(ctypes.windll.shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid)))

    def _remove_icon(self):
        if self._hwnd is None:
            return False
        nid = NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        nid.hWnd = self._hwnd
        nid.uID = 1
        return bool(ctypes.windll.shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(nid)))

    def add_menu_item(self, label, callback=None, **kwargs):
        with self._lock:
            iid = self._menu_id_counter
            self._menu_id_counter += 1
            self._menu_items[iid] = TrayMenuItem(id=iid, label=label, callback=callback, **kwargs)
            return iid

    def remove_menu_item(self, item_id):
        with self._lock:
            return self._menu_items.pop(item_id, None) is not None

    @property
    def is_running(self) -> bool:
        return self._running

    def get_menu_items(self) -> list:
        with self._lock:
            return [{"id": i.id, "label": i.label, "enabled": i.enabled, "separator": i.separator}
                    for i in self._menu_items.values()]

    def _show_context_menu(self) -> None:
        user32 = ctypes.windll.user32
        menu = user32.CreatePopupMenu()
        with self._lock:
            items = list(self._menu_items.values())
        for it in items:
            if it.separator:
                user32.AppendMenuW(menu, 0x0800, 0, "")
            else:
                user32.AppendMenuW(menu, 0x0000, it.id, it.label)
        if not items:
            user32.AppendMenuW(menu, 0x0000, 0, "AURA")
        user32.TrackPopupMenu(menu, 0x0100, self._menu_pos_x, self._menu_pos_y, 0, self._hwnd, None)
        user32.DestroyMenu(menu)

    def show_notification(self, title: str, message: str) -> bool:
        if self._hwnd is None:
            return False
        nid = NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        nid.hWnd = self._hwnd
        nid.uID = 1
        nid.uFlags = NIF_INFO
        nid.szInfo = message[:255]
        nid.szInfoTitle = title[:63]
        nid.dwInfoFlags = NIIF_INFO
        return bool(ctypes.windll.shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(nid)))

    def status(self) -> dict:
        with self._lock:
            return {
                "running": self._running,
                "app_name": self.app_name,
                "menu_items": len(self._menu_items),
                "tooltip": self.tooltip,
            }


_tray = None
_tray_lock = threading.Lock()


def get_tray_manager():
    global _tray
    if _tray is None:
        with _tray_lock:
            if _tray is None:
                _tray = SystemTrayManager()
    return _tray


def reset_tray_manager():
    global _tray
    with _tray_lock:
        if _tray and _tray._running:
            _tray.stop()
        _tray = None


__all__ = [
    "TrayMenuItem", "SystemTrayManager", "get_tray_manager", "reset_tray_manager",
    "NOTIFYICONDATAW",
]

