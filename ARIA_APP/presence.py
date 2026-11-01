from __future__ import annotations

import ctypes
import threading
import time
from ctypes import Structure, windll, c_uint, c_ulong, sizeof, byref


class LASTINPUTINFO(Structure):
    _fields_ = [("cbSize", c_uint), ("dwTime", c_ulong)]


def idle_seconds() -> float:
    lii = LASTINPUTINFO()
    lii.cbSize = sizeof(lii)
    if windll.user32.GetLastInputInfo(byref(lii)):
        millis = windll.kernel32.GetTickCount() - lii.dwTime
        return millis / 1000.0
    return 0.0


class PresenceWatcher:
    def __init__(self, on_present, on_away, threshold: float = 120.0, poll: float = 5.0):
        self.on_present = on_present
        self.on_away = on_away
        self.threshold = threshold
        self.poll = poll
        self._stop = threading.Event()
        self._present = True
        self._thread = threading.Thread(target=self._loop, daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set()

    def _loop(self):
        while not self._stop.is_set():
            idle = idle_seconds()
            if idle >= self.threshold and self._present:
                self._present = False
                try:
                    self.on_away()
                except Exception:
                    pass
            elif idle < self.threshold and not self._present:
                self._present = True
                try:
                    self.on_present()
                except Exception:
                    pass
            time.sleep(self.poll)
PY