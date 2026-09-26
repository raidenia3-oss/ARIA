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

    def restart(self, service: str = 'backend') -> Dict[str, Any]:
        return self._request('POST', '/api/restart', {'service': service})

    def deploy(self, service: str = 'backend') -> Dict[str, Any]:
        return self._request('POST', '/api/deploy', {'service': service})

    def transcribe(self, audio_base64: str) -> Dict[str, Any]:
        return self._request('POST', '/api/voice/transcribe', {'audio_base64': audio_base64})


class VoiceCommandRouter:
    def __init__(self, command_map: Optional[Dict[str, str]] = None, backend_client: Optional[AuraBackendClient] = None) -> None:
        self.command_map = command_map or {
            'ejecutar training': 'run_training',
            'detener servicios': 'stop_services',
            'publicar estado': 'publish_status',
            'reiniciar bot': 'restart_bot',
        }
        self.backend_client = backend_client or AuraBackendClient()

    def route(self, text: str) -> str:
        return self.command_map.get(text.lower().strip(), 'unknown')

    def dispatch(self, text: str) -> Dict[str, Any]:
        transcription = self.backend_client.transcribe(text)
        command = self.route(transcription.get('text', text))
        if command == 'run_training':
            return {'command': command, 'backend': self.backend_client.get_status(), 'transcription': transcription}
        if command == 'stop_services':
            return {'command': command, 'backend': self.backend_client.restart('backend'), 'transcription': transcription}
        if command == 'publish_status':
            return {'command': command, 'backend': self.backend_client.get_status(), 'transcription': transcription}
        if command == 'restart_bot':
            return {'command': command, 'backend': self.backend_client.deploy('discord-bot'), 'transcription': transcription}
        return {'command': command, 'backend': {'status': 'ignored'}, 'transcription': transcription}
