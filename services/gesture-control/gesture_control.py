from __future__ import annotations

import json
import os
import urllib.request
from typing import Any, Dict, Optional


class AuraBackendClient:
    def __init__(self, base_url: Optional[str] = None, auth_token: Optional[str] = None) -> None:
        self.base_url = (base_url or os.getenv('AURA_BACKEND_URL', 'http://localhost:8000')).rstrip('/')
        self.auth_token = auth_token or os.getenv('AURA_AUTH_TOKEN') or os.getenv('AURA_BEARER_TOKEN')

    def _request(self, method: str, path: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        headers = {'Content-Type': 'application/json'}
        if self.auth_token:
            headers['Authorization'] = f'Bearer {self.auth_token}'

        api_key = os.getenv('AURA_API_KEY')
        if api_key:
            headers['X-API-Key'] = api_key

        data = None if payload is None else json.dumps(payload).encode('utf-8')
        request = urllib.request.Request(f'{self.base_url}{path}', data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                text = response.read().decode('utf-8') or '{}'
                return json.loads(text)
        except Exception as exc:  # pragma: no cover - exercised in unit tests via mock
            return {'error': str(exc)}

    def get_status(self) -> Dict[str, Any]:
        return self._request('GET', '/api/status')

    def get_logs(self, service: str = 'backend', lines: int = 20) -> Dict[str, Any]:
        return self._request('GET', f'/api/logs?service={service}&lines={lines}')

    def restart(self, service: str = 'backend') -> Dict[str, Any]:
        return self._request('POST', '/api/restart', {'service': service})

    def deploy(self, service: str = 'backend') -> Dict[str, Any]:
        return self._request('POST', '/api/deploy', {'service': service})

    def predict_gesture(self, image_base64: str) -> Dict[str, Any]:
        return self._request('POST', '/api/gesture/predict', {'image_base64': image_base64})


class GestureController:
    def __init__(self, gesture_map: Optional[Dict[str, str]] = None, backend_client: Optional[AuraBackendClient] = None) -> None:
        self.gesture_map = gesture_map or {
            'open_hand': 'stop',
            'fist': 'pause',
            'index': 'select',
            'two_fingers': 'scroll',
            'swipe': 'navigate',
        }
        self.backend_client = backend_client or AuraBackendClient()

    def map_gesture(self, gesture_name: str) -> str:
        return self.gesture_map.get(gesture_name, 'unknown')

    def dispatch(self, gesture_name: str) -> Dict[str, Any]:
        action = self.map_gesture(gesture_name)
        if action == 'stop':
            return {'gesture': gesture_name, 'action': action, 'backend': self.backend_client.get_status()}
        if action == 'pause':
            return {'gesture': gesture_name, 'action': action, 'backend': self.backend_client.get_logs('backend', 10)}
        if action == 'select':
            return {'gesture': gesture_name, 'action': action, 'backend': self.backend_client.restart('backend')}
        if action == 'scroll':
            return {'gesture': gesture_name, 'action': action, 'backend': self.backend_client.deploy('backend')}
        return {'gesture': gesture_name, 'action': action, 'backend': {'status': 'ignored'}}
