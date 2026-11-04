from __future__ import annotations

import threading
import time
from typing import Callable, Optional

try:
    import cv2
    import numpy as np
    _CV2 = True
except Exception:
    _CV2 = False


class HandReactor:
    def __init__(self, on_hand: Callable[[str], None], camera_index: int = 0):
        self.on_hand = on_hand
        self.camera_index = camera_index
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def available(self) -> bool:
        return _CV2

    def start(self):
        if not _CV2:
            return False
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return True

    def stop(self):
        self._stop.set()

    def _loop(self):
        cap = cv2.VideoCapture(self.camera_index)
        if not cap.isOpened():
            return
        # skin color range in HSV
        lower = (0, 30, 60)
        upper = (25, 180, 255)
        while not self._stop.is_set():
            ok, frame = cap.read()
            if not ok:
                time.sleep(0.1)
                continue
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            mask = cv2.inRange(hsv, lower, upper)
            cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            big = [c for c in cnts if cv2.contourArea(c) > 3000]
            if big:
                try:
                    self.on_hand("hand_detected")
                except Exception:
                    pass
            time.sleep(0.3)
        cap.release()