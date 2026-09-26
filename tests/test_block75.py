"""BLOQUE 75 - Unit tests for Tray, Hotkeys, and Overlay subsystems."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_overlay_imports():
    from backend.desktop.overlay import (
        OverlayBridge,
        OverlayMode,
        OverlayPosition,
        OverlayState,
        get_overlay_bridge,
        reset_overlay_bridge,
    )

    assert OverlayMode.HIDDEN.value == "hidden"
    assert OverlayPosition.TOP_RIGHT.value == "top_right"


def test_overlay_state_to_dict():
    from backend.desktop.overlay import OverlayMode, OverlayState

    s = OverlayState(mode=OverlayMode.COMPACT, opacity=0.5, visible=True)
    d = s.to_dict()
    assert d["mode"] == "compact"
    assert d["opacity"] == 0.5
    assert d["visible"] is True


def test_bridge_set_mode():
    from backend.desktop.overlay import OverlayBridge, OverlayMode

    bridge = OverlayBridge()
    state = bridge.set_mode(OverlayMode.COMPACT)
    assert state.mode == OverlayMode.COMPACT
    assert state.visible is True


def test_bridge_toggle_visibility():
    from backend.desktop.overlay import OverlayBridge, OverlayMode

    bridge = OverlayBridge()
    s1 = bridge.toggle_visibility()
    assert s1.mode == OverlayMode.COMPACT
    assert s1.visible is True
    s2 = bridge.toggle_visibility()
    assert s2.mode == OverlayMode.HIDDEN
    assert s2.visible is False


def test_bridge_set_position():
    from backend.desktop.overlay import OverlayBridge, OverlayPosition

    bridge = OverlayBridge()
    s = bridge.set_position(OverlayPosition.BOTTOM_LEFT, 100, 200)
    assert s.position == OverlayPosition.BOTTOM_LEFT
    assert s.custom_x == 100
    assert s.custom_y == 200


def test_bridge_set_opacity():
    from backend.desktop.overlay import OverlayBridge

    bridge = OverlayBridge()
    s = bridge.set_opacity(0.5)
    assert s.opacity == 0.5
    s2 = bridge.set_opacity(2.0)
    assert s2.opacity == 1.0
    s3 = bridge.set_opacity(-1.0)
    assert s3.opacity == 0.1


def test_bridge_notifications():
    from backend.desktop.overlay import OverlayBridge

    bridge = OverlayBridge()
    bridge.add_notification("Title", "Message", "info")
    bridge.add_notification("T2", "M2", "warning")
    status = bridge.status()
    assert status["state"]["notifications_count"] == 2
    cleared = bridge.clear_notifications()
    assert cleared == 2


def test_bridge_toggle_dnd():
    from backend.desktop.overlay import OverlayBridge, OverlayMode


def test_hotkey_binding():
    from backend.desktop.hotkeys import MOD_ALT, MOD_CONTROL, VK_A, HotkeyBinding

    calls = []
    b = HotkeyBinding(
        id=1,
        modifiers=MOD_CONTROL | MOD_ALT,
        vk_code=VK_A,
        label="test",
        callback=lambda: calls.append(True),
    )
    assert b.key_string == "Ctrl+Alt+A"
    b.callback()
    assert len(calls) == 1


def test_hotkey_key_string():
    from backend.desktop.hotkeys import MOD_SHIFT, VK_ESCAPE, VK_F1, VK_SPACE, HotkeyBinding

    b1 = HotkeyBinding(id=1, modifiers=MOD_SHIFT, vk_code=VK_F1, label="l", callback=lambda: None)
    assert b1.key_string == "Shift+F1"
    b2 = HotkeyBinding(id=2, modifiers=0, vk_code=VK_ESCAPE, label="l", callback=lambda: None)
    assert b2.key_string == "Esc"


def test_hotkey_listener_register():
    from backend.desktop.hotkeys import GlobalHotkeyListener

    calls = []
    listener = GlobalHotkeyListener()
    hk_id = listener.register_hotkey(0, 0x41, lambda: calls.append(True), "test")
    assert hk_id > 0
    assert len(listener.get_bindings()) == 1


def test_hotkey_listener_unregister():
    from backend.desktop.hotkeys import GlobalHotkeyListener

    listener = GlobalHotkeyListener()
    hk_id = listener.register_hotkey(0, 0x41, lambda: None)
    assert listener.unregister_hotkey(hk_id) is True
    assert listener.unregister_hotkey(hk_id) is False


def test_hotkey_listener_defaults():
    from backend.desktop.hotkeys import GlobalHotkeyListener

    calls = {"toggle_overlay": 0, "toggle_mic": 0, "screenshot": 0, "quit": 0}
    listener = GlobalHotkeyListener()
    ids = listener.register_defaults(
        {
            "toggle_overlay": lambda: calls.update(toggle_overlay=calls["toggle_overlay"] + 1),
            "toggle_mic": lambda: calls.update(toggle_mic=calls["toggle_mic"] + 1),
            "screenshot": lambda: calls.update(screenshot=calls["screenshot"] + 1),
            "quit": lambda: calls.update(quit=calls["quit"] + 1),
        }
    )
    assert len(ids) == 4
    assert listener.status()["bindings_count"] == 4


def test_hotkey_listener_singleton():
    from backend.desktop.hotkeys import get_hotkey_listener, reset_hotkey_listener

    reset_hotkey_listener()
    a = get_hotkey_listener()
    b = get_hotkey_listener()
    assert a is b
    reset_hotkey_listener()


def test_tray_menu_item():
    from backend.desktop.tray import TrayMenuItem

    item = TrayMenuItem(id=1, label="Test Item")
    assert item.id == 1
    assert item.label == "Test Item"
    assert item.enabled is True
    assert item.separator is False


def test_tray_manager_create():
    from backend.desktop.tray import SystemTrayManager

    tray = SystemTrayManager(app_name="Test AURA", tooltip="Test Tooltip")
    assert tray.app_name == "Test AURA"
    assert tray.is_running is False


def test_tray_add_remove_menu_item():
    from backend.desktop.tray import SystemTrayManager

    tray = SystemTrayManager()
    iid = tray.add_menu_item("Open", lambda: None)
    assert iid > 0
    assert len(tray._menu_items) == 1
    assert tray.remove_menu_item(iid) is True
    assert tray.remove_menu_item(iid) is False


def test_tray_singleton():
    from backend.desktop.tray import get_tray_manager, reset_tray_manager

    reset_tray_manager()
    a = get_tray_manager()
    b = get_tray_manager()
    assert a is b
    reset_tray_manager()


def test_tray_status():
    from backend.desktop.tray import SystemTrayManager

    tray = SystemTrayManager(app_name="Status Test")
    s = tray.status()
    assert s["running"] is False
    assert s["menu_items"] == 0
    assert s["app_name"] == "Status Test"


def test_bridge_toggle_dnd():
    from backend.desktop.overlay import OverlayBridge, OverlayMode

    bridge = OverlayBridge()
    s1 = bridge.toggle_dnd()
    assert s1.mode == OverlayMode.DND
    s2 = bridge.toggle_dnd()
    assert s2.mode == OverlayMode.COMPACT


def test_bridge_toggle_pin():
    from backend.desktop.overlay import OverlayBridge

    bridge = OverlayBridge()
    assert bridge.state.pinned is False
    s1 = bridge.toggle_pin()
    assert s1.pinned is True
    s2 = bridge.toggle_pin()
    assert s2.pinned is False


def test_bridge_singleton():
    from backend.desktop.overlay import get_overlay_bridge, reset_overlay_bridge

    reset_overlay_bridge()
    a = get_overlay_bridge()
    b = get_overlay_bridge()
    assert a is b
    reset_overlay_bridge()
    c = get_overlay_bridge()
    assert c is not a
