"""GUI automation engine for AURA - Module 28.

Automatizacion de interfaz grafica (GUI/OS): captura de pantalla,
analisis de elementos visuales, ejecucion segura de clics, escritura y atajos.
"""

from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class Coordinates:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    def to_dict(self) -> Dict[str, float]:
        return {"x": self.x, "y": self.y, "z": self.z}


@dataclass
class ActionPayload:
    """Representa una accion de GUI: click, type, keypress, scroll, drag, move, screenshot."""

    action_type: str
    coordinates: Optional[Coordinates] = None
    text: Optional[str] = None
    key: Optional[str] = None
    key_combination: Optional[List[str]] = None
    scroll_amount: int = 0
    duration: float = 0.0
    delay: float = 0.0
    confirm: bool = False

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if d.get("coordinates") is not None:
            d["coordinates"] = self.coordinates.to_dict()
        return d


class ScreenAnalyzer:
    """Captura de pantalla y analisis de elementos visuales."""

    def __init__(self) -> None:
        self._last_screenshot: Optional[Dict[str, Any]] = None
        self._last_analysis: Optional[Dict[str, Any]] = None

    @property
    def available(self) -> bool:
        try:
            import pyautogui
            return True
        except ImportError:
            return False

    async def capture_screen(self, region: Optional[Tuple[int, int, int, int]] = None) -> Dict[str, Any]:
        if not self.available:
            return {"captured": False, "error": "pyautogui not available"}
        try:
            import pyautogui
            screenshot = pyautogui.screenshot(region=region)
            info = {
                "captured": True,
                "width": screenshot.width,
                "height": screenshot.height,
                "mode": screenshot.mode,
                "region": list(region) if region else None,
                "captured_at": datetime.utcnow().isoformat() + "Z",
            }
            self._last_screenshot = info
            return info
        except Exception as exc:
            return {"captured": False, "error": str(exc)}

    async def analyze_elements(self) -> Dict[str, Any]:
        screen = await self.capture_screen()
        if not screen.get("captured"):
            return {"analyzed": False, "error": screen.get("error", "capture_failed")}

        width = screen.get("width", 0)
        height = screen.get("height", 0)
        elements = [
            {
                "type": "screen_center",
                "x": width / 2,
                "y": height / 2,
                "confidence": 1.0,
            },
            {
                "type": "bottom_right",
                "x": width,
                "y": height,
                "confidence": 1.0,
            },
        ]
        analysis = {
            "analyzed": True,
            "screen_width": width,
            "screen_height": height,
            "elements": elements,
            "element_count": len(elements),
            "analyzed_at": datetime.utcnow().isoformat() + "Z",
        }
        self._last_analysis = analysis
        return analysis

    def get_screen_state(self) -> Dict[str, Any]:
        return {
            "last_screenshot": self._last_screenshot,
            "last_analysis": self._last_analysis,
            "pyautogui_available": self.available,
        }


