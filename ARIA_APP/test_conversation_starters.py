import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import conversation_starters as cs

def test_starters():
    s = cs.starters_para("Daniel")
    assert s and any("Daniel" in x for x in s)

def test_elegir():
    assert cs.elegir_starter("Daniel")

def test_checkin():
    assert cs.checkin_pendiente(["grafo"])