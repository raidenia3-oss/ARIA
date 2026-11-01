import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import inner_thoughts as it

def test_pensar():
    assert it.pensar("hola", ["leccion"]) 

def test_momento():
    assert it.momento_de_intervenir(None) is False