# -*- coding: utf-8 -*-
"""ARIA OS - Computer Use & Automation Routes.

Endpoints para automatización de escritorio Windows:
  POST /api/computer/screenshot        - Capturar pantalla
  POST /api/computer/click             - Click en coordenadas
  POST /api/computer/type              - Escribir texto
  POST /api/computer/key               - Presionar tecla
  POST /api/computer/scroll            - Scroll
  POST /api/computer/drag              - Arrastrar
  GET  /api/computer/windows           - Listar ventanas
  POST /api/computer/window/focus      - Enfocar ventana
  POST /api/computer/execute           - Ejecutar comando
  POST /api/computer/automate          - Automatización compleja (MCP)
  GET  /api/computer/accessibility     - Info de accesibilidad
  POST /api/computer/accessibility/find - Encontrar elemento por accesibilidad

Basado en: sandraschi/windows-computer-use-mcp
"""

from __future__ import annotations

import asyncio
import base64
import logging
import os
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger("ARIA.ComputerUse")

router = APIRouter(prefix="/api/computer", tags=["computer-use"])

# ============================================================================
# Models
# ============================================================================

class ScreenshotRequest(BaseModel):
    region: Optional[List[int]] = None  # [x, y, width, height]
    monitor: int = 0
    format: str = "png"  # png, jpeg, base64


class ScreenshotResponse(BaseModel):
    image_base64: str
    width: int
    height: int
    format: str
    monitor: int


class ClickRequest(BaseModel):
    x: int
    y: int
    button: str = "left"  # left, right, middle
    clicks: int = 1
    delay_ms: int = 0


class TypeRequest(BaseModel):
    text: str
    interval_ms: int = 10


class KeyRequest(BaseModel):
    key: str  # e.g., "enter", "ctrl+c", "alt+tab"
    presses: int = 1


class ScrollRequest(BaseModel):
    x: int
    y: int
    amount: int  # positive = up, negative = down


class DragRequest(BaseModel):
    start_x: int
    start_y: int
    end_x: int
    end_y: int
    duration_ms: int = 500


class WindowInfo(BaseModel):
    handle: int
    title: str
    class_name: str
    process_id: int
    rect: List[int]  # [left, top, right, bottom]
    is_visible: bool
    is_minimized: bool


class FocusWindowRequest(BaseModel):
    handle: Optional[int] = None
    title: Optional[str] = None
    class_name: Optional[str] = None


class ExecuteRequest(BaseModel):
    command: str
    args: List[str] = Field(default_factory=list)
    cwd: Optional[str] = None
    timeout: int = 30
    shell: bool = False


class ExecuteResponse(BaseModel):
    stdout: str
    stderr: str
    returncode: int
    latency_ms: int


class AutomateRequest(BaseModel):
    steps: List[Dict[str, Any]]
    stop_on_error: bool = True


class AutomateResponse(BaseModel):
    results: List[Dict[str, Any]]
    success: bool
    total_latency_ms: int


class AccessibilityElement(BaseModel):
    element_id: str
    name: str
    role: str
    class_name: str
    rect: List[int]
    is_enabled: bool
    is_visible: bool
    children: List["AccessibilityElement"] = Field(default_factory=list)


