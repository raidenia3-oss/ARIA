import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import memory_triggers as mt

def test_trigger():
    assert mt.trigger_para("reel instagram") == "reel"
    assert mt.trigger_para("cita") == "social"