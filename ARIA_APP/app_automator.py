"""Automatizacion de apps de escritorio para ARIA usando solo stdlib (ctypes)."""
import ctypes
import subprocess
import time

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
VK_RETURN = 0x0D


def launch_app(path: str, args: str = "") -> dict:
    try:
        proc = subprocess.Popen([path] + (args.split() if args else []))
        return {"status": "ok", "pid": proc.pid}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def find_window(title_contains: str) -> int:
    hwnds = []

    def cb(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            buf = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(hwnd, buf, 256)
            if title_contains.lower() in buf.value.lower():
                hwnds.append(hwnd)
        return True

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    user32.EnumWindows(WNDENUMPROC(cb), 0)
    return hwnds[0] if hwnds else 0


def send_text(text: str, hwnd: int = 0) -> dict:
    if hwnd:
        user32.SetForegroundWindow(hwnd)
        time.sleep(0.2)
    for ch in text:
        # VK for char via VkKeyScanW
        vk = user32.VkKeyScanW(ord(ch))
        if vk == -1:
            continue
        scan = user32.MapVirtualKeyW(vk & 0xFF, 0)
        down = (ctypes.c_ulong * 4)(0, scan, 0, 0)
        # use SendInput with KEYBDINPUT
        ki = ctypes.c_ushort(vk & 0xFF)
        # simplified: use keybd_event
        user32.keybd_event(ki, scan, 0, 0)
        user32.keybd_event(ki, scan, KEYEVENTF_KEYUP, 0)
        time.sleep(0.02)
    return {"status": "ok", "sent": len(text)}


def click(x: int, y: int) -> dict:
    user32.SetCursorPos(x, y)
    time.sleep(0.05)
    user32.mouse_event(0x0002, 0, 0, 0, 0)  # left down
    user32.mouse_event(0x0004, 0, 0, 0, 0)  # left up
    return {"status": "ok", "x": x, "y": y}


def list_windows() -> list:
    out = []

    def cb(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            buf = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(hwnd, buf, 256)
            if buf.value.strip():
                out.append({"hwnd": hwnd, "title": buf.value})
        return True

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    user32.EnumWindows(WNDENUMPROC(cb), 0)
    return out


def run(action: str, **kw) -> dict:
    if action == "launch":
        return launch_app(kw.get("path", ""), kw.get("args", ""))
    if action == "find":
        return {"hwnd": find_window(kw.get("title", ""))}
    if action == "type":
        return send_text(kw.get("text", ""), kw.get("hwnd", 0))
    if action == "click":
        return click(kw.get("x", 0), kw.get("y", 0))
    if action == "list":
        return {"windows": list_windows()}
    return {"status": "error", "error": "accion desconocida"}