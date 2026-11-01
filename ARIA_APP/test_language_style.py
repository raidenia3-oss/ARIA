import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import language_style as ls

def test_estilo():
    assert ls.guia("inicio")
    assert ls.guia("respuesta")