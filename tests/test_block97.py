"""BLOQUE 97 - unit tests for Omni-Interaction engine."""

import pytest

from backend.hud.omni_interaction import (
    HUDController,
    HUDMode,
    HUDPosition,
    HUDState,
    OmniChannel,
    OmniCommand,
    OmniEvent,
    OmniInput,
    OmniInputSynthesizer,
    OmniIntent,
    OmniInteractionEngine,
    get_omni_engine,
    reset_omni_engine,
)


@pytest.fixture(autouse=True)
def _clean():
    reset_omni_engine()
    yield
    reset_omni_engine()


def test_enums():
    assert OmniChannel.TEXT.value == "text"
    assert OmniChannel.VOICE.value == "voice"
    assert OmniChannel.GESTURE.value == "gesture"
    assert OmniChannel.SCREEN_CONTEXT.value == "screen_context"
    assert OmniChannel.HOTKEY.value == "hotkey"
    assert OmniIntent.EXECUTE.value == "execute"
    assert OmniIntent.QUERY.value == "query"
    assert OmniIntent.CONTROL.value == "control"
    assert OmniIntent.NOTIFY.value == "notify"
    assert OmniIntent.CANCEL.value == "cancel"
    assert HUDMode.FLOATING.value == "floating"
    assert HUDMode.MINIMAL.value == "minimal"
    assert HUDMode.DOCKED.value == "docked"
    assert HUDPosition.BOTTOM_RIGHT.value == "bottom_right"


def test_dataclasses():
    inp = OmniInput(channel=OmniChannel.TEXT.value, raw_text="hola", confidence=0.9)
    assert inp.channel == "text"
    assert inp.offline_only is True
    cmd = OmniCommand(intent=OmniIntent.EXECUTE.value, target="app", params={"x": 1})
    assert cmd.target == "app"
    st = HUDState()
    assert st.mode == HUDMode.FLOATING
    assert st.offline_only is True
    ev = OmniEvent(type="test", payload={"a": 1})
    assert ev.payload == {"a": 1}


def test_synthesize_text():
    s = OmniInputSynthesizer()
    inp = s.ingest(OmniChannel.TEXT.value, text="abre calculadora")
    assert inp.intent in (
        OmniIntent.EXECUTE.value,
        OmniIntent.CONTROL.value,
        OmniIntent.NAVIGATE.value,
    )
    inp2 = s.ingest(OmniChannel.TEXT.value, text="what time is it")
    assert inp2.intent == OmniIntent.QUERY.value
    inp3 = s.ingest(OmniChannel.TEXT.value, text="cancela todo")
    assert inp3.intent == OmniIntent.CANCEL.value


def test_synthesize_hotkey():
    s = OmniInputSynthesizer()
    inp = s.ingest(OmniChannel.HOTKEY.value, text="ctrl+n")
    assert inp.intent == OmniIntent.CONTROL.value
    assert inp.channel == OmniChannel.HOTKEY.value


def test_synthesize_gesture():
    s = OmniInputSynthesizer()
    inp = s.ingest(OmniChannel.GESTURE.value, text="swipe_right")
    assert inp.intent == OmniIntent.CONTROL.value


def test_synthesize_screen_context():
    s = OmniInputSynthesizer()
    inp = s.ingest(OmniChannel.SCREEN_CONTEXT.value, text="boton azul")
    assert inp.intent == OmniIntent.QUERY.value


def test_hud_controller_modes():
    c = HUDController()
    c.set_mode(HUDMode.MINIMAL)
    assert c.state.mode == HUDMode.MINIMAL
    c.set_position(HUDPosition.TOP_LEFT)
    assert c.state.position == HUDPosition.TOP_LEFT
    c.set_opacity(0.5)
    assert c.state.opacity == 0.5


def test_hud_controller_alerts():
    c = HUDController()
    c.push_alert("Hola", message="msg", severity="info")
    assert len(c.state.alerts) == 1
    c.clear_alerts()
    assert len(c.state.alerts) == 0


def test_hud_controller_quick_actions():
    c = HUDController()
    c.set_quick_actions([{"id": "a", "label": "A"}])
    assert len(c.state.quick_actions) == 1
    assert c.state.quick_actions[0]["id"] == "a"


def test_engine_singleton():
    a = get_omni_engine()
    b = get_omni_engine()
    assert a is b


def test_engine_ingest_text():
    e = OmniInteractionEngine()
    events = []
    e.on_event(lambda p: events.append(p))
    e.ingest(OmniChannel.TEXT.value, text="hola", confidence=0.9)
    assert any(ev["type"] == "omni_command" for ev in events)


def test_engine_ingest_hotkey():
    e = OmniInteractionEngine()
    events = []
    e.on_event(lambda p: events.append(p))
    e.ingest(OmniChannel.HOTKEY.value, text="ctrl+n")
    assert any(ev["type"] == "omni_command" for ev in events)


def test_engine_dispatch_fallback():
    e = OmniInteractionEngine()
    dispatched = []

    class _Orch:
        def execute_omni_command(self, cmd):
            dispatched.append(cmd)

    e.set_orchestrator(_Orch())
    e.ingest(OmniChannel.TEXT.value, text="abre algo")
    assert len(dispatched) >= 1


def test_engine_reset():
    e = get_omni_engine()
    e.ingest(OmniChannel.TEXT.value, text="hola")
    e.reset()
    assert e.hud.state.alerts == []


def test_engine_status():
    e = get_omni_engine()
    s = e.status()
    assert "hud" in s
    assert "offline_only" in s
    assert s["offline_only"] is True
    hud = s["hud"]
    assert "mode" in hud
    assert "position" in hud


def test_engine_hud_action():
    e = OmniInteractionEngine()
    r = e.hud_action("mode", {"mode": "minimal"})
    assert r["status"] == "ok"
    assert r["state"]["mode"] == "minimal"


def test_engine_process_command():
    e = OmniInteractionEngine()
    r = e.process_command({"channel": "text", "text": "hola"})
    assert r["status"] == "ok"
    assert r["input"]["channel"] == "text"


def test_engine_snapshot():
    e = OmniInteractionEngine()
    snap = e.snapshot()
    assert "hud" in snap
    assert "recent_commands" in snap
    assert "offline_only" in snap
    assert snap["offline_only"] is True