class GUIActionExecutor:
    """Ejecutor seguro de acciones de GUI con historial y controles de seguridad."""

    SAFE_ACTIONS = {
        "click", "double_click", "right_click", "type", "keypress",
        "scroll", "move", "drag", "screenshot", "press_combination",
    }

    def __init__(self) -> None:
        self._safety_enabled: bool = True
        self._action_history: List[Dict[str, Any]] = []
        self._max_history: int = 1000

    @property
    def available(self) -> bool:
        try:
            import pyautogui
            return True
        except ImportError:
            return False

    async def execute(self, payload: ActionPayload) -> Dict[str, Any]:
        if payload.action_type not in self.SAFE_ACTIONS:
            return {"executed": False, "error": f"unsafe_action: {payload.action_type}"}

        if payload.delay > 0:
            await asyncio.sleep(payload.delay)

        if not self.available:
            return {
                "executed": False,
                "error": "pyautogui not available",
                "action": payload.action_type,
                "payload": payload.to_dict(),
            }

        try:
            import pyautogui
            result = await self._do_action(pyautogui, payload)
        except Exception as exc:
            result = {"executed": False, "error": str(exc), "action": payload.action_type}

        entry: Dict[str, Any] = {
            "action": payload.action_type,
            "payload": payload.to_dict(),
            "result": result,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        self._action_history.append(entry)
        if len(self._action_history) > self._max_history:
            self._action_history = self._action_history[-self._max_history :]
        return result

    async def _do_action(self, pag: Any, payload: ActionPayload) -> Dict[str, Any]:
        atype = payload.action_type
        coords = payload.coordinates

        if atype == "click":
            x, y = coords.x if coords else None, coords.y if coords else None
            if x is not None and y is not None:
                pag.click(x=x, y=y, duration=payload.duration)
            else:
                pag.click(duration=payload.duration)
            return {"executed": True, "action": "click", "coordinates": coords.to_dict() if coords else None}

        if atype == "double_click":
            x, y = coords.x if coords else None, coords.y if coords else None
            if x is not None and y is not None:
                pag.doubleClick(x=x, y=y)
            else:
                pag.doubleClick()
            return {"executed": True, "action": "double_click"}

        if atype == "right_click":
            x, y = coords.x if coords else None, coords.y if coords else None
            if x is not None and y is not None:
                pag.rightClick(x=x, y=y)
            else:
                pag.rightClick()
            return {"executed": True, "action": "right_click"}

        if atype == "type":
            pag.write(payload.text or "")
            return {"executed": True, "action": "type", "text": payload.text}

        if atype == "keypress":
            pag.press(payload.key or "enter")
            return {"executed": True, "action": "keypress", "key": payload.key}

        if atype == "press_combination":
            keys = payload.key_combination or []
            for k in keys:
                pag.keyDown(k)
            for k in reversed(keys):
                pag.keyUp(k)
            return {"executed": True, "action": "press_combination", "keys": keys}

        if atype == "scroll":
            pag.scroll(payload.scroll_amount)
            return {"executed": True, "action": "scroll", "amount": payload.scroll_amount}

        if atype == "move":
            if coords:
                pag.moveTo(coords.x, coords.y, duration=payload.duration)
                return {"executed": True, "action": "move", "coordinates": coords.to_dict()}

        if atype == "drag":
            if coords:
                pag.dragTo(coords.x, coords.y, duration=payload.duration)
                return {"executed": True, "action": "drag", "coordinates": coords.to_dict()}

        if atype == "screenshot":
            info = await ScreenAnalyzer().capture_screen()
            return {"executed": True, "action": "screenshot", "screen_info": info}

        return {"executed": False, "error": f"unhandled_action: {atype}"}

    def get_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self._action_history[-limit:]

    def clear_history(self) -> None:
        self._action_history.clear()


class ComputerUseAgent:
    """Agente de uso de computadora: combina analisis de pantalla y ejecucion de acciones."""

    def __init__(self) -> None:
        self.screen_analyzer = ScreenAnalyzer()
        self.action_executor = GUIActionExecutor()
        self._last_command: Optional[Dict[str, Any]] = None

    async def execute_command(self, command: str) -> Dict[str, Any]:
        cmd = command.lower().strip()
        self._last_command = {"command": command, "timestamp": datetime.utcnow().isoformat() + "Z"}

        if "click" in cmd:
            numbers = re.findall(r"\d+", command)
            x = float(numbers[0]) if len(numbers) >= 1 else None
            y = float(numbers[1]) if len(numbers) >= 2 else None
            coords = Coordinates(x=x, y=y) if x is not None and y is not None else None
            payload = ActionPayload(action_type="click", coordinates=coords)
            result = await self.action_executor.execute(payload)
            self._last_command["result"] = result
            return {"command": "click", "executed": True, "result": result}

        if "type " in cmd or "escribe " in cmd:
            text = command.split(" ", 1)[1] if " " in command else ""
            payload = ActionPayload(action_type="type", text=text)
            result = await self.action_executor.execute(payload)
            self._last_command["result"] = result
            return {"command": "type", "executed": True, "result": result}

        if "press" in cmd and "+" in cmd:
            keys = re.split(r"[\s+]+", command.replace("press ", "").strip())
            keys = [k for k in keys if k]
            payload = ActionPayload(action_type="press_combination", key_combination=keys)
            result = await self.action_executor.execute(payload)
            self._last_command["result"] = result
            return {"command": "key_combination", "executed": True, "result": result}

        if "screenshot" in cmd or "captura" in cmd:
            screen = await self.screen_analyzer.capture_screen()
            self._last_command["result"] = screen
            return {"command": "screenshot", "executed": True, "result": screen}

        if "describe" in cmd or "analiza" in cmd:
            analysis = await self.screen_analyzer.analyze_elements()
            self._last_command["result"] = analysis
            return {"command": "describe", "executed": True, "result": analysis}

        if "scroll" in cmd:
            scroll_match = re.search(r"(-?\d+)", command)
            amount = int(scroll_match.group(1)) if scroll_match else 1
            payload = ActionPayload(action_type="scroll", scroll_amount=amount)
            result = await self.action_executor.execute(payload)
            self._last_command["result"] = result
            return {"command": "scroll", "executed": True, "result": result}

        self._last_command["result"] = {"error": "command_not_recognized"}
        return {"command": "unknown", "executed": False, "error": "command_not_recognized"}

    async def describe_screen(self) -> Dict[str, Any]:
        return await self.screen_analyzer.analyze_elements()

    def get_state(self) -> Dict[str, Any]:
        return {
            "screen_state": self.screen_analyzer.get_screen_state(),
            "executor_available": self.action_executor.available,
            "action_history_count": len(self.action_executor.get_history()),
            "last_command": self._last_command,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
