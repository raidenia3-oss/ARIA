import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import reflective_memory as rm

def test_prospectiva():
    assert rm.prospectiva("tarea")

def test_retrospectiva():
    assert rm.retrospectiva("r", "ok")