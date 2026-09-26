from __future__ import annotations

import asyncio
import os
import re
import platform
import secrets
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import psutil


class OSActionType(str, Enum):
    CLICK = "click"
    DOUBLE_CLICK = "double_click"
    RIGHT_CLICK = "right_click"
    TYPE = "type"
    KEYPRESS = "keypress"
    KEY_COMBINATION = "key_combination"
    SCROLL = "scroll"
    MOVE = "move"
    DRAG = "drag"
    SCREENSHOT = "screenshot"
    FOCUS_WINDOW = "focus_window"
    LIST_WINDOWS = "list_windows"
    CLOSE_WINDOW = "close_window"
    MINIMIZE_WINDOW = "minimize_window"
    MAXIMIZE_WINDOW = "maximize_window"
    RUN_COMMAND = "run_command"
    LAUNCH_APP = "launch_app"


class RiskLevel(str, Enum):
    SAFE = "safe"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class OSAction:
    action_type: OSActionType
    coordinates: Optional[Tuple[float, float]] = None
    text: Optional[str] = None
    key: Optional[str] = None
    key_combination: Optional[List[str]] = None
    scroll_amount: int = 0
    duration: float = 0.0
    delay: float = 0.0
    window_title: Optional[str] = None
    command: Optional[str] = None
    app_name: Optional[str] = None
    app_args: Optional[List[str]] = None
    require_confirmation: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "action_type": self.action_type.value,
            "coordinates": list(self.coordinates) if self.coordinates else None,
            "text": self.text,
            "key": self.key,
            "key_combination": self.key_combination,
            "scroll_amount": self.scroll_amount,
            "duration": self.duration,
            "delay": self.delay,
            "window_title": self.window_title,
            "command": self.command,
            "app_name": self.app_name,
            "app_args": self.app_args,
            "require_confirmation": self.require_confirmation,
            "metadata": self.metadata,
        }
        return d


@dataclass
class CommandValidationResult:
    allowed: bool
    risk_level: RiskLevel
    requires_confirmation: bool
    reason: str = ""
    sanitized_command: Optional[str] = None
    warning: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allowed": self.allowed,
            "risk_level": self.risk_level.value,
            "requires_confirmation": self.requires_confirmation,
            "reason": self.reason,
            "sanitized_command": self.sanitized_command,
            "warning": self.warning,
        }


@dataclass
class ActionResult:
    success: bool
    action_type: str
    output: Any = None
    error: Optional[str] = None
    risk_level: RiskLevel = RiskLevel.SAFE
    requires_confirmation: bool = False
    confirmation_prompt: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "action_type": self.action_type,
            "output": self.output,
            "error": self.error,
            "risk_level": self.risk_level.value,
            "requires_confirmation": self.requires_confirmation,
            "confirmation_prompt": self.confirmation_prompt,
            "metadata": self.metadata,
        }


