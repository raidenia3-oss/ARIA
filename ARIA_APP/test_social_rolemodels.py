import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import social_rolemodels as sr

def test_lecciones():
    assert sr.lecciones("lectura")
    assert sr.lecciones()

def test_principios():
    assert sr.principios()

def test_no_hacer():
    assert sr.no_hacer()

def test_simulacion():
    # module has no simulacion; check principios usable
    assert sr.principios()