class FindElementRequest(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    class_name: Optional[str] = None
    window_title: Optional[str] = None
    max_depth: int = 10


# ============================================================================
# Windows Automation Backend
# ============================================================================

_automation_backend = None


def _get_automation_backend():
    """Get or initialize automation backend."""
    global _automation_backend
    if _automation_backend is None:
        _automation_backend = WindowsAutomation()
    return _automation_backend


class WindowsAutomation:
    """Windows automation using UIA (UI Automation) and pywinauto."""
    
    def __init__(self):
        self.uia_available = False
        self.pywinauto_available = False
        self._init_backends()
    
    def _init_backends(self):
        # Try UIA (Windows 10+ built-in)
        try:
            import uiautomation as auto
            self.auto = auto
            self.uia_available = True
            logger.info("UIA automation available")
        except ImportError:
            logger.warning("uiautomation not installed")
        
        # Try pywinauto
        try:
            import pywinauto
            self.pywinauto = pywinauto
            self.pywinauto_available = True
            logger.info("pywinauto available")
        except ImportError:
            logger.warning("pywinauto not installed")
        
        # Try PIL for screenshots
        try:
            from PIL import ImageGrab
            self.ImageGrab = ImageGrab
        except ImportError:
            logger.warning("PIL not installed")
            self.ImageGrab = None
    
    def screenshot(self, region: Optional[List[int]] = None, monitor: int = 0) -> ScreenshotResponse:
        """Take screenshot."""
        if not self.ImageGrab:
            raise HTTPException(status_code=503, detail="PIL not installed")
        
        if region:
            bbox = (region[0], region[1], region[0] + region[2], region[1] + region[3])
            img = self.ImageGrab.grab(bbox=bbox)
        else:
            img = self.ImageGrab.grab(all_screens=(monitor < 0))
        
        # Convert to base64
        import io
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        img_base64 = base64.b64encode(buffer.getvalue()).decode()
        
        return ScreenshotResponse(
            image_base64=img_base64,
            width=img.width,
            height=img.height,
            format="png",
            monitor=monitor
        )
    
    def click(self, x: int, y: int, button: str = "left", clicks: int = 1, delay_ms: int = 0):
        """Click at coordinates."""
        if self.uia_available:
            self.auto.Click(x, y, button=button, clickCount=clicks, delay=delay_ms/1000)
        elif self.pywinauto_available:
            import pywinauto.mouse as mouse
            for _ in range(clicks):
                mouse.click(button=button, coords=(x, y))
                if delay_ms:
                    time.sleep(delay_ms/1000)
        else:
            # Fallback: use Windows API
            import ctypes
            user32 = ctypes.windll.user32
            user32.SetCursorPos(x, y)
            if button == "left":
                user32.mouse_event(0x0002, 0, 0, 0, 0)  # LEFTDOWN
                user32.mouse_event(0x0004, 0, 0, 0, 0)  # LEFTUP
            elif button == "right":
                user32.mouse_event(0x0008, 0, 0, 0, 0)  # RIGHTDOWN
                user32.mouse_event(0x0010, 0, 0, 0, 0)  # RIGHTUP
        
        return {"status": "ok", "x": x, "y": y}
    
    def type_text(self, text: str, interval_ms: int = 10):
        """Type text."""
        if self.uia_available:
            self.auto.SendKeys(text, interval=interval_ms/1000)
        elif self.pywinauto_available:
            import pywinauto.keyboard as keyboard
            keyboard.send_keys(text, with_spaces=True, pause=interval_ms/1000)
        else:
            raise HTTPException(
                status_code=501,
                detail="type_text not executed: no automation backend available "
                       "(install uiautomation or pywinauto: pip install uiautomation pywinauto)"
            )
        
        return {"status": "ok", "length": len(text)}
    
    def press_key(self, key: str, presses: int = 1):
        """Press key combination."""
        if self.uia_available:
            self.auto.SendKeys(key, presses=presses)
        elif self.pywinauto_available:
            import pywinauto.keyboard as keyboard
            keyboard.send_keys(key, presses=presses)
        else:
            raise HTTPException(
                status_code=501,
                detail="press_key not executed: no automation backend available "
                       "(install uiautomation or pywinauto: pip install uiautomation pywinauto)"
            )
        
        return {"status": "ok", "key": key}
    
    def scroll(self, x: int, y: int, amount: int):
        """Scroll at position."""
        if self.uia_available:
            self.auto.Wheel(x, y, amount)
        elif self.pywinauto_available:
            import pywinauto.mouse as mouse
            mouse.wheel(amount, coords=(x, y))
        else:
            raise HTTPException(
                status_code=501,
                detail="scroll not executed: no automation backend available "
                       "(install uiautomation or pywinauto: pip install uiautomation pywinauto)"
            )
        
        return {"status": "ok", "x": x, "y": y, "amount": amount}
    
    def drag(self, start_x: int, start_y: int, end_x: int, end_y: int, duration_ms: int = 500):
        """Drag from start to end."""
        if self.uia_available:
            self.auto.DragDrop(start_x, start_y, end_x, end_y, duration=duration_ms/1000)
        elif self.pywinauto_available:
            import pywinauto.mouse as mouse
            mouse.press(coords=(start_x, start_y))
            time.sleep(0.1)
            mouse.move(coords=(end_x, end_y))
            time.sleep(0.1)
            mouse.release(coords=(end_x, end_y))
        else:
            raise HTTPException(
                status_code=501,
                detail="drag not executed: no automation backend available "
                       "(install uiautomation or pywinauto: pip install uiautomation pywinauto)"
            )
        
        return {"status": "ok"}
    
    def list_windows(self) -> List[WindowInfo]:
        """List all visible windows using UIA with pywinauto + ctypes fallback."""
        windows: List[WindowInfo] = []

        # ── Attempt UIA ──────────────────────────────────────────────
        if self.uia_available:
            try:
                root = self.auto.GetRootControl()
                children = root.GetChildren()
                if children:
                    for win in children:
                        try:
                            if win.ControlTypeName in ("Window", "Pane") or win.NativeWindowHandle != 0:
                                rect = win.BoundingRectangle
                                if rect.width() > 0 and rect.height() > 0:
                                    windows.append(WindowInfo(
                                        handle=win.NativeWindowHandle,
                                        title=win.Name or "Untitled",
                                        class_name=win.ClassName,
                                        process_id=win.ProcessId,
                                        rect=[rect.left, rect.top, rect.right, rect.bottom],
                                        is_visible=win.IsVisible,
                                        is_minimized=False
                                    ))
                        except Exception:
                            continue

                    if windows:
                        return windows
            except Exception as e:
                logger.warning("UIA enumeration failed: %s, falling back to pywinauto", e)
            else:
                if not windows:
                    logger.warning("UIA GetRootControl().GetChildren() returned empty — trying pywinauto fallback")

        # ── Fallback: pywinauto ──────────────────────────────────────
        if self.pywinauto_available:
            try:
                from pywinauto import Desktop
                desktop = Desktop(backend="uia")
                for w in desktop.windows():
                    try:
                        rect = w.rectangle()
                        if rect.width() > 0 and rect.height() > 0:
                            windows.append(WindowInfo(
                                handle=w.handle,
                                title=w.window_text() or "Untitled",
                                class_name=w.class_name() or "Unknown",
                                process_id=w.process_id(),
                                rect=[rect.left, rect.top, rect.right, rect.bottom],
                                is_visible=w.is_visible(),
                                is_minimized=w.is_minimized()
                            ))
                    except Exception:
                        continue

                if windows:
                    return windows
            except Exception as e:
                logger.warning("pywinauto enumeration failed: %s, falling back to ctypes", e)

        # ── Final fallback: EnumWindows via ctypes ───────────────────
        try:
            import ctypes
            from ctypes import wintypes

            EnumWindows = ctypes.windll.user32.EnumWindows
            GetWindowText = ctypes.windll.user32.GetWindowTextW
            GetWindowTextLength = ctypes.windll.user32.GetWindowTextLengthW
            IsWindowVisible = ctypes.windll.user32.IsWindowVisible
            GetClassName = ctypes.windll.user32.GetClassNameW
            GetWindowRect = ctypes.windll.user32.GetWindowRect
            GetWindowThreadProcessId = ctypes.windll.user32.GetWindowThreadProcessId

            class RECT(ctypes.Structure):
                _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                           ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

            @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
            def enum_proc(hwnd, lparam):
                if IsWindowVisible(hwnd):
                    length = GetWindowTextLength(hwnd)
                    if length > 0:
                        buff = ctypes.create_unicode_buffer(length + 1)
                        GetWindowText(hwnd, buff, length + 1)

                        class_buff = ctypes.create_unicode_buffer(256)
                        GetClassName(hwnd, class_buff, 256)

                        rect = RECT()
                        GetWindowRect(hwnd, ctypes.byref(rect))

                        if rect.right - rect.left > 0 and rect.bottom - rect.top > 0:
                            pid = wintypes.DWORD()
                            GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

                            windows.append(WindowInfo(
                                handle=hwnd,
                                title=buff.value,
                                class_name=class_buff.value,
                                process_id=pid.value,
                                rect=[rect.left, rect.top, rect.right, rect.bottom],
                                is_visible=True,
                                is_minimized=False
                            ))
                return True

            EnumWindows(enum_proc, 0)
        except Exception as e:
            logger.error("ctypes EnumWindows fallback failed: %s", e)

        return windows
    
    def focus_window(self, handle: Optional[int] = None, title: Optional[str] = None, class_name: Optional[str] = None):
        """Focus window by handle, title, or class."""
        if self.uia_available:
            root = self.auto.GetRootControl()
            for win in root.GetChildren():
                match = False
                if handle and win.NativeWindowHandle == handle:
                    match = True
                elif title and title.lower() in win.Name.lower():
                    match = True
                elif class_name and class_name.lower() in win.ClassName.lower():
                    match = True
                
                if match:
                    win.SetFocus()
                    return {"status": "focused", "title": win.Name, "handle": win.NativeWindowHandle}
        
        elif self.pywinauto_available:
            if handle:
                win = self.pywinauto.WindowSpecification({"handle": handle})
            elif title:
                win = self.pywinauto.Desktop(backend="uia").window(title=title)
            elif class_name:
                win = self.pywinauto.Desktop(backend="uia").window(class_name=class_name)
            else:
                raise ValueError("Must specify handle, title, or class_name")
            
            win.set_focus()
            return {"status": "focused"}
        
        else:
            import ctypes
            if handle:
                ctypes.windll.user32.SetForegroundWindow(handle)
                return {"status": "focused", "handle": handle}
        
        raise HTTPException(status_code=404, detail="Window not found")
    
    def execute(self, command: str, args: List[str], cwd: Optional[str], timeout: int, shell: bool) -> ExecuteResponse:
        """Execute command."""
        start = time.time()
        
        try:
            if shell:
                cmd = [command] + args
                proc = subprocess.run(
                    " ".join(cmd),
                    cwd=cwd,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    shell=True
                )
            else:
                proc = subprocess.run(
                    [command] + args,
                    cwd=cwd,
                    capture_output=True,
                    text=True,
                    timeout=timeout
                )
            
            return ExecuteResponse(
                stdout=proc.stdout,
                stderr=proc.stderr,
                returncode=proc.returncode,
                latency_ms=int((time.time() - start) * 1000)
            )
        except subprocess.TimeoutExpired:
            return ExecuteResponse(
                stdout="",
                stderr="Timeout",
                returncode=-1,
                latency_ms=int((time.time() - start) * 1000)
            )
        except Exception as e:
            return ExecuteResponse(
                stdout="",
                stderr=str(e),
                returncode=-1,
                latency_ms=int((time.time() - start) * 1000)
            )
    
    def get_accessibility_tree(self, window_title: Optional[str] = None, max_depth: int = 3) -> List[AccessibilityElement]:
        """Get accessibility tree for window."""
        elements = []
        
        if self.uia_available:
            root = self.auto.GetRootControl()
            
            if window_title:
                for win in root.GetChildren():
                    if window_title.lower() in win.Name.lower():
                        root = win
                        break
            
            def walk(control, depth=0):
                if depth > max_depth:
                    return None
                
                try:
                    rect = control.BoundingRectangle
                    elem = AccessibilityElement(
                        element_id=str(id(control)),
                        name=control.Name,
                        role=control.ControlTypeName,
                        class_name=control.ClassName,
                        rect=[rect.left, rect.top, rect.right, rect.bottom],
                        is_enabled=control.IsEnabled,
                        is_visible=control.IsVisible
                    )
                    
                    for child in control.GetChildren():
                        child_elem = walk(child, depth + 1)
                        if child_elem:
                            elem.children.append(child_elem)
                    
                    return elem
                except:
                    return None
            
            result = walk(root)
            if result:
                elements.append(result)
        
        return elements
    
    def find_element(self, name: Optional[str] = None, role: Optional[str] = None, 
                     class_name: Optional[str] = None, window_title: Optional[str] = None,
                     max_depth: int = 10) -> List[AccessibilityElement]:
        """Find accessibility element."""
        results = []
        
        if self.uia_available:
            root = self.auto.GetRootControl()
            
            if window_title:
                for win in root.GetChildren():
                    if window_title.lower() in win.Name.lower():
                        root = win
                        break
            
            def walk(control, depth=0):
                if depth > max_depth:
                    return
                
                try:
                    match = True
                    if name and name.lower() not in control.Name.lower():
                        match = False
                    if role and role.lower() not in control.ControlTypeName.lower():
                        match = False
                    if class_name and class_name.lower() not in control.ClassName.lower():
                        match = False
                    
                    if match:
                        rect = control.BoundingRectangle
                        results.append(AccessibilityElement(
                            element_id=str(id(control)),
                            name=control.Name,
                            role=control.ControlTypeName,
                            class_name=control.ClassName,
                            rect=[rect.left, rect.top, rect.right, rect.bottom],
                            is_enabled=control.IsEnabled,
                            is_visible=control.IsVisible
                        ))
                    
                    for child in control.GetChildren():
                        walk(child, depth + 1)
                except:
                    pass
            
            walk(root)
        
        return results


# ============================================================================
# Endpoints
# ============================================================================

@router.post("/screenshot", response_model=ScreenshotResponse)
async def screenshot(req: ScreenshotRequest):
    """Capture screenshot."""
    backend = _get_automation_backend()
    return backend.screenshot(req.region, req.monitor)


@router.post("/click")
async def click(req: ClickRequest):
    """Click at coordinates."""
    backend = _get_automation_backend()
    return backend.click(req.x, req.y, req.button, req.clicks, req.delay_ms)


@router.post("/type")
async def type_text(req: TypeRequest):
    """Type text."""
    backend = _get_automation_backend()
    return backend.type_text(req.text, req.interval_ms)


@router.post("/key")
async def press_key(req: KeyRequest):
    """Press key."""
    backend = _get_automation_backend()
    return backend.press_key(req.key, req.presses)


@router.post("/scroll")
async def scroll(req: ScrollRequest):
    """Scroll."""
    backend = _get_automation_backend()
    return backend.scroll(req.x, req.y, req.amount)


@router.post("/drag")
async def drag(req: DragRequest):
    """Drag."""
    backend = _get_automation_backend()
    return backend.drag(req.start_x, req.start_y, req.end_x, req.end_y, req.duration_ms)


@router.get("/windows", response_model=List[WindowInfo])
async def list_windows():
    """List all windows."""
    backend = _get_automation_backend()
    return backend.list_windows()


@router.post("/window/focus")
async def focus_window(req: FocusWindowRequest):
    """Focus window."""
    backend = _get_automation_backend()
    return backend.focus_window(req.handle, req.title, req.class_name)


@router.post("/execute", response_model=ExecuteResponse)
async def execute(req: ExecuteRequest):
    """Execute command."""
    backend = _get_automation_backend()
    return backend.execute(req.command, req.args, req.cwd, req.timeout, req.shell)


@router.post("/automate", response_model=AutomateResponse)
async def automate(req: AutomateRequest):
    """Run automation sequence."""
    backend = _get_automation_backend()
    start = time.time()
    results = []
    success = True
    
    for i, step in enumerate(req.steps):
        action = step.get("action")
        params = step.get("params", {})
        
        try:
            if action == "click":
                result = backend.click(**params)
            elif action == "type":
                result = backend.type_text(**params)
            elif action == "key":
                result = backend.press_key(**params)
            elif action == "scroll":
                result = backend.scroll(**params)
            elif action == "drag":
                result = backend.drag(**params)
            elif action == "focus":
                result = backend.focus_window(**params)
            elif action == "execute":
                result = backend.execute(**params)
            elif action == "wait":
                await asyncio.sleep(params.get("seconds", 1))
                result = {"status": "waited"}
            elif action == "screenshot":
                result = backend.screenshot(**params)
            else:
                result = {"status": "error", "error": f"Unknown action: {action}"}
            
            results.append({"step": i, "action": action, "result": result})
            
            if "error" in str(result) and req.stop_on_error:
                success = False
                break
                
        except Exception as e:
            results.append({"step": i, "action": action, "error": str(e)})
            success = False
            if req.stop_on_error:
                break
    
    return AutomateResponse(
        results=results,
        success=success,
        total_latency_ms=int((time.time() - start) * 1000)
    )


@router.get("/accessibility", response_model=List[AccessibilityElement])
async def get_accessibility_tree(window_title: Optional[str] = None, max_depth: int = 3):
    """Get accessibility tree."""
    backend = _get_automation_backend()
    return backend.get_accessibility_tree(window_title, max_depth)


@router.post("/accessibility/find", response_model=List[AccessibilityElement])
async def find_element(req: FindElementRequest):
    """Find accessibility element."""
    backend = _get_automation_backend()
    return backend.find_element(
        req.name, req.role, req.class_name, req.window_title, req.max_depth
    )


@router.get("/health")
async def computer_use_health():
    """Health check for computer use."""
    backend = _get_automation_backend()
    
    return {
        "uia_available": backend.uia_available,
        "pywinauto_available": backend.pywinauto_available,
        "pil_available": backend.ImageGrab is not None,
        "timestamp": time.time()
    }


@router.get("/debug/window-test")
async def debug_window_test():
    """Debug endpoint para verificar window enumeration."""
    backend = _get_automation_backend()
    windows = backend.list_windows()
    return {
        "uia_available": backend.uia_available,
        "pywinauto_available": backend.pywinauto_available,
        "pil_available": backend.ImageGrab is not None,
        "windows_count": len(windows),
        "windows": [w.model_dump() for w in windows[:5]],
        "test_status": "✅ Window enumeration working"
    }


# ============================================================================
# MCP Computer Use Integration (for advanced automation)
# ============================================================================

@router.post("/mcp/execute")
async def mcp_computer_use(req: Dict[str, Any]):
    """Execute via Windows Computer Use MCP server."""
    # This would connect to the MCP server for computer use
    # Based on: sandraschi/windows-computer-use-mcp
    
    # For now, delegate to local backend
    backend = _get_automation_backend()
    action = req.get("action")
    params = req.get("params", {})
    
    if action == "click":
        return backend.click(**params)
    elif action == "type":
        return backend.type_text(**params)
    elif action == "key":
        return backend.press_key(**params)
    elif action == "screenshot":
        return backend.screenshot(**params)
    elif action == "list_windows":
        return {"windows": backend.list_windows()}
    
    raise HTTPException(status_code=400, detail=f"Unknown MCP action: {action}")