class SafetyFilter:
    """Filtro de seguridad que intercepta comandos destructivos o no autorizados."""

    DANGEROUS_PATTERNS = [
        r"\brm\s+-[a-z]*r[a-z]*\s+(?:/|\*)",
        r"\bmkfs\b",
        r"\bdd\s+if=.*of=/dev/",
        r":\(\)\s*\{.*\};\s*:",  # fork bomb
        r"\bshutdown\b",
        r"\breboot\b",
        r"\bpoweroff\b",
        r"\bhalt\b",
        r"\biptables\s+-F",
        r"\bchmod\s+777\s+/",
        r"\bchown\s+.*\s+/",
        r"\bformat\s+[A-Za-z]:",
        r"\bdel\s+/[fqs]\s+",
        r"\bformat\s+[A-Za-z]:",
    ]

    DANGEROUS_COMMANDS = {
        "shutdown", "reboot", "poweroff", "halt",
        "mkfs", "dd", "fdisk", "parted",
        "net user /add", "net localgroup administrators",
    }

    ALLOWED_COMMAND_PATTERNS = [
        r"^echo\s+",
        r"^ls\s+|^dir\s+",
        r"^cat\s+",
        r"^head\s+",
        r"^tail\s+",
        r"^grep\s+",
        r"^find\s+",
        r"^pwd$",
        r"^whoami$",
        r"^date$",
        r"^cal$",
        r"^uptime$",
        r"^df\s+-h$",
        r"^free\s+-h$",
        r"^ps\s+",
        r"^top\s+-bn",
        r"^which\s+",
        r"^whereis\s+",
        r"^python\s+.*\.py$",
        r"^python3\s+.*\.py$",
        r"^pip\s+(list|show|install)",
        r"^git\s+(status|diff|log|branch|tag|remote)",
        r"^npm\s+(list|run|start)",
    ]

    def __init__(self, allowed_commands: Optional[List[str]] = None,
                 require_confirmation_for: Optional[List[str]] = None) -> None:
        self._allowed_commands = set(allowed_commands or [])
        self._require_confirmation_for = set(require_confirmation_for or [])
        self._confirmation_cache: Dict[str, bool] = {}

    def validate_command(self, command: str) -> CommandValidationResult:
        cmd = command.strip()
        cmd_lower = cmd.lower()

        for pattern in self.DANGEROUS_PATTERNS:
            if re.search(pattern, cmd_lower):
                return CommandValidationResult(
                    allowed=False,
                    risk_level=RiskLevel.CRITICAL,
                    requires_confirmation=False,
                    reason=f"Comando potencialmente destructivo detectado: {pattern}",
                )

        tokens = cmd_lower.split()
        if tokens and tokens[0] in self.DANGEROUS_COMMANDS:
            return CommandValidationResult(
                allowed=False,
                risk_level=RiskLevel.CRITICAL,
                requires_confirmation=False,
                reason=f"Comando prohibido: {tokens[0]}",
            )

        if self._allowed_commands:
            if cmd not in self._allowed_commands:
                matched = False
                for allowed in self._allowed_commands:
                    if cmd_lower.startswith(allowed.lower()):
                        matched = True
                        break
                if not matched:
                    return CommandValidationResult(
                        allowed=False,
                        risk_level=RiskLevel.HIGH,
                        requires_confirmation=True,
                        reason="Comando no esta en la lista blanca",
                        sanitized_command=cmd,
                    )

        risk = RiskLevel.LOW
        requires_confirm = False

        if tokens:
            base = tokens[0]
            if base in ("rm", "mv", "cp", "chmod", "chown", "kill", "curl", "wget"):
                risk = RiskLevel.HIGH
                requires_confirm = True
            elif base in ("sudo", "su"):
                risk = RiskLevel.CRITICAL
                requires_confirm = True
            elif base in ("pip", "npm", "git", "docker"):
                risk = RiskLevel.MEDIUM
                requires_confirm = True
            elif base in self._require_confirmation_for:
                requires_confirm = True

        return CommandValidationResult(
            allowed=True,
            risk_level=risk,
            requires_confirmation=requires_confirm,
            sanitized_command=cmd,
        )

    def set_confirmation(self, command: str, approved: bool) -> None:
        self._confirmation_cache[command.strip().lower()] = approved

    def is_confirmed(self, command: str) -> bool:
        return self._confirmation_cache.get(command.strip().lower(), False)


