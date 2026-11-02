import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engagement_loop as el

def test_engagement():
    assert el.ciclo(None, ["tema"])