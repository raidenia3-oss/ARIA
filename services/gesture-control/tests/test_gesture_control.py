from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gesture_control import GestureController


def test_gesture_mapping_supports_core_actions() -> None:
    controller = GestureController()

    assert controller.map_gesture('open_hand') == 'stop'
    assert controller.map_gesture('fist') == 'pause'
    assert controller.map_gesture('index') == 'select'
    assert controller.map_gesture('two_fingers') == 'scroll'
    assert controller.map_gesture('swipe') == 'navigate'


def test_dispatch_uses_backend_client() -> None:
    client = Mock()
    client.get_status.return_value = {'backend': {'status': 'ok'}}
    controller = GestureController(backend_client=client)

    result = controller.dispatch('open_hand')

    assert result['action'] == 'stop'
    assert result['backend'] == {'backend': {'status': 'ok'}}
    client.get_status.assert_called_once_with()


def test_dispatch_supports_all_gestures() -> None:
    client = Mock()
    client.get_status.return_value = {'status': 'ok'}
    client.get_logs.return_value = {'logs': 'log1'}
    client.restart.return_value = {'message': 'restarted'}
    client.deploy.return_value = {'message': 'deployed'}
    controller = GestureController(backend_client=client)

    assert controller.dispatch('open_hand')['action'] == 'stop'
    assert controller.dispatch('fist')['action'] == 'pause'
    assert controller.dispatch('index')['action'] == 'select'
    assert controller.dispatch('two_fingers')['action'] == 'scroll'
    assert controller.dispatch('swipe')['action'] == 'navigate'
    assert controller.dispatch('unknown')['action'] == 'unknown'


def test_predict_gesture_uses_backend_client() -> None:
    client = Mock()
    client.predict_gesture.return_value = {'gesture': 'index', 'confidence': 0.8}
    controller = GestureController(backend_client=client)

    result = controller.dispatch('index')

    assert result['gesture'] == 'index'
    assert result['action'] == 'select'
    client.restart.assert_called_once_with('backend')
