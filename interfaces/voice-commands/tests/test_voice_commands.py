from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from voice_commands import VoiceCommandRouter


def test_voice_command_routes_to_action() -> None:
    router = VoiceCommandRouter()
    assert router.route('detener servicios') == 'stop_services'


def test_unknown_voice_command_returns_unknown() -> None:
    router = VoiceCommandRouter()
    assert router.route('comando extraño') == 'unknown'
