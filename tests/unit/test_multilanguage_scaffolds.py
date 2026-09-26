import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_module(module_name: str, path: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_gesture_mapping_supports_core_actions():
    gesture_module = load_module(
        "gesture_control",
        ROOT / ".." / "interfaces" / "gesture-control" / "gesture_control.py",
    )
    controller = gesture_module.GestureController()

    assert controller.map_gesture("open_hand") == "stop"
    assert controller.map_gesture("fist") == "pause"
    assert controller.map_gesture("index") == "select"
    assert controller.map_gesture("two_fingers") == "scroll"
    assert controller.map_gesture("swipe") == "navigate"


def test_voice_routing_supports_core_commands():
    voice_module = load_module(
        "voice_commands",
        ROOT / ".." / "interfaces" / "voice-commands" / "voice_commands.py",
    )
    router = voice_module.VoiceCommandRouter()

    assert router.route("ejecutar training") == "run_training"
    assert router.route("detener servicios") == "stop_services"
    assert router.route("publicar estado") == "publish_status"
    assert router.route("reiniciar bot") == "restart_bot"
