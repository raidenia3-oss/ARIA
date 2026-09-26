from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from voice_commands import VoiceCommandRouter


def test_voice_routing_supports_core_commands() -> None:
    router = VoiceCommandRouter()

    assert router.route('ejecutar training') == 'run_training'
    assert router.route('detener servicios') == 'stop_services'
    assert router.route('publicar estado') == 'publish_status'
    assert router.route('reiniciar bot') == 'restart_bot'


def test_dispatch_uses_backend_client() -> None:
    client = Mock()
    client.get_status.return_value = {'backend': {'status': 'ok'}}
    client.transcribe.return_value = {'text': 'publicar estado', 'command': 'publish_status'}
    router = VoiceCommandRouter(backend_client=client)

    result = router.dispatch('publicar estado')

    assert result['command'] == 'publish_status'
    assert result['backend'] == {'backend': {'status': 'ok'}}
    client.transcribe.assert_called_once_with('publicar estado')


def test_dispatch_supports_all_commands() -> None:
    client = Mock()
    client.get_status.return_value = {'status': 'ok'}
    client.restart.return_value = {'message': 'restarted'}
    client.deploy.return_value = {'message': 'deployed'}
    
    router = VoiceCommandRouter(backend_client=client)
    
    client.transcribe.return_value = {'text': 'ejecutar training', 'command': 'run_training'}
    assert router.dispatch('ejecutar training')['command'] == 'run_training'
    
    client.transcribe.return_value = {'text': 'detener servicios', 'command': 'stop_services'}
    assert router.dispatch('detener servicios')['command'] == 'stop_services'
    
    client.transcribe.return_value = {'text': 'publicar estado', 'command': 'publish_status'}
    assert router.dispatch('publicar estado')['command'] == 'publish_status'
    
    client.transcribe.return_value = {'text': 'reiniciar bot', 'command': 'restart_bot'}
    assert router.dispatch('reiniciar bot')['command'] == 'restart_bot'
    
    client.transcribe.return_value = {'text': 'unknown', 'command': 'unknown'}
    assert router.dispatch('unknown')['command'] == 'unknown'
