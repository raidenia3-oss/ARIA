import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import proactive_nudges as pn

def test_nudge_temas():
    assert pn.nudge_si_aplica(0, ["grafo"]) is not None

def test_nudge_none():
    import time
    assert pn.nudge_si_aplica(time.time(), []) is None