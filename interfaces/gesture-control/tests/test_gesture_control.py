from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from gesture_control import GestureController


def test_open_hand_maps_to_stop() -> None:
    controller = GestureController()
    assert controller.map_gesture('open_hand') == 'stop'


def test_unknown_gesture_returns_unknown() -> None:
    controller = GestureController()
    assert controller.map_gesture('unknown') == 'unknown'
