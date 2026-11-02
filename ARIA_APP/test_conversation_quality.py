import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import conversation_quality as cq

def test_calidad():
    assert cq.evaluar("Entiendo, ¿quieres ayuda?") > 0.5