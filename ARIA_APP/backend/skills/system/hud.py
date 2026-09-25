import os
import sys
import time
from typing import Any, Dict, List


def run(params: Dict[str, Any]) -> Dict[str, Any]:
    action = params.get("action", "")
    if action == "toggle_hud":
        return _toggle_hud(params)
    elif action == "show_hud":
        return _show_hud(params)
    elif action == "minimize_hud":
        return _minimize_hud(params)
    elif action == "get_hud_status":
        return {"status": "running", "hotkey": "Ctrl+Shift+A"}
    return {"error": f"Unknown action: {action}"}


def _toggle_hud(params: Dict[str, Any]) -> Dict[str, Any]:
    try:
        import pyautogui
        pyautogui.hotkey("alt", "space")
        time.sleep(0.2)
        pyautogui.press("n")
        return {"status": "ok", "action": "toggle_hud"}
    except Exception as e:
        return {"error": str(e)}


def _show_hud(params: Dict[str, Any]) -> Dict[str, Any]:
    try:
        import pyautogui
        pyautogui.hotkey("alt", "tab")
        return {"status": "ok", "action": "show_hud"}
    except Exception as e:
        return {"error": str(e)}


def _minimize_hud(params: Dict[str, Any]) -> Dict[str, Any]:
    try:
        import pyautogui
        pyautogui.hotkey("win", "down")
        return {"status": "ok", "action": "minimize_hud"}
    except Exception as e:
        return {"error": str(e)}
