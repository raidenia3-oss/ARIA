import os
from typing import Any, Dict


def run(params: Dict[str, Any]) -> Dict[str, Any]:
    try:
        import pyautogui  # type: ignore

        screenshot = pyautogui.screenshot()
        base = os.path.dirname(__file__)
        path = os.path.join(base, "../../logs/screenshot.png")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        screenshot.save(path)
        return {
            "screenshot": "captured",
            "path": path,
            "width": screenshot.width,
            "height": screenshot.height,
        }
    except Exception as e:
        return {"screenshot": "error", "error": str(e)}