class OSController:
    """Controlador de sistema operativo local con ejecucion segura de eventos de entrada."""

    def __init__(self, safety_filter: Optional[SafetyFilter] = None) -> None:
        self._safety = safety_filter or SafetyFilter()
        self._action_history: List[Dict[str, Any]] = []
        self._max_history: int = 500
        self._safety_enabled: bool = True
        self._pyautogui_available: bool = self._check_pyautogui()
        self._pygetwindow_available: bool = self._check_pygetwindow()

    @staticmethod
    def _check_pyautogui() -> bool:
        try:
            import pyautogui
            return True
        except ImportError:
            return False

    @staticmethod
    def _check_pygetwindow() -> bool:
        try:
            import pygetwindow
            return True
        except ImportError:
            return False

    @property
    def available(self) -> bool:
        return self._pyautogui_available

    @property
    def window_manager_available(self) -> bool:
        return self._pygetwindow_available

    def get_status(self) -> Dict[str, Any]:
        return {
            "pyautogui_available": self._pyautogui_available,
            "pygetwindow_available": self._pygetwindow_available,
            "safety_enabled": self._safety_enabled,
            "history_count": len(self._action_history),
            "platform": platform.system(),
        }

    async def execute_action(self, action: OSAction) -> ActionResult:
        if self._safety_enabled and action.action_type in (
            OSActionType.RUN_COMMAND,
            OSActionType.LAUNCH_APP,
        ):
            if action.command:
                validation = self._safety.validate_command(action.command)
                if not validation.allowed:
                    return ActionResult(
                        success=False,
                        action_type=action.action_type.value,
                        error=f"Comando bloqueado: {validation.reason}",
                        risk_level=validation.risk_level,
                    )
                if validation.requires_confirmation and not self._safety.is_confirmed(action.command):
                    return ActionResult(
                        success=False,
                        action_type=action.action_type.value,
                        error="Requiere confirmacion del usuario",
                        risk_level=validation.risk_level,
                        requires_confirmation=True,
                        confirmation_prompt=f"Confirmar ejecucion de: {action.command}",
                    )

        if action.delay > 0:
            await asyncio.sleep(action.delay)

        try:
            result = await self._do_action(action)
        except Exception as exc:
            result = ActionResult(
                success=False,
                action_type=action.action_type.value,
                error=str(exc),
            )

        entry = {
            "action_type": action.action_type.value,
            "payload": action.to_dict(),
            "result": result.to_dict(),
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        self._action_history.append(entry)
        if len(self._action_history) > self._max_history:
            self._action_history = self._action_history[-self._max_history:]
        return result

    async def _do_action(self, action: OSAction) -> ActionResult:
        atype = action.action_type

        if atype == OSActionType.CLICK:
            return await self._do_click(action)
        if atype == OSActionType.DOUBLE_CLICK:
            return await self._do_click(action, clicks=2)
        if atype == OSActionType.RIGHT_CLICK:
            return await self._do_click(action, button="right")
        if atype == OSActionType.TYPE:
            return await self._do_type(action)
        if atype == OSActionType.KEYPRESS:
            return await self._do_keypress(action)
        if atype == OSActionType.KEY_COMBINATION:
            return await self._do_key_combination(action)
        if atype == OSActionType.SCROLL:
            return await self._do_scroll(action)
        if atype == OSActionType.MOVE:
            return await self._do_move(action)
        if atype == OSActionType.DRAG:
            return await self._do_drag(action)
        if atype == OSActionType.SCREENSHOT:
            return await self._do_screenshot(action)
        if atype == OSActionType.FOCUS_WINDOW:
            return await self._do_focus_window(action)
        if atype == OSActionType.LIST_WINDOWS:
            return await self._do_list_windows(action)
        if atype == OSActionType.CLOSE_WINDOW:
            return await self._do_close_window(action)
        if atype == OSActionType.MINIMIZE_WINDOW:
            return await self._do_minimize_window(action)
        if atype == OSActionType.MAXIMIZE_WINDOW:
            return await self._do_maximize_window(action)
        if atype == OSActionType.RUN_COMMAND:
            return await self._do_run_command(action)
        if atype == OSActionType.LAUNCH_APP:
            return await self._do_launch_app(action)

        return ActionResult(
            success=False,
            action_type=atype.value,
            error=f"Unhandled action type: {atype}",
        )

    async def _do_click(self, action: OSAction, clicks: int = 1, button: str = "left") -> ActionResult:
        if not self._pyautogui_available:
            return ActionResult(success=False, action_type=action.action_type.value, error="pyautogui not available")
        import pyautogui
        coords = action.coordinates
        x, y = coords if coords else (None, None)
        try:
            if x is not None and y is not None:
                pyautogui.click(x=x, y=y, clicks=clicks, button=button, duration=action.duration)
            else:
                pyautogui.click(clicks=clicks, button=button, duration=action.duration)
            return ActionResult(
                success=True,
                action_type=action.action_type.value,
                output={"clicked": True, "coordinates": [x, y] if x is not None else None, "clicks": clicks},
            )
        except Exception as exc:
            return ActionResult(success=False, action_type=action.action_type.value, error=str(exc))

    async def _do_type(self, action: OSAction) -> ActionResult:
        if not self._pyautogui_available:
            return ActionResult(success=False, action_type=action.action_type.value, error="pyautogui not available")
        import pyautogui
        try:
            pyautogui.write(action.text or "", interval=action.duration or 0.05)
            return ActionResult(
                success=True,
                action_type=action.action_type.value,
                output={"typed": True, "text": action.text},
            )
        except Exception as exc:
            return ActionResult(success=False, action_type=action.action_type.value, error=str(exc))

    async def _do_keypress(self, action: OSAction) -> ActionResult:
        if not self._pyautogui_available:
            return ActionResult(success=False, action_type=action.action_type.value, error="pyautogui not available")
        import pyautogui
        try:
            pyautogui.press(action.key or "enter")
            return ActionResult(
                success=True,
                action_type=action.action_type.value,
                output={"pressed": True, "key": action.key},
            )
        except Exception as exc:
            return ActionResult(success=False, action_type=action.action_type.value, error=str(exc))

    async def _do_key_combination(self, action: OSAction) -> ActionResult:
        if not self._pyautogui_available:
            return ActionResult(success=False, action_type=action.action_type.value, error="pyautogui not available")
        import pyautogui
        keys = action.key_combination or []
        try:
            for k in keys:
                pyautogui.keyDown(k)
            for k in reversed(keys):
                pyautogui.keyUp(k)
            return ActionResult(
                success=True,
                action_type=action.action_type.value,
                output={"pressed_combination": True, "keys": keys},
            )
        except Exception as exc:
            return ActionResult(success=False, action_type=action.action_type.value, error=str(exc))

    async def _do_scroll(self, action: OSAction) -> ActionResult:
        if not self._pyautogui_available:
            return ActionResult(success=False, action_type=action.action_type.value, error="pyautogui not available")
        import pyautogui
        try:
            pyautogui.scroll(action.scroll_amount)
            return ActionResult(
                success=True,
                action_type=action.action_type.value,
                output={"scrolled": True, "amount": action.scroll_amount},
            )
        except Exception as exc:
            return ActionResult(success=False, action_type=action.action_type.value, error=str(exc))

    async def _do_move(self, action: OSAction) -> ActionResult:
        if not self._pyautogui_available:
            return ActionResult(success=False, action_type=action.action_type.value, error="pyautogui not available")
        import pyautogui
        coords = action.coordinates
        if not coords:
            return ActionResult(success=False, action_type=action.action_type.value, error="coordinates required")
        try:
            pyautogui.moveTo(coords[0], coords[1], duration=action.duration)
            return ActionResult(
                success=True,
                action_type=action.action_type.value,
                output={"moved": True, "coordinates": list(coords)},
            )
        except Exception as exc:
            return ActionResult(success=False, action_type=action.action_type.value, error=str(exc))

    async def _do_drag(self, action: OSAction) -> ActionResult:
        if not self._pyautogui_available:
            return ActionResult(success=False, action_type=action.action_type.value, error="pyautogui not available")
        import pyautogui
        coords = action.coordinates
        if not coords:
            return ActionResult(success=False, action_type=action.action_type.value, error="coordinates required")
        try:
            pyautogui.dragTo(coords[0], coords[1], duration=action.duration)
            return ActionResult(
                success=True,
                action_type=action.action_type.value,
                output={"dragged": True, "coordinates": list(coords)},
            )
        except Exception as exc:
            return ActionResult(success=False, action_type=action.action_type.value, error=str(exc))

    async def _do_screenshot(self, action: OSAction) -> ActionResult:
        if not self._pyautogui_available:
            return ActionResult(success=False, action_type=action.action_type.value, error="pyautogui not available")
        import pyautogui
        try:
            screenshot = pyautogui.screenshot()
            return ActionResult(
                success=True,
                action_type=action.action_type.value,
                output={
                    "captured": True,
                    "width": screenshot.width,
                    "height": screenshot.height,
                    "mode": screenshot.mode,
                },
            )
        except Exception as exc:
            return ActionResult(success=False, action_type=action.action_type.value, error=str(exc))

    async def _do_focus_window(self, action: OSAction) -> ActionResult:
        if not self._pygetwindow_available:
            return ActionResult(success=False, action_type=action.action_type.value, error="pygetwindow not available")
        import pygetwindow as gw
        title = action.window_title or ""
        try:
            windows = gw.getWindowsWithTitle(title)
            if windows:
                windows[0].activate()
                return ActionResult(
                    success=True,
                    action_type=action.action_type.value,
                    output={"focused": True, "title": windows[0].title},
                )
            return ActionResult(
                success=False,
                action_type=action.action_type.value,
                error=f"Window not found: {title}",
            )
        except Exception as exc:
            return ActionResult(success=False, action_type=action.action_type.value, error=str(exc))

    async def _do_list_windows(self, action: OSAction) -> ActionResult:
        if not self._pygetwindow_available:
            return ActionResult(success=False, action_type=action.action_type.value, error="pygetwindow not available")
        import pygetwindow as gw
        try:
            windows = gw.getAllWindows()
            return ActionResult(
                success=True,
                action_type=action.action_type.value,
                output={
                    "windows": [
                        {
                            "title": w.title,
                            "visible": w.visible,
                            "active": w.isActive,
                            "size": [w.width, w.height] if hasattr(w, "width") else None,
                            "position": [w.left, w.top] if hasattr(w, "left") else None,
                        }
                        for w in windows
                    ],
                    "count": len(windows),
                },
            )
        except Exception as exc:
            return ActionResult(success=False, action_type=action.action_type.value, error=str(exc))

    async def _do_close_window(self, action: OSAction) -> ActionResult:
        if not self._pygetwindow_available:
            return ActionResult(success=False, action_type=action.action_type.value, error="pygetwindow not available")
        import pygetwindow as gw
        title = action.window_title or ""
        try:
            windows = gw.getWindowsWithTitle(title)
            if windows:
                windows[0].close()
                return ActionResult(
                    success=True,
                    action_type=action.action_type.value,
                    output={"closed": True, "title": windows[0].title},
                )
            return ActionResult(
                success=False,
                action_type=action.action_type.value,
                error=f"Window not found: {title}",
            )
        except Exception as exc:
            return ActionResult(success=False, action_type=action.action_type.value, error=str(exc))

    async def _do_minimize_window(self, action: OSAction) -> ActionResult:
        if not self._pygetwindow_available:
            return ActionResult(success=False, action_type=action.action_type.value, error="pygetwindow not available")
        import pygetwindow as gw
        title = action.window_title or ""
        try:
            windows = gw.getWindowsWithTitle(title)
            if windows:
                windows[0].minimize()
                return ActionResult(
                    success=True,
                    action_type=action.action_type.value,
                    output={"minimized": True, "title": windows[0].title},
                )
            return ActionResult(
                success=False,
                action_type=action.action_type.value,
                error=f"Window not found: {title}",
            )
        except Exception as exc:
            return ActionResult(success=False, action_type=action.action_type.value, error=str(exc))

    async def _do_maximize_window(self, action: OSAction) -> ActionResult:
        if not self._pygetwindow_available:
            return ActionResult(success=False, action_type=action.action_type.value, error="pygetwindow not available")
        import pygetwindow as gw
        title = action.window_title or ""
        try:
            windows = gw.getWindowsWithTitle(title)
            if windows:
                windows[0].maximize()
                return ActionResult(
                    success=True,
                    action_type=action.action_type.value,
                    output={"maximized": True, "title": windows[0].title},
                )
            return ActionResult(
                success=False,
                action_type=action.action_type.value,
                error=f"Window not found: {title}",
            )
        except Exception as exc:
            return ActionResult(success=False, action_type=action.action_type.value, error=str(exc))

    async def _do_run_command(self, action: OSAction) -> ActionResult:
        command = action.command or ""
        if not command:
            return ActionResult(success=False, action_type=action.action_type.value, error="command is required")
        try:
            timeout = int(action.metadata.get("timeout", 30))
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            return ActionResult(
                success=True,
                action_type=action.action_type.value,
                output={
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "returncode": result.returncode,
                },
            )
        except subprocess.TimeoutExpired:
            return ActionResult(
                success=False,
                action_type=action.action_type.value,
                error="command timed out",
            )
        except Exception as exc:
            return ActionResult(success=False, action_type=action.action_type.value, error=str(exc))

    async def _do_launch_app(self, action: OSAction) -> ActionResult:
        app = action.app_name or ""
        if not app:
            return ActionResult(success=False, action_type=action.action_type.value, error="app_name is required")
        args = action.app_args or []
        cmd = [app] + [str(a) for a in args]
        try:
            subprocess.Popen(cmd, shell=False)
            return ActionResult(
                success=True,
                action_type=action.action_type.value,
                output={"launched": True, "command": cmd},
            )
        except Exception as exc:
            try:
                subprocess.Popen(cmd, shell=True)
                return ActionResult(
                    success=True,
                    action_type=action.action_type.value,
                    output={"launched": True, "command": cmd},
                )
            except Exception as exc2:
                return ActionResult(
                    success=False,
                    action_type=action.action_type.value,
                    error=str(exc2),
                )

    def get_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self._action_history[-limit:]

    def clear_history(self) -> None:
        self._action_history.clear()

    def confirm_action(self, command: str, approved: bool) -> None:
        self._safety.set_confirmation(command, approved)


os_controller = OSController()


__all__ = [
    "OSController",
    "OSAction",
    "OSActionType",
    "RiskLevel",
    "SafetyFilter",
    "CommandValidationResult",
    "ActionResult",
    "os_controller",
]
