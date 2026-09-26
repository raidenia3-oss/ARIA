from __future__ import annotations

from typing import Dict


class GestureController:
    def __init__(self, gesture_map: Dict[str, str] | None = None) -> None:
        self.gesture_map = gesture_map or {
            'open_hand': 'stop',
            'fist': 'pause',
            'index': 'select',
            'two_fingers': 'scroll',
            'swipe': 'navigate',
        }

    def map_gesture(self, gesture_name: str) -> str:
        return self.gesture_map.get(gesture_name, 'unknown')
