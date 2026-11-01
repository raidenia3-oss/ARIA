import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import response_composer as rc

def test_componer():
    r = rc.componer("hola", "neutral", ["leccion"], "amable")
    assert "Lección relevante" in r