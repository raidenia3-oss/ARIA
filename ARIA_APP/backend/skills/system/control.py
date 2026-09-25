import os
import subprocess
import sys
import time
from typing import Any, Dict, List


def run(params: Dict[str, Any]) -> Dict[str, Any]:
    action = params.get("action", "")
    if action == "mouse_move":
        return _mouse_move(params)
    elif action == "mouse_click":
        return _mouse_click(params)
    elif action == "mouse_drag":
        return _mouse_drag(params)
    elif action == "keyboard_type":
        return _keyboard_type(params)
    elif action == "keyboard_press":
        return _keyboard_press(params)
    elif action == "screenshot":
        return _screenshot(params)
    elif action == "get_screen_size":
        return _screen_size(params)
    return {"error": f"Unknown action: {action}"}


def _mouse_move(params: Dict[str, Any]) -> Dict[str, Any]:
    try:
        import pyautogui
        x = params.get("x", 0)
        y = params.get("y", 0)
        duration = params.get("duration", 0.3)
        pyautogui.moveTo(x, y, duration=duration)
        return {"status": "ok", "action": "mouse_move", "x": x, "y": y}
    except Exception as e:
        return {"error": str(e)}


def _mouse_click(params: Dict[str, Any]) -> Dict[str, Any]:
    try:
        import pyautogui
        x = params.get("x", 0)
        y = params.get("y", 0)
        button = params.get("button", "left")
        clicks = params.get("clicks", 1)
        pyautogui.click(x=x, y=y, button=button, clicks=clicks)
        return {"status": "ok", "action": "mouse_click", "x": x, "y": y, "button": button}
    except Exception as e:
        return {"error": str(e)}


def _mouse_drag(params: Dict[str, Any]) -> Dict[str, Any]:
    try:
        import pyautogui
        x = params.get("x", 0)
        y = params.get("y", 0)
        duration = params.get("duration", 0.5)
        pyautogui.moveTo(x, y, duration=duration)
        pyautogui.drag(x, y, duration=duration)
        return {"status": "ok", "action": "mouse_drag", "x": x, "y": y}
    except Exception as e:
        return {"error": str(e)}


def _keyboard_type(params: Dict[str, Any]) -> Dict[str, Any]:
    try:
        import pyautogui
        text = params.get("text", "")
        interval = params.get("interval", 0.0)
        pyautogui.typewrite(text, interval=interval)
        return {"status": "ok", "action": "keyboard_type", "text": text[:50]}
    except Exception as e:
        return {"error": str(e)}


def _keyboard_press(params: Dict[str, Any]) -> Dict[str, Any]:
    try:
        import pyautogui
        key = params.get("key", "")
        presses = params.get("presses", 1)
        pyautogui.press(key, presses=presses)
        return {"status": "ok", "action": "keyboard_press", "key": key}
    except Exception as e:
        return {"error": str(e)}


def _screenshot(params: Dict[str, Any]) -> Dict[str, Any]:
    try:
        import pyautogui
        path = params.get("path", f"screenshot_{int(time.time())}.png")
        region = params.get("region")
        if region:
            screenshot = pyautogui.screenshot(region=tuple(region))
        else:
            screenshot = pyautogui.screenshot()
        screenshot.save(path)
        return {"status": "ok", "path": path, "width": screenshot.width, "height": screenshot.height}
    except Exception as e:
        return {"error": str(e)}


def _screen_size(params: Dict[str, Any]) -> Dict[str, Any]:
    try:
        import pyautogui
        return {"status": "ok", "width": pyautogui.size().width, "height": pyautogui.size().height}
    except Exception as e:
        return {"error": str(e)